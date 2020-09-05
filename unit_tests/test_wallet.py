######################################################
# test_wallet.rb
######################################################
import hchaindb
import hmining
import hconfig
import hblockchain
import rcrypt
import tx
import wallet
import json
import logging
import os
import pdb
import pytest
import secrets
import sys
import time

"""
   log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w",  \
format='client: %(asctime)s:%(levelname)s:%(message)s', level=logging.DEBUG)

def setup_module():
    """
    start the databases
    """
    # start the Chainstate Database
    ret = hchaindb.open_hchainstate("heliumdb")
    if ret == False: 
        print("error: failed to start Chainstate database")
        return  
    else: print("Chainstate Database running")

    # make a simulated blockchain with height 5
    make_blocks(5)


def teardown_module():
    """
    stop the databases
    """
    hchaindb.close_hchainstate()


# unspent transaction fragment values [{fragmentid:value}]
unspent_fragments = []

keys = []


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
    global keys
    keys.append(transaction_keys) 


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

            if frag_dict["blockno"] == blockno or frag_dict["value"] < 10:
                ctr += 1
                if ctr == 10000:
                    print("failed to get random unspent fragment")
                    return False  
                continue 
            
            key = frag_dict["key"]
            unspent_fragments.pop(index)
            assert unspent_fragments.count(frag_dict) == 0

            total_spendable += frag_dict["value"]
            tmp = hchaindb.get_transaction(key)
            if tmp == False: 
                print("cannot get fragment from chainstate: " + key)
            
            assert tmp["spent"] == False
            assert tmp["value"] > 0 
            
            # create a random vin element
            key_array = key.split("_")

            signed = rcrypt.sign_message(frag_dict["privkey"], frag_dict["pubkey"])
            ScriptSig = []
            ScriptSig.append(signed)
            ScriptSig.append(frag_dict["pubkey"]) 
            
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
        total_spendable = secrets.randbelow(10000000) + 50000

    # we need at least one transaction output for non-coinbase 
    # transactions
    if is_coinbase == True: max_outputs = 1
    else:
        max_outputs = secrets.randbelow(hconfig.conf["MAX_OUTPUTS"])
        if max_outputs == 0: max_outputs = hconfig.conf["MAX_OUTPUTS"]

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
            if amt == 0: break
            value = secrets.randbelow(amt)   # helium cents
            if value == 0: value = int(amt) 
            total_spendable -= value
            assert value > 0
            assert total_spendable >= 0

        txn["vout"].append({
                  "value": value,
                  "ScriptPubKey": ScriptPubKey
                })

        # save the transaction fragment
        fragid = txn["transactionid"] + "_" + str(ind)
        fragment = {
                        "key": fragid,
                        "value":value, 
                        "privkey":transaction_keys[0], 
                        "pubkey":transaction_keys[1],
                        "blockno": blockno 
                    }
        unspent_fragments.append(fragment)   
        print("added to unspent fragments: " + fragment["key"])

        if total_spendable <= 50: break
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
    total_tx = 0 
    blocks = []

    global unspent_fragments
    unspent_fragments.clear()
    hblockchain.blockchain.clear()

    while ctr < num_blocks:
        block = {}
        block["prevblockhash"] = ""
        block["version"] = hconfig.conf["VERSION_NO"]
        block["timestamp"] = int(time.time())
        block["difficulty_bits"] = hconfig.conf["DIFFICULTY_BITS"]
        block["nonce"] = hconfig.conf["NONCE"]
        block["merkle_root"] = ""
        block["height"] = ctr
        block["tx"] = []

        # make a random number of transactions for this block
        # genesis block is ctr == 0
        if ctr == 0: num_transactions = 200                      
        else: 
            num_transactions = secrets.randbelow(50)          
            if num_transactions <= 1: num_transactions = 25

        txctr = 0
        while txctr < num_transactions:
            if ctr > 0 and txctr == 0: coinbase_trans = True
            else: coinbase_trans = False 
            
            trx = make_random_transaction(ctr, coinbase_trans)
            assert trx != False 
            block["tx"].append(trx)
            total_tx += 1
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

    print("blockchain height: " + str(blocks[-1]["height"]))
    print("total transactions count: " + str(total_tx))

    return blocks



def test_no_values_received():
    """
    get all of the transaction values received by the wallet-holder
    when the holder has no keys
    """
    wallet.wallet_state["keys"] = []
    wallet.value_received(0)
    assert wallet.wallet_state["received"] == [] 


@pytest.mark.parametrize("index", [
     (0),
     (1),
     (11),
     (55),
])
def test_values_received(index):
    """
    test that each value received by the wallet-owner pertains to a 
    public key owned by the wallet-owner.
    Note: At least 55 private-public keys must have been generated.
    """
    wallet.initialize_wallet()
    wallet.wallet_state["keys"] = []
    my_key_pairs = keys[:]

    for _ in range(index):
        key_index = secrets.randbelow(len(my_key_pairs))
        wallet.wallet_state["keys"].append(keys[key_index])

    # remove any duplicates
    wallet.wallet_state["keys"] = list(set(wallet.wallet_state["keys"]))

    my_public_keys = []
    for key_pair in wallet.wallet_state["keys"]:
        my_public_keys.append(key_pair[1])

    wallet.value_received(0)
    for received in wallet.wallet_state["received"]:
        assert received["public_key"] in my_public_keys 


def test_one_received():
    """
    test that for a given public key owned by the wallet-holder, at least one 
    transaction fragment exists in the wallet. 
    """
    wallet.initialize_wallet()
    wallet.wallet_state["keys"] = []

    key_index = secrets.randbelow(len(keys))
    wallet.wallet_state["keys"].append(keys[key_index])
    
    ctr = 0

    wallet.value_received(0)

    for received in wallet.wallet_state["received"]:
        if received["public_key"] == wallet.wallet_state["keys"][0][1]: ctr  += 1 
    assert ctr >= 1


@pytest.mark.parametrize("index", [
     (0),
     (1),
     (13),
     (49),
     (55)
])
def test_values_spent(index):
    """
    test that values spent pertain to public keys owned by the wallet-owner.
    Note: At least 55 private-public keys must hav been generated.
   """
    wallet.initialize_wallet()
    wallet.wallet_state["keys"] = []
    my_key_pairs = keys[:]

    for _ in range(index):
        key_index = secrets.randbelow(len(my_key_pairs))
        wallet.wallet_state["keys"].append(keys[key_index])

    # remove any duplicates
    wallet.wallet_state["keys"] = list(set(wallet.wallet_state["keys"]))

    my_public_keys = []
    for key_pair in wallet.wallet_state["keys"]:
        my_public_keys.append(key_pair[1])

    wallet.value_spent(0)
    for spent in wallet.wallet_state["spent"]:
        assert spent["public_key"] in my_public_keys 


def test_received_and_spent():
    """
    test that if a transaction fragment is spent then it has also been 
    received by the wallet-owner.
    """
    wallet.initialize_wallet()
    wallet.wallet_state["keys"] = []

    key_index = secrets.randbelow(len(keys))
    wallet.wallet_state["keys"].append(keys[key_index])
    
    wallet.value_received(0)
    wallet.value_spent(0)
    assert len(wallet.wallet_state["received"]) >= 1

    for spent in wallet.wallet_state["spent"]:
        ctr = 0
        assert spent["public_key"] == wallet.wallet_state[keys][0][1] 
        ptr = spent["fragmentid"]
        for received in wallet.wallet_state["received"]:
            if received["fragmentid"] == ptr: ctr += 1
        assert ctr == 1
        ctr = 0


def test_wallet_persistence():
    """
    test the persistence of a wallet to a file.
    """
    wallet.initialize_wallet()
    wallet.wallet_state["keys"] = []
    my_key_pairs = keys[:]

    for _ in range(25):
        key_index = secrets.randbelow(len(my_key_pairs))
        wallet.wallet_state["keys"].append(keys[key_index])

    # remove any duplicates
    wallet.wallet_state["keys"] = list(set(wallet.wallet_state["keys"]))
    wallet.value_spent(0)
    wallet.value_received(0)

    wallet_str = json.dumps(wallet.wallet_state)
    wallet_copy = json.loads(wallet_str)

    assert wallet.save_wallet() == True
    assert wallet.load_wallet() == True

    assert wallet.wallet_state["received"] == wallet_copy["received"]
    assert wallet.wallet_state["spent"] == wallet_copy["spent"]
    assert wallet.wallet_state["received_last_block_scanned"] == wallet_copy["received_last_block_scanned"]
    assert wallet.wallet_state["spent_last_block_scanned"] == wallet_copy["spent_last_block_scanned"]

    max = len(wallet_copy["keys"])
    ctr = 0

    for ctr in range(max):    
        assert wallet.wallet_state["keys"][ctr][0] == wallet_copy["keys"][ctr][0]
        assert wallet.wallet_state["keys"][ctr][1] == wallet_copy["keys"][ctr][1]

