
"""
pytest unit tests for blockchain functionality
transaction values are synthetic.
"""
import pytest
import hblockchain
import hconfig
import rcrypt
import time
import os
import pdb
import secrets

def teardown_module():
    """
    after all of the tests have been executed, remove any blocks that were created
    """
    os.system("rm *.dat")
    hblockchain.blockchain.clear()


###################################################
# Make A Synthetic Random Transaction For Testing
###################################################
def make_random_transaction(block_height):

    tx = {}
    tx["version"] =  "1" 
    tx["transactionid"] = rcrypt.make_uuid()
    tx["locktime"] = secrets.randbelow(hconfig.conf["MAX_LOCKTIME"])

    # public-private key pair for previous transaction
    prev_keys = rcrypt.make_ecc_keys()

    # public-private key pair for this transaction
    keys = rcrypt.make_ecc_keys()

    # Build vin
    tx["vin"] = []

    if block_height > 0:
        ctr = secrets.randbelow(hconfig.conf["MAX_INPUTS"]) + 1
        ind = 0
        while ind < ctr:
            signed = rcrypt.sign_message(prev_keys[0], prev_keys[1])
            ScriptSig = []
            ScriptSig.append(signed[0])
            ScriptSig.append(prev_keys[1]) 

            tx["vin"].append({
                    "txid": rcrypt.make_uuid(),
                    "vout_index": ctr,
                    "ScriptSig": ScriptSig
                })
            ind += 1

    # Build Vout
    tx["vout"] = []

    ctr = secrets.randbelow(hconfig.conf["MAX_OUTPUTS"]) + 1
    ind = 0
    while ind < ctr:

        ScriptPubKey = []
        ScriptPubKey.append("DUP")
        ScriptPubKey.append("HASH-160")
        ScriptPubKey.append(keys[1])
        ScriptPubKey.append("EQ_VERIFY")
        ScriptPubKey.append("CHECK-SIG")


        tx["vout"] = {
                  "value": secrets.randbelow(10000000) + 1000000,   # helium cents
                  "ScriptPubKey": ScriptPubKey
                }
        ind += 1

    return tx


#############################################
# Build Three Synthetic Blocks For Testing
#############################################
block_0 = {
           "prevblockhash": "",
           "version": "1",
           "timestamp": 0,
           "difficulty_bits": 20,
           "nonce": 0,
           "merkle_root": rcrypt.make_SHA256_hash('msg0'),
           "height": 0,
           "tx": [make_random_transaction(0)]
}



block_1 = {
           "prevblockhash": hblockchain.blockheader_hash(block_0),
           "version": "1",
           "timestamp": 0,
           "difficulty_bits": 20,
           "nonce": 0,
           "merkle_root": rcrypt.make_SHA256_hash('msg1'),
           "height": 1,
}
block_1["tx"] = []
block_1["tx"].append(make_random_transaction(1))
block_1["tx"].append(make_random_transaction(1))


block_2 = {
           "prevblockhash": hblockchain.blockheader_hash(block_1),
           "version": "1",
           "timestamp": 0,
           "difficulty_bits": 20,
           "nonce": 0,
           "merkle_root": rcrypt.make_SHA256_hash('msg2'),
           "height": 2,
}
block_2["tx"] = []
block_2["tx"].append(make_random_transaction(2))
block_2["tx"].append(make_random_transaction(2))


def test_block_type(monkeypatch):
    """
    tests the type of a block
    """
    monkeypatch.setattr(hblockchain, "merkle_root", 
        lambda x, y: rcrypt.make_SHA256_hash('msg0'))
    assert hblockchain.validate_block(block_0) == True


def test_add_good_block(monkeypatch):
    """
    test add a good block
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
         rcrypt.make_SHA256_hash('msg0'))
    assert hblockchain.add_block(block_0) == True

    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    assert hblockchain.add_block(block_1) == True
    hblockchain.blockchain.clear()

def test_missing_version(monkeypatch):
    """
    test for a missing version number
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    monkeypatch.setitem(block_1, "version", "")

    assert hblockchain.add_block(block_1) == False


def test_version_bad(monkeypatch):
    """
    test for an unknown version number
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    monkeypatch.setitem(block_1, "version", -1)

    assert hblockchain.add_block(block_1) == False

def test_bad_timestamp_type(monkeypatch):
    """
    test for a bad timestamp type
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    monkeypatch.setitem(block_1, "timestamp", "12345")

    assert hblockchain.add_block(block_1) == False

def test_negative_timestamp(monkeypatch):
    """
    test for a negative timestamp
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_0, "timestamp", -2)

    assert hblockchain.add_block(block_0) == False


def test_missing_timestamp(monkeypatch):
    """
    test for a missing timestamp
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    monkeypatch.setitem(block_1, "timestamp", "")

    assert hblockchain.add_block(block_1) == False
    

def test_block_height_type(monkeypatch):
    """
    test the type of the block height parameter
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_0, "height", "0")
    
    hblockchain.blockchain.clear()
    assert hblockchain.add_block(block_0) == False


def test_bad_nonce(monkeypatch):
    """
    test for a negative nonce
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    monkeypatch.setitem(block_1, "nonce", -1)

    assert hblockchain.add_block(block_1) == False


def test_missing_nonce(monkeypatch):
    """
    test for a missing nonce
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_0, "nonce", "")
   
    assert hblockchain.add_block(block_0) == False


def test_block_nonce_type(monkeypatch):
    """
    test nonce has the wrong type"
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_0, "nonce", "0")
    
    assert hblockchain.add_block(block_0) == False
   


def test_negative_difficulty_bit(monkeypatch):
    """
    test for negative difficulty bits
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    monkeypatch.setitem(block_1, "difficulty_bits", -5)
   
    assert hblockchain.add_block(block_1) == False


def test_difficulty_type(monkeypatch):
    """
    test difficulty bits has the wrong type"
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_0, "difficulty_bits", "20")
    
    assert hblockchain.add_block(block_0) == False



def test_missing_difficulty_bit(monkeypatch):
    """
    test for missing difficulty bits
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('data'))
    monkeypatch.setitem(block_1, "difficulty_bits", '')

    assert hblockchain.add_block(block_1) == False


def test_read_genesis_block(monkeypatch):
    """
    test reading the genesis block from the blockchain
    """
    hblockchain.blockchain.clear()
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    
    hblockchain.add_block(block_0)
    assert hblockchain.read_block(0) == block_0
    hblockchain.blockchain.clear()


def test_genesis_block_height(monkeypatch):
    """
    test genesis block height
    """
    hblockchain.blockchain.clear()
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
     rcrypt.make_SHA256_hash('msg0'))
    block_0["height"] = 0

    assert hblockchain.add_block(block_0) == True
    blk = hblockchain.read_block(0) 
    assert blk != False
    assert blk["height"] == 0
    hblockchain.blockchain.clear()


def test_read_second_block(monkeypatch):
    """
    test reading the second block from the blockchain
    """
    hblockchain.blockchain.clear()
    assert len(hblockchain.blockchain) == 0

    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y:    
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_1, "prevblockhash", hblockchain.blockheader_hash(block_0))

    ret = hblockchain.add_block(block_0)
    assert ret == True
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: \
        rcrypt.make_SHA256_hash('msg1'))
    ret = hblockchain.add_block(block_1)
    assert ret == True
    block = hblockchain.read_block(1)
    assert block != False
    hblockchain.blockchain.clear()


def test_block_height(monkeypatch):
    """
    test height of the the second block
    """
    hblockchain.blockchain.clear()
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y:  
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_0, "height", 0)
    monkeypatch.setitem(block_0, "prevblockhash", "")
    monkeypatch.setitem(block_1, "height", 1)
    monkeypatch.setitem(block_1, "prevblockhash", hblockchain.blockheader_hash(block_0))

    assert hblockchain.add_block(block_0) == True

    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    assert hblockchain.add_block(block_1) == True
    blk = hblockchain.read_block(1)
    assert blk != False
    assert blk["height"] == 1
    hblockchain.blockchain.clear()


def test_block_size(monkeypatch):
    """
    The block size must be less than hconfig["MAX_BLOCKS"]
    """
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    arry = []
    filler = "0" * 2000000
    arry.append(filler)
    monkeypatch.setitem(block_0, "tx", arry)
    hblockchain.blockchain.clear()
    assert hblockchain.add_block(block_0) == False


def test_genesis_block_prev_hash(monkeypatch):
    """
    test that the previous block hash for the genesis block is empty
    """
    hblockchain.blockchain.clear()
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_0, "height", 0)
    monkeypatch.setitem(block_0, "prevblockhash", rcrypt.make_uuid() )

    assert len(hblockchain.blockchain) == 0 
    assert hblockchain.add_block(block_0) == False


def test_computes_previous_block_hash(monkeypatch):
    """
    test previous block hash has correct format
    """
    val = hblockchain.blockheader_hash(block_0)
    rcrypt.validate_SHA256_hash(val) == True


def test_invalid_previous_hash(monkeypatch):
    """
    test block's prevblockhash is invalid
    """
    hblockchain.blockchain.clear()

    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y:  
        rcrypt.make_SHA256_hash('msg0'))
    monkeypatch.setitem(block_2, "prevblockhash", \
        "188a1fd32a1f83af966b31ca781d71c40f756a3dc2a7ac44ce89734d2186f632")

    hblockchain.blockchain.clear()
    assert hblockchain.add_block(block_0) == True
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg1'))
    assert hblockchain.add_block(block_1) == True

    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
         rcrypt.make_SHA256_hash('msg2'))
    assert hblockchain.add_block(block_2) == False
    hblockchain.blockchain.clear()


def test_no_consecutive_duplicate_blocks(monkeypatch):
    """
    test cannot add the same block twice consecutively to the blockchain
    """
    hblockchain.blockchain.clear()
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
        rcrypt.make_SHA256_hash('msg0'))
    assert hblockchain.add_block(block_0) == True
    
    monkeypatch.setattr(hblockchain, "merkle_root", lambda x, y: 
     rcrypt.make_SHA256_hash('msg1'))
    monkeypatch.setitem(block_1, "prevblockhash", hblockchain.blockheader_hash(block_0))
    assert hblockchain.add_block(block_1) == True
    
    monkeypatch.setitem(block_1, "height", 2)
    assert hblockchain.add_block(block_1) == False
    hblockchain.blockchain.clear()

