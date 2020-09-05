
"""
   hmining.py: The code in this module implements a Helium mining node.
   The node is listening for transactions propagating over the Helium peer-to-peer 
   network. 
"""

import blk_index
import hconfig
import hblockchain as bchain
import hchaindb
import networknode
import rcrypt
import tx
import asyncio
import json
import math
import sys
import time
import threading
import pdb
import logging


"""
   log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w",  \
    format='%(asctime)s:%(levelname)s:%(message)s', 
    level=logging.DEBUG)

"""
address list of nodes on the Helium network
"""
address_list = []


"""
   specify a list container to hold transactions which are received by the miner. 
"""
mempool       = []

"""
  blocks mined by other miners which are received by this mining node
  and are to intended to be appended to this miner's blockchain.
"""  
received_blocks = []

"""
   blocks which are received and cannot be added to the head of the blockchain 
   or the parent of the block at the head of the blockchain.
"""   
orphan_blocks = []

"""
list of transactions to be removed from memcache because they are part of a
block that has been mined
"""   
remove_list = []


semaphore = threading.Semaphore()


def mining_reward(block_height:"integer") -> "non-negative integer":
    """
    The mining_reward function determines the mining reward.
    When a miner successfully mines a block he is entitled to a reward which
    is a number of Helium coins. 
    The reward depends on the number of blocks that have been mined so far. 
    The initial reward  is hconfig.conf["MINING_REWARD"] coins. 
    This reward halves every hconfig.conf["REWARD_INTERVAL"] blocks.
    """

    try:
        # there is no reward for the genesis block
        sz = block_height 
        sz = sz // hconfig.conf["REWARD_INTERVAL"]
        if sz == 0:  return hconfig.conf["MINING_REWARD"] 

        # determine the mining reward
        reward = hconfig.conf["MINING_REWARD"]
        for __ctr in range(0,sz):
            reward = reward/2
        
        # truncate to an integer
        reward = int(round(reward))  

        # the mining reward cannot be less than the lowest denominated 
        # currency unit 
        if reward < hconfig.conf["HELIUM_CENT"]: return 0
            
    except Exception as err:
        print(str(err))
        logging.debug('mining reward: exception: ' + str(err))
        return -1

    return reward


def receive_transaction(transaction: "dictionary") -> "bool":
    """
    receives a transaction propagating over the P2P cryptocurrency network
    this function executes in a thread
    """
    # do not add the transaction if:
    #     it already exists in the mempool
    #     it exists in the Chainstate
    #     it is invalid

    try:
        # if the transaction is in the mempool, return
        for trans in mempool:
            if trans == transaction: return False

        # do not add the transaction if it has been accounted for in
        # the chainstate database.
        tx_fragment_id = transaction["transactionid"] + "_" + "0"

        if hchaindb.get_transaction(tx_fragment_id) != False:
            return True

        # verify that the incoming transaction is valid
        if len(transaction["vin"]) >  0: zero_inputs = False
        else: zero_inputs = True
        if tx.validate_transaction(transaction, zero_inputs) == False:
            raise(ValueError("invalid transaction received"))

        # add the transaction to the mempool
        mempool.append(transaction)

        
        # place the transaction on the P2P network for further
        # propagation
        propagate_transaction(transaction)

    except Exception as err:
        logging.debug('receive_transaction: exception: ' + str(err))
        return False

    return True
    

async def make_candidate_block() -> "dictionary || bool":
    """
    makes a candidate block for inclusion in the Helium blockchain.
    A candidate block is created by:
            (i)  fetching transactions from the  mempool and adding them to 
                 the candidate blocks transaction list.
            (ii) specifying the block header. 

    returns the candidate block or returns False if there is an error or if 
    the mempool is empty.
    Executes in a Python thread
    """
    try:
        # if the mempool is empty then no transactions can be put into 
        # the candidate block
        if len(mempool) == 0: return False
        
        # make a public-private key pair that the miner will use to receive
        # the mining reward as well as the transaction fees.
        key_pair = make_miner_keys()

        block = {}

        # create a incomplete candidate block header
        block['version']   = hconfig.conf["VERSION_NO"]
        block['timestamp'] = int(time.time())
        block['difficulty_bits']    = hconfig.conf["DIFFICULTY_BITS"]
        block['nonce']     = hconfig.conf["NONCE"]
        
        if len(bchain.blockchain) > 0:
             block['height'] = bchain.blockchain[-1]["height"] + 1
        else:
             block['height'] = 0

        block['merkle_root'] = ""

        # get the value of the hash of the previous block's header
        # this induces tamperproofness for the blockchain
        if len(bchain.blockchain) > 0:
             block['prevblockhash'] = bchain.blockheader_hash(bchain.blockchain[-1])
        else:
             block['prevblockhash'] = ""

        
        # calculate the  size (in bytes) of the candidate block header 
        # The number 64 is  the byte size of the SHA-256 hexadecimal 
        # merkle root. The merkle root is computed after all the 
        # transactions are included in the candidate block
        # reserve 1000 bytes for the coinbase transaction
        block_size =  sys.getsizeof(block['version'])
        block_size += sys.getsizeof(block['timestamp']) 
        block_size += sys.getsizeof(block['difficulty_bits']) 
        block_size += sys.getsizeof(block['nonce'])
        block_size += sys.getsizeof(block['height'])
        block_size += sys.getsizeof(block['prevblockhash'])
        block_size += 64
        block_size += sys.getsizeof(block['timestamp'])
        block_size += 1000

        # list of transactions in the block
        block['tx'] = [] 
 

        # get the Unix Time now
        now = int(time.time())


        # add transactions from the mempool to the candidate block until 
        # the transactions in the mempool are exhausted or the block
        # attains it's maximum permissible size
        for memtx in mempool:
                # do not process future transactions
                if memtx['locktime'] > now: continue

                memtx = add_transaction_fee(memtx, key_pair[1])

                # add the transaction to the candidate block
                block_size += sys.getsizeof(memtx)
                if block_size <= hconfig.conf['MAX_BLOCK_SIZE']:
                     block['tx'].append(memtx)
                     remove_list.append(memtx)
                else:
                     break     

        # return if there are no transactions in the block
        if len(block["tx"]) == 0: return False

        # add a coinbase transaction
        coinbase_tx = make_coinbase_transaction(block['height'], key_pair[1])
        block['tx'].insert(0, coinbase_tx)

        # update the length of the block
        block_size += sys.getsizeof(block['tx'])

        # calculate the merkle root of this block
        ret = bchain.merkle_root(block['tx'], True)
        
        if ret == False: 
            logging.debug('mining::make_candidate_block - merkle root error')
            return False

        block['merkle_root'] = ret

        ###################################
        # validate the candidate block
        ###################################
        if bchain.validate_block(block) == False: 
            logging.debug('mining::make_candidate_block - invalid block header')
            return False


    except Exception as err:
        logging.debug('make_candidate_block: exception: ' + str(err))

    # At this stage the candidate block has been created and it can be mined
    return block


def make_miner_keys():
    """
    makes a public-private key pair that the miner will use to receive
    the mining reward and the transaction fee for each transaction.
    This function writes the  keys to a file and returns hash: 
    RIPEMD160(SHA256(public key))
    """

    try:
        keys    = rcrypt.make_ecc_keys()
        privkey = keys[0]
        pubkey  = keys[1]

        pkhash  = rcrypt.make_SHA256_hash(pubkey)
        mdhash  = rcrypt.make_RIPEMD160_hash(pkhash)

        # write the keys to file with the private key as a hexadecimal string
        f = open('coinbase_keys.txt', 'a')
        f.write(privkey)
        f.write('\n')       # newline
        f.write(pubkey)
        f.write('\n')    
        f.close()

    except Exception as err:
        logging.debug('make_miner_keys: exception: ' + str(err))

    return mdhash


def add_transaction_fee(trx: 'dictionary', pubkey: 'string') -> 'dictionary':
    """
    add_transaction_fee directs the transaction fee of a transaction to 
    the miner.
    receives a transaction and a miner's public key.
    amends and returns the transaction so that it consumes the transaction fee.
    """

    try:
        # get the previous transaction fragments
        prev_fragments = []

        for vin in trx["vin"]:
            fragment_id = vin["txid"] + "_" + str(vin["vout_index"])
            prev_fragments.append(hchaindb.get_transaction(fragment_id))

        #  Calculate the transaction fee
        fee = tx.transaction_fee(trx, prev_fragments)

        if fee > 0:
            vout = {}
            vout["value"] = fee
            ScriptPubKey = []
            ScriptPubKey.append('SIG')
            ScriptPubKey.append(rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(pubkey)))
            ScriptPubKey.append('<DUP>')
            ScriptPubKey.append('<HASH_160>')
            ScriptPubKey.append('HASH-160')
            ScriptPubKey.append('<EQ-VERIFY>')
            ScriptPubKey.append('<CHECK_SIG>')
            vout["ScriptPubKey"] = ScriptPubKey
            
            trx["vout"].append(vout)

    except Exception as err:
        logging.debug('add_transaction_fee: exception: ' + str(err))
        return False

    return trx


def make_coinbase_transaction(block_height: "integer", pubkey: "string") -> 'dict':
    """
    makes a coinbase transaction, this is the miner's reward for mining 
    a block. Receives a public key to denote ownership of the reward. 
    Since this is a fresh issuance of heliums there are no vin elements.
    locks the transaction for hconfig["COINBASE_INTERVAL"] blocks.
    Returns the coinbase transaction.
    """
    try:
        # calculate the mining reward 
        reward = mining_reward(block_height)

        # create a coinbase transaction
        trx = {}
        trx['transactionid'] = rcrypt.make_uuid()
        trx['version']  = hconfig.conf["VERSION_NO"]
        # the mining reward cannot be claimed until approximately 100 blocks are mined
        # convert into a time interval
        trx['locktime'] = hconfig.conf["COINBASE_INTERVAL"]*600                         
        trx['vin']  = []
        trx['vout'] = []

        ScriptPubKey = []
        ScriptPubKey.append('SIG')
        ScriptPubKey.append(rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(pubkey)))
        ScriptPubKey.append('<DUP>')
        ScriptPubKey.append('<HASH_160>')
        ScriptPubKey.append('HASH-160')
        ScriptPubKey.append('<EQ-VERIFY>')
        ScriptPubKey.append('<CHECK_SIG>')
        
        # create the vout element with the reward
        trx['vout'].append({
                            'value':  reward, 
                            'ScriptPubKey': ScriptPubKey
                        })

    except Exception as err:
        logging.debug('make_coinbase_transaction: exception: ' + str(err))


    return trx


def remove_mempool_transactions(block: 'dictionary') -> "bool":
    """
    removes the transactions in the candidate block from the mempool
    """
    try:
        for transaction in block["tx"]:
            if transaction in mempool:
                mempool.remove(transaction)  

    except Exception as err:
        logging.debug('remove_mempool_transactions: exception: ' + str(err))
        return False

    return True


async def mine_block(candidate_block: 'dictionary') -> "bool":
    """
    Mines a candidate block.
    Returns the solution nonce as a hexadecimal string if the block is 
    mined and False otherwise
 
    Executes in a Python thread 
    """

    try:
        final_nonce = None
        save_block = dict(candidate_block)

        # Loop until block is mined
        while True:
            # compute the SHA-256 hash for the block header of the candidate block
            hash = bchain.blockheader_hash(candidate_block)
            # convert the SHA-256 hash string to a Python integer
            mined_value = int(hash, 16)
            mined_value = 1/mined_value
        
            # test to determine whether the block has been mined
            if mined_value < hconfig.conf["DIFFICULTY_NUMBER"]:
                final_nonce = candidate_block["nonce"]
                break

            with semaphore:
                if len(received_blocks) > 0:
                    if compare_transaction_lists(candidate_block) == False: 
                        return False

            # failed to mine the block so increment the 
            # nonce and try again
            candidate_block['nonce'] += 1

        logging.debug('mining.py: block has been mined')

        # add block to the miner's blockchain
        with semaphore:
            ret = bchain.add_block(save_block)
            if ret == False:
                raise(ValueError("failed to add mined block to blockchain"))

        # propagate the block on the Helium network
        propagate_mined_block(candidate_block)    

    except Exception as err:
        logging.debug('mine_block: exception: ' + str(err))
        return False

    return hex(final_nonce)


def proof_of_work(block):
    """
    Proves whether a received block has in fact been mined.
    Returns True or False
    """
    try:
        if block['difficulty_bits'] != hconfig.conf["DIFFICULTY_BITS"]:
            raise(ValueError("wrong difficulty bits used"))

        # compute the SHA-256 hash for the block header of the candidate block
        hash = bchain.blockheader_hash(block)
        # convert the SHA-256 hash string to a Python integer to base 10
        mined_value = int(hash, 16)
        mined_value = 1/mined_value

        # test to determine whether the block has been mined
        if mined_value < hconfig.conf["DIFFICULTY_NUMBER"]: return True

    except Exception as err:
        logging.debug('proof_of_work: exception: ' + str(err))
        return False
        
    return False


def receive_block(block):
    """
    Maintains the received_blocks list. 
    Receives a block and returns False if:

    (1)  the block is invalid
    (2)  the block height is less than (blockchain height - 2)
    (3)  block height > (blockchain height + 1)
    (4)  the proof of work fails
    (5)  the block does not contain at least two transactions
    (6)  the first block transaction is not a coinbase transaction
    (7)  transactions in the block are invalid
    (8)  block is already in the blockchain
    (9)  the block is already in the received_blocks list
    
    Otherwise (i)  adds the block to the received_blocks list
             (ii) propagates the block
    
    Executes in a python thread
    """
  
    try:
        # test if block is already in the received_blocks list
        with semaphore:
            for blk in received_blocks:
                if blk == block: return False
    
        # verify the proof of work
        if proof_of_work(block) == False:
            raise(ValueError("block proof of work failed"))

        # reset the nonce to its initial value
        block["nonce"] == hconfig.conf["NONCE"]

        # validate the block
        if bchain.validate_block(block) == False: return False

        if len(bchain.blockchain) > 0:
            # do not add stale blocks to the blockchain
            if block["height"] < bchain.blockchain[-1]["height"] - 2:
                raise(ValueError("block height too old"))

            # do not add blocks that are too distant into the future
            if block["height"] > bchain.blockchain[-1]["height"] + 1:
                raise(ValueError("block height beyond future"))

        # test if block is in the primary or secondary blockchains
        if len(bchain.blockchain) > 0:
            if block == bchain.blockchain[-1]: return False          
    
        if len(bchain.blockchain) > 1:
          if block == bchain.blockchain[-2]: return False          
        
        if len(bchain.secondary_blockchain) > 0:
            if block == bchain.secondary_blockchain[-1]: return False          

        if len(bchain.secondary_blockchain) > 1:
            if block == bchain.secondary_blockchain[-2]: return False          

        # add the block to the blocks_received list
        received_blocks.append(block)
    
        process_received_blocks()

    except Exception as err:
        logging.debug('receive_block: exception: ' + str(err))
        return False

    return True


def process_received_blocks() -> 'bool':
    """
    processes mined blocks that are in the in the received_blocks 
    list and attempts to add these blocks to a blockchain. 

    Algorithm:
     (1)  get a block from the received blocks list.
 
     (2)  if the blockchain is empty and the block has a empty prevblockhash field
          then add the block to the blockchain.

  
     (3)  Compute the block header hash of the last block on the blockchain (blkhash).

          if blkhash == block["prevblockhash"] then add the block to the blockchain.
 

     (4)  if the blockchain has at least two blocks, then if:
             let blk_hash be the hash second-latest block of the blockchain, then if 
             
             block["prevblockhash"] == blk_hash
             
             create a secondary block consisting of all of the blocks of the blockchain
             except for the latest. Append the block to the secondary blockchain.

    (5)  Otherwise move the block to the orphans list.      
                
    (6)  If the received block was attached to a blockchain, for each block in the orphans
         list, try  to attach the orphan block to the primary blockchain or the secondary
         blockchain if it exists.
 
    (7) If the received block was attached to a blockchain and the secondary blockchain has
        elements then swap the blockchain and the secondary blockchain if the length of the
        secondary blockchain is greater.   
 
   (8)  if the receive block was attached and the secondary blockchain has elements then
        clear the secondary blockchain if its length is more than two blocks behind the
        primary blockchain.
  
    Note: Runs In A Python thread 
    """
    while True:
        # process all of the blocks in the received blocks list
        add_flag = False

        # get a received block
        if len(received_blocks) > 0: 
            block = received_blocks.pop()
        else:
            return True

        # add it to the primary blockchain
        with semaphore:
            if bchain.add_block(block) == True:
                logging.debug('receive_mined_block: block added to primary blockchain')
                add_flag = True
            

            # test whether the primary blockchain must be forked                
            # if the previous block hash is equal to the hash of the parent block of the
            # block at the head of the blockchain add the block as a child of the parent and
            # create a secondary blockchain. This constitutes a fork of the primary
            # blockchain        
            elif len(bchain.blockchain) >= 2 and  block['prevblockhash'] == bchain.blockheader_hash(bchain.blockchain[-2]):
                logging.debug('receive_mined_block: forking the blockchain')
                fork_blockchain(block)
                if bchain.add_block(block) == True:
                    logging.debug('receive_mined_block: block added to blockchain')
                    add_flag = True


            # add it to the secondary blockchain
            elif len(bchain.secondary_blockchain) > 0 and block['prevblockhash'] == bchain.blockheader_hash(bchain.secondary_blockchain[-1]):
                swap_blockchains()
                if bchain.add_block(block) == True:
                    logging.debug('receive_mined_block: block added to blockchain')
                    add_flag = True

            # cannot attach the block to a blockchain, place it in the orphans list
            else:
                orphan_blocks.append(block)

        if add_flag == True:
            if block["height"] % hconfig.conf["RETARGET_INTERVAL"] == 0:
                retarget_difficulty_number(block)
            handle_orphans()
            swap_blockchains()

            # remove any transactions in this block that are also
            # in the the mempool
            with semaphore:
                remove_mempool_transactions(block)

        propagate_mined_block(block)

    return True


def fork_blockchain(block: 'list') -> 'bool':

    """
    forks the primary blockchain and creates a secondary blockchain from 
    the primary blockchain and then adds the received block to the secondary block
    """
    try:
        bchain.secondary_blockchain = list(bchain.blockchain[0:-1])
        bchain.secondary_blockchain.append(block)
    
        # switch the primary and secondary blockchain if required
        swap_blockchains()

    except Exception as err:
        logging.debug('fork_blockchain: exception: ' + str(err))
        return False

    return True


def swap_blockchains() -> 'bool':
    """
    compares the length of the primary and secondary blockchains.
    The longest blockchain is designated as the primary blockchain and the other
    blockchain is designated as the secondary blockchain.
    if the primary blockchain is ahead of the secondary blockchin by at least 
    two blocks then clear the secondary blockchain.
    """

    try:
        # if the secondary blockchain is longer than the primary blockchain
        # designate the secondary blockchain as the primary blockchain
        # and the primary blockchain as the secondary blockchain 
        if len(bchain.secondary_blockchain) >= len(bchain.blockchain):
            tmp = list(bchain.blockchain)
            bchain.blockchain = list(bchain.secondary_blockchain)
            bchain.secondary_blockchain = list(tmp)

        # if the primary blockchain is ahead of the secondary blockchain by
        # at least two blocks then clear the secondary blockchain
        if len(bchain.blockchain) - len(bchain.secondary_blockchain) > 2:
            bchain.secondary_blockchain.clear()

    except Exception as err:
        logging.debug('swap_blockchains: exception: ' + str(err))
        return False

    return True


def handle_orphans() -> "bool":
    """
    tries to attach an orphan block to the head of the primary or secondary blockchain.
    Sometimes blocks are received out of order and cannot be attached to the primary 
    or secondary blockchains. These blocks are placed in an orphan_blocks list and as
    new blocks are added to the primary or secondary blockchains, an attempt is made to
    add orphaned  blocks to the blockchain(s).
    """
    try:
        # iterate through the orphan blocks attempting to append an orphan
        # block to a blockchain
        if len(bchain.blockchain) == 0: return
        # try to append to the primary blockchain
        for block in orphan_blocks:
            if block['prevblockhash'] == bchain.blockheader_hash(bchain.blockchain[-1]):
                if block["height"] == bchain.blockchain[-1]["height"] + 1:
                    bchain.blockchain.append(block)
                    orphan_blocks.remove(block)

                    # remove this orphan blocks transactions from the mempool
                    with semaphore:
                        remove_mempool_transactions(block)

        # try to append to the secondary blockchain
        if len(bchain.secondary_blockchain) > 0:
            for block in orphan_blocks:
                if block['prevblockhash'] == bchain.blockheader_hash(bchain.secondary_blockchain[-1]):
                    if block["height"] == bchain.secondary_blockchain[-1]["height"] + 1:
                        bchain.secondary_blockchain.append(block)
                        orphan_blocks.remove(block)
                        
                        # remove this blocks transactions from the mempool
                        with semaphore:
                            remove_mempool_transactions(block)

        # remove stale orphaned blocks
        for block in orphan_blocks:
            if bchain.blockchain[-1]["height"] >=3:
                    if bchain.blockchain[-1]["height"] - block["height"] >= 2: orphan_blocks.remove(block)  

    except Exception as err:
        logging.debug('handle_orphans: exception: ' + str(err))
        return False


    return True


def remove_received_block(block: 'dictionary') -> "bool":
    """
    remove a block from the received blocks list
    """
    try:
        if block in received_blocks:
                received_blocks.remove(block)  

    except Exception as err:
        logging.debug('remove_received_block: exception: ' + str(err))
        return False

    return True


def retarget_difficulty_number(block):
    """
    recalibrates the difficulty number every hconfig.conf["RETARGET_INTERVAL"] blocks
    """
    if block["height"] == 0: return

    old_diff_no   = hconfig.conf["DIFFICULTY_NUMBER"]
    initial_block = bchain.blockchain[(block["height"] - hconfig.conf["RETARGET_INTERVAL"])]
    time_initial  = initial_block["timestamp"] 
    time_now      = block["timestamp"]

    elapsed_seconds = time_now - time_initial 
    # the average time to mine a block is 600 seconds
    blocks_expected_to_be_mined = int(elapsed_seconds / 600) 
    discrepancy = 1000 - blocks_expected_to_be_mined

    hconfig.conf["DIFFICULTY_NUMBER"] =  old_diff_no - \
        old_diff_no * (20/100)*(discrepancy /(1000 + blocks_expected_to_be_mined)) 

    return


def propagate_transaction(txn: "dictionary"):
    """
    propagates a transaction that is received
    """
    if len(address_list) % 20 == 0: get_address_list()
    cmd = {}
    cmd["jsonrpc"] = "2.0"
    cmd["method"]  = "receive_transaction"
    cmd["params"]  = {"trx":txn}
    cmd["id"] = 0

    for addr in address_list:
        rpc = json.dumps(cmd)
        networknode.hclient(addr,rpc)
    
    return


def propagate_mined_block(block): 
    """
    sends a block to other mining nodes so that they may add this block
    to their blockchain. 
    We refresh the list of known node addresses periodically
    """
    if len(address_list) % 20 == 0: get_address_list()
    
    cmd = {}
    cmd["jsonrpc"] = "2.0"
    cmd["method"]  = "receive_block"
    cmd["params"]  = {"block":block}
    cmd["id"] = 0

    for addr in address_list:
        rpc = json.dumps(cmd)
        networknode.hclient(addr,rpc)

    return


def get_address_list():
    '''
    update the list of node addresses that are known
    AMEND IP ADDRESS AND PORT AS REQUIRED.
    '''
    ret = networknode.hclient("http://127.0.0.69:8081", 
           '{"jsonrpc":"2.0","method":"get_address_list","params":{},"id":1}')
    if ret.find("error") != -1: return
    retd = json.loads(ret)

    for addr in retd["result"]:
        if address_list.count(addr) == 0:
            address_list.append(addr)

    return         


def start_mining():
    """
    assemble a candidate block
    then mine this block
    """
    while True:
        candidate_block = make_candidate_block()
        if candidate_block() == False:
            time.sleep(1)
            continue
        # remove transactions in the mined block from the mempool
        if mine_block(candidate_block) != False:
            remove_mempool_transactions(remove_list)
        else: time.sleep(1)


def compare_transaction_lists(block):
    """
    tests whether a transaction in a received block is also in a candidate
    block that is being mined
    """      
    for tx1 in block["tx"]:
        for tx2 in remove_list:
            if tx1 == tx2: return False
 
    return True        


#####################################
# start mining in a thread:
# $(virtual) python hmining.py 
#####################################

if __name__ == "__main__":
    #Create the Threads
    t1 = threading.Thread(target=start_mining, args=(), daemon=True)
    t1.start()
    t1.join()






 