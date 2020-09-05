"""
   integration tests for hmining module
"""
import hmining
import hblockchain
import tx
import hchaindb
import blk_index
import hconfig
import rcrypt
import plyvel
import random
import secrets
import time
import pytest
import pdb
import os

def setup_module():
    hchaindb.open_hchainstate("heliumdb")
    blk_index.open_blk_index("hblk_index")

def teardown_module():
    hchaindb.close_hchainstate()
    blk_index.close_blk_index()
    if os.path.isfile("coinbase_keys.txt"):
         os.remove("coinbase_keys.txt")

# transactionid: (private_key, public_key)
tx_keys = {}

##################################
# Synthetic Transaction
##################################
def make_synthetic_transaction(block):
    """
    makes a synthetic transaction with randomized values
    """

    transaction = {}
    transaction['version'] = hconfig.conf["VERSION_NO"]
    transaction['transactionid'] = rcrypt.make_uuid() 
    transaction['locktime'] = 0
    transaction['vin'] = []
    transaction['vout'] = []

    # make public-private key pair for the transaction
    pair = rcrypt.make_ecc_keys()
    tx_keys[transaction["transactionid"]] = pair

    # make vin list
    # genesis block does not have inputs
    if block["height"] > 0:
        num_inputs = secrets.randbelow(3) + 1
        for ctr in range(num_inputs):
            trx = make_synthetic_vin(transaction, ctr)
            if trx == False: break
            transaction["vin"].append(trx)

    # make vout list
    num_outputs = secrets.randbelow(5) + 1
    ctr = 0
    for ctr in range(num_outputs):
        vout = make_synthetic_vout(block, transaction, ctr, pair[1])
        if vout != False: transaction["vout"].append(vout)

    block["tx"].append(transaction)
    hchaindb.transaction_update(transaction)

    return transaction


#############################
# make a synthetic vin list
#############################

def make_synthetic_vin(transaction, vin_index):
    """
    make a vin object 
    """
    vin = {}

    # get a transaction fragment to consume from HeliumDB
    # get some random block earlier then our consuming block
    #        select a random vout element
    #        check Heliumb to see if output spent
    #        if not add it


    # get a transaction fragment to consume 
    
    for ctr in range(10):
                
        if wfragment["spent"]== False: break 
        if ctr == 10: return False         # could not get any inputs
    
    vin['txid'] = wfragment["transactionid"]  
    vin['vout_index'] = wfragment["vout_index"]

    keys = tx_keys[wfragment["transactionid"]]

    vin['ScriptSig'] = []
    vin["ScriptSig"].append(rcrypt.sign_message(keys[0], keys[1]))
    vin["ScriptSig"].append(keys[1])

    return vin
 

#############################
# make a synthetic vout list
#############################

def make_synthetic_vout(block, trx, vout_index, pubkey):
    """
    make a randomized vout element
    receives a public key
    returns the vout dict element
    """
    vout = {}
    
    # genesis transaction
    # spendable values
    if block["height"] == 0:
         vout['value'] = secrets.randbelow(10_000_000_000_000) +10  # helium cents
    else:
        value_received = 0
        ctr = 0
        for vin in trx["vin"]:
             fragmentid = vin["txid"] + "_" + str(ctr) 
             fragment = hchaindb.get_transaction(fragmentid)
             if fragment == False: break
             value_received += fragment["value"] 
             ctr += 1
             if value_received < 0: raise(ValueError("negative value receive by vin"))

        if value_received == 0: return False 
        value_spent = 0
        for vout in trx["vout"]:
            value_spent += vout["value"]

        value_available = value_received - value_spent
        if value_available < 0: raise(ValueError("funds available are negative")) 
        if value_available == 0: return False
        vout['value'] = secrets.randbelow(value_available) + 1000


    ripemd_hash = rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(pubkey))    
    tmp = []
    tmp.append('<DUP>')
    tmp.append('<HASH-160>')
    tmp.append(ripemd_hash)
    tmp.append('<EQ-VERIFY>')
    tmp.append('<CHECK-SIG>')
    vout["ScriptPubKey"] = [] 
    vout['ScriptPubKey'].append(tmp)

  
    #add fragment to wallet
    fragment["transactionid"] = trx["transactionid"]
    fragment["vout_index"] = vout_index
    wallet.append(fragment )

    return vout


#########################################
# Make A Synthetic Blocks
# receives the number of blocks to make
# inserts the blocks into the blockchain
# #######################################
def make_synthetic_blocks(num_blocks):
    """
    make synthetic blocks for unit testing
    add the blocks to the blockchain
    """

    for ctr in range(num_blocks):

        block = {}
        block["transactionid"] = rcrypt.make_uuid()
        block["version"] = hconfig.conf["VERSION_NO"]
        block["difficulty_bits"] = hconfig.conf["DIFFICULTY_BITS"]
        block["nonce"] = hconfig.conf["NONCE"]
        block["height"] = ctr
        block["timestamp"] = int(time.time())    
        block["tx"] = []

        # add transactions to the block
        num_tx = secrets.randbelow(5) + 1
        for __ctr in range(num_tx):
            trx = make_synthetic_transaction(block)
            block["tx"].append(trx)

        block["merkle_root"] =  hblockchain.merkle_root(block["tx"], True)

        if ctr == 0:
            block["prevblockhash"] = ""
        else:
            block["prevblockhash"] = hblockchain.blockheader_hash(hblockchain.blockchain[ctr -1])

        # append block to blockchain
        hblockchain.blockchain.append(block)
        

    return


def test_make_blocks():
    tx_keys.clear()
    wallet.clear()
    make_synthetic_blocks(2)
    tx_keys.clear()
    wallet.clear()
