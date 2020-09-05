######################################################
# simulated blockchain constructor
######################################################
import blk_index as blkindex
import hchaindb
import hmining
import hconfig
import hblockchain
import rcrypt
import tx
import json
import logging
import pdb
import os
import secrets
import sys
import time

"""
   log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w",  \
format='client: %(asctime)s:%(levelname)s:%(message)s', level=logging.DEBUG)

def startup():
    """
    start the databases
    """
    # start the Chainstate Database
    ret = hchaindb.open_hchainstate("heliumdb")
    if ret == False: return "error: failed to start Chainstate database"  
    else: print("Chainstate Database running")
    # start the LevelDB Database blk_index
    ret = blkindex.open_blk_index("hblk_index")
    if ret == False: return "error: failed to start blk_index"  
    else: print("blkindex Database running")

def stop():
    """
    stop the databases
    """
    hchaindb.close_hchainstate()
    blkindex.close_blk_index()


# unspent transaction fragment values [{fragmentid:value}]
unspent_fragments = []

######################################################
# Make A Synthetic Random Transaction For Testing
# receives a block no and a predicate indicating
# whether the transaction is a coinbase transaction 
######################################################
def make_random_transaction(blockno, is_coinbase):

    txn = {}
    txn["version"] =  "1" 
    txn["transactionid"] = rcrypt.make_uuid()
    if is_coinbase == True: txn["locktime"] = hconfig.conf["COINBASE_LOCKTIME"]
    else: txn["locktime"] = 0
    
    # the public-private key pair for this transaction
    transaction_keys = rcrypt.make_ecc_keys() 
     
    # previous transaction fragments spent by this transaction
    total_spendable = 0


    #######################
    # Build the vin array
    #######################
    txn["vin"] = []
    
    # genesis block transactions have no prior inputs.
    # coinbase transactions do not have any inputs
    if (blockno > 0) and (is_coinbase != True):
        max_inputs = secrets.randbelow(hconfig.conf["MAX_INPUTS"])
        if max_inputs == 0: max_inputs = hconfig.conf["MAX_INPUTS"] - 1

        # get some random previous unspent transaction 
        # fragments to spend
        ind = 0
        ctr = 0

        while ind < max_inputs:
            # get a random unspent fragment from a previous block
            index = secrets.randbelow(len(unspent_fragments))
            frag_dict = unspent_fragments[index]
            key = [*frag_dict.keys()][0]
            val = [*frag_dict.values()][0]
            if val["blockno"] == blockno:
                ctr += 1
                if ctr == 10000:
                    print("failed to get random unspent fragment")
                    return False  
                continue 
            
            unspent_fragments.pop(index)

            total_spendable += val["value"]
            tmp = hchaindb.get_transaction(key)
            if tmp == False: 
                print("cannot get fragment from chainstate: " + key)
            
            
            assert tmp != False
            assert tmp["spent"] == False
            assert tmp["value"] > 0 
            
            # create a random vin element
            key_array = key.split("_")

            signed = rcrypt.sign_message(val["privkey"], val["pubkey"])
            ScriptSig = []
            ScriptSig.append(signed)
            ScriptSig.append(val["pubkey"]) 
            
            txn["vin"].append({
                    "txid": key_array[0],
                    "vout_index": int(key_array[1]),
                    "ScriptSig": ScriptSig
                })
            
            ctr = 0
            ind += 1

    #####################
    # Build Vout list
    #####################
    txn["vout"] = []

    # genesis block
    if blockno == 0:
        total_spendable = secrets.randbelow(10_000_000) + 50_000

    # we need at least one transaction output for non-coinbase 
    # transactions
    if is_coinbase == True: max_outputs = 1
    else:
        max_outputs = secrets.randbelow(hconfig.conf["MAX_OUTPUTS"])
        if max_outputs == 0: max_outputs = 6

    ind = 0

    while ind < max_outputs:
        tmp = rcrypt.make_SHA256_hash(transaction_keys[1])
        tmp = rcrypt.make_RIPEMD160_hash(tmp)

        ScriptPubKey = []
        ScriptPubKey.append("<DUP>")
        ScriptPubKey.append("<HASH-160>")
        ScriptPubKey.append(tmp)
        ScriptPubKey.append("<EQ-VERIFY>")
        ScriptPubKey.append("<CHECK-SIG>")

        if is_coinbase == True:
            value = hmining.mining_reward(blockno)
        else: 
            amt = int(total_spendable/max_outputs)
            value = secrets.randbelow(amt)   # helium cents
            if value == 0:
               pdb.set_trace() 
               value = int(amt / 10) 
            total_spendable -= value
            assert value > 0
            assert total_spendable >= 0

        txn["vout"].append({
                  "value": value,
                  "ScriptPubKey": ScriptPubKey
                })

        # save the transaction fragment
        fragid = txn["transactionid"] + "_" + str(ind)
        fragment = {}
        fragment[fragid] = { "value":value, 
                             "privkey":transaction_keys[0], 
                             "pubkey":transaction_keys[1],
                             "blockno": blockno 
                           }
        unspent_fragments.append(fragment)   
        print("added to unspent fragments: " + fragid)

        if total_spendable <= 0: break
        ind += 1

    return txn


########################################################
# Build some random Synthetic Blocks For Testing.
# Makes num_blocks, sequentially linking each
# block to the previous block through the prevblockhash
# attribute.
# Returns an array of synthetic blocks
#########################################################

def make_blocks(num_blocks):

    ctr = 0      
    blocks = []

    global unspent_fragments
    unspent_fragments.clear()
    hblockchain.blockchain.clear()

    while ctr < num_blocks:
        block = {
                "prevblockhash": "",
                "version": "1",
                "timestamp": int(time.time()),
                "difficulty_bits": 20,
                "nonce": 0,
                "merkle_root": "",
                "height": ctr,
                "tx": []
            }

        # make a random number of transactions for this block
        # genesis block is ctr == 0
        if ctr == 0: num_transactions = 200                      
        else: 
            num_transactions = secrets.randbelow(50)          
            if num_transactions == 0: num_transactions = 40
            num_transactions = 2

        txctr = 0
        while txctr < num_transactions:
            if ctr > 0 and txctr == 0: is_coinbase = True
            else: is_coinbase = False 
            
            trx = make_random_transaction(ctr, is_coinbase)
            assert trx != False 
            block["tx"].append(trx)
            txctr += 1

        if ctr > 0:
            block["prevblockhash"] = hblockchain.blockheader_hash(hblockchain.blockchain[ctr - 1]) 
             
        ret = hblockchain.merkle_root(block["tx"], True)
        assert ret != False
        block["merkle_root"] = ret

        
        ret = hblockchain.add_block(block)
        assert ret == True
        blocks.append(block)
        ctr+= 1

    return blocks






###################################################
# make the simulated blockchain
###################################################
startup()
make_blocks(500)
print("finished synthetic blockchain construction")
stop()
