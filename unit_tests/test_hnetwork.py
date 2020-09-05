###################################################################################
# test a helium network
###################################################################################
import blk_index as blkindex
import hchaindb
import hmining
import hconfig
import hblockchain
import networknode
import rcrypt
import tx
import json
import logging
import pdb
import pytest
import os
import secrets
import sys
import time

"""
   log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w",  \
format='client: %(asctime)s:%(levelname)s:%(message)s', level=logging.DEBUG)

def setup_module():
        os.system("rm -rf ../data/heliumdb/*")
        os.system("rm -rf ../data/hblk_index/*")
        os.system("rm *.log")
        
        # start the Chainstate Database
        ret = hchaindb.open_hchainstate("../data/heliumdb")
        if ret == False: return "error: failed to start Chainstate database"  
        else: print("Chainstate Database running")
        # start the LevelDB Database blk_index
        ret = blkindex.open_blk_index("../data/hblk_index")
        if ret == False: return "error: failed to start blk_index"  
        else: print("blkindex Database running")


def teardown_module():
    """
    remove the debug logs, close databases
    """
    hchaindb.close_hchainstate()
    blkindex.close_blk_index()

# unspent transaction fragment values [{fragmentid:value}]
unspent_fragments = []

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
    if is_coinbase == True: max_outputs = hconfig.conf["MAX_OUTPUTS"]
    else:
        max_outputs = secrets.randbelow(hconfig.conf["MAX_OUTPUTS"])
        if max_outputs <= 1: max_outputs = 2

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
        #print("added to unspent fragments: " + fragid)

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
        

        txctr = 0
        while txctr < num_transactions:
            if ctr > 0 and txctr == 0: is_coinbase = True
            else: is_coinbase = False 
            
            trx = make_random_transaction(ctr, is_coinbase)
            assert trx != False 
            block["tx"].append(trx)
            txctr += 1

        if ctr > 0:
            block["prevblockhash"] = \
               hblockchain.blockheader_hash(hblockchain.blockchain[ctr - 1]) 
             
        ret = hblockchain.merkle_root(block["tx"], True)
        assert ret != False
        block["merkle_root"] = ret

        
        ret = hblockchain.add_block(block)
        assert ret == True
        blocks.append(block)
        ctr+= 1

    return blocks


def test_register_address():
    '''
    test address registration with the directory server at 127.0.0.69:8081' 
    '''
    #test 1
    ret = networknode.hclient("http://127.0.0.69:8081",
    '{"jsonrpc":"2.0","method":"register_address","params":{"address":"127.0.0.19:8081"},"id":1}')
    
    result = (json.loads(ret))["result"]
    print(result)
    assert result.find("error") == -1
    
    #test 2
    ret = networknode.hclient("http://127.0.0.69:8081",
    '{"jsonrpc":"2.0","method":"register_address","params":{"address":"127.0.0.19"},"id":2}')
    
    result = (json.loads(ret))["result"]
    print(result)
    assert result.find("error") >= 0

    #test 3
    ret = networknode.hclient("http://127.0.0.69:8081",
    '{"jsonrpc":"2.0","method":"register_address","params":{"address":"127.0.0:8081"},"id":3}')
    
    result = (json.loads(ret))["result"]
    print(result)
    assert result.find("error")  >= 0
    

def test_get_address_list():
     '''
     get an address list from a directory server. These are synthetic addresses,
     servers are not running at these addresses.
     '''
     ret = networknode.hclient("http://127.0.0.69:8081", 
           '{"jsonrpc":"2.0","method":"get_address_list","params":{},"id":4}')
     assert (ret.find("error")) == -1
     retd = json.loads(ret)
     assert "127.0.0.10:8081" in retd["result"]
     print(ret)


def test_get_blockchain_height():
    """ test get the height of some node's blockchain"""

    blocks = make_blocks(2)
    assert len(blocks) == 2
    
    # clear the primary and secondary blockchains for this test
    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc": "2.0", "method": "clear_blockchain", "params": {}, "id": 10}')
    assert ret.find("ok") != -1 

    rpc   = json.dumps({"jsonrpc":"2.0","method":"receive_block",
        "params":{"block": blocks[0]}, "id":11})
    ret = networknode.hclient("http://127.0.0.51:8081",rpc)
    assert ret.find("ok") != -1

    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc": "2.0", "method": "get_blockchain_height", "params": {}, "id": 12}')
    assert ret.find("error") == -1 
    height = (json.loads(ret))["result"]
    assert height == 0

    rpc   = json.dumps({"jsonrpc":"2.0","method":"receive_block",
        "params":{"block": blocks[1]}, "id":13})
    ret = networknode.hclient("http://127.0.0.51:8081",rpc)
    assert ret.find("ok") != -1

    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc": "2.0", "method": "get_blockchain_height", "params": {}, "id": 14}')
    assert ret.find("error") == -1 
    height = (json.loads(ret))["result"]
    assert height == 1


def test_receive_block():
    """
    send a block to a remote node. The remote node returns ok 
    if the block is appended to its received_blocks list,
    otherwise returns an error string
    """
    blocks = make_blocks(2)
    assert len(blocks) == 2

    # clear the primary and secondary blockchains for this test
    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc": "2.0", "method": "clear_blockchain", "params": {}, "id": 10}')
    assert ret.find("ok") != -1 

    rpc   = json.dumps({"jsonrpc":"2.0","method":"receive_block",
        "params":{"block": blocks[0]}, "id":8})
    ret = networknode.hclient("http://127.0.0.51:8081",rpc)
    assert ret.find("ok") != -1
     
    rpc   = json.dumps({"jsonrpc":"2.0","method":"receive_block",
        "params":{"block": blocks[1]}, "id":9})
    ret = networknode.hclient("http://127.0.0.51:8081",rpc)
    assert ret.find("ok") != -1
     

def test_receive_transaction():
    """
    send a transaction to a remote node. The remote node returns ok 
    if the transaction is appended to its mempool.
    Otherwise returns an error string
    """
    blocks = make_blocks(2)
    assert len(blocks) == 2

    # clear the primary and secondary blockchains for this test
    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc":"2.0", "method": "clear_blockchain", "params": {}, "id": 15}')
    assert ret.find("ok") >= 0 

    rpc   = json.dumps({"jsonrpc":"2.0","method":"receive_transaction",
        "params":{"trx":blocks[0]["tx"][0]},"id":16})
    ret = networknode.hclient("http://127.0.0.51:8081",rpc)
    assert ret.find("ok") >= 0 

    rpc   = json.dumps({"jsonrpc":"2.0","method":"receive_transaction",
         "params":{"trx": blocks[0]["tx"][1]}, "id":17})
    ret = networknode.hclient("http://127.0.0.51:8081",rpc)
    assert ret.find("ok") >= 0


def test_clear_blockchain(monkeypatch):
    """
    builds and clears the primary and secondary blockchains of a node
    """
    # clear the primary and secondary blockchains for this test
    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc":"2.0", "method": "clear_blockchain", "params": {}, "id": 19}')
    assert ret.find("ok") >= 0 

    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)

    num_blocks = 20
    blocks = make_blocks(num_blocks)
    assert len(blocks) == num_blocks


    tmp = hblockchain.blockheader_hash(blocks[0])
    assert tmp == blocks[1]["prevblockhash"]
    assert blocks[1]["height"] == 1

    rpc   = json.dumps({"jsonrpc":"2.0","method":"receive_block",
        "params":{"block": blocks[0]}, "id":21})
    ret = networknode.hclient("http://127.0.0.51:8081",rpc)
    assert ret.find("ok") != -1

    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc": "2.0", "method": "get_blockchain_height", "params": {}, "id": 22}')
    assert ret.find("error") == -1 
    height = (json.loads(ret))["result"]
    # value of height attribute of the latest block in the blockchain
    # meaning there is one block in the blockchain
    assert height == 0

    rpc   = json.dumps({"jsonrpc":"2.0","method":"receive_block",
        "params":{"block": blocks[1]}, "id":23})
    ret = networknode.hclient("http://127.0.0.51:8081",rpc)
    assert ret.find("ok") != -1

    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc": "2.0", "method": "get_blockchain_height", "params": {}, "id": 24}')
    assert ret.find("error") == -1 
    height = (json.loads(ret))["result"]
    # value of height attribute of the latest block in the blockchain
    # meaning there are two blocks in the blockchain
    assert height == 1

    # clear the primary and secondary blockchains for this test
    ret = networknode.hclient("http://127.0.0.51:8081",
             '{"jsonrpc":"2.0", "method": "clear_blockchain", "params": {}, "id": 25}')
    assert ret.find("ok") >= 0