"""
   pytest unit tests for hmining module
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


def teardown_module():
    #hchaindb.close_hchainstate()
    if os.path.isfile("coinbase_keys.txt"):
         os.remove("coinbase_keys.txt")

##################################
# Synthetic Transaction
##################################
def make_synthetic_transaction():
    """
    makes a synthetic transaction with randomized values
    """

    transaction = {}
    transaction['version'] = hconfig.conf["VERSION_NO"]
    transaction['transactionid'] = rcrypt.make_uuid() 
    transaction['locktime'] = 0
    transaction['vin'] = []
    transaction['vout'] = []

    # make vin list
    vin = {}
    vin["txid"] = rcrypt.make_uuid()
    vin["vout_index"] = 0
    vin["ScriptSig"] = []
    vin["ScriptSig"].append(rcrypt.make_uuid())
    vin["ScriptSig"].append(rcrypt.make_uuid())
    transaction['vin'].append(vin)

    # make vout list
    vout = {}
    vout["value"] = secrets.randbelow(10000000) +1000
    vin["ScripPubKey"] = []
    transaction['vout'].append(vout)
    
    return transaction
 
def make_synthetic_block():
    """
    make synthetic block for unit testing
    """
    block = {}
    block["transactionid"] = rcrypt.make_uuid()
    block["version"] = hconfig.conf["VERSION_NO"]
    block["difficulty_bits"] = hconfig.conf["DIFFICULTY_BITS"]
    block["nonce"] = hconfig.conf["NONCE"]
    block["height"] = 1024
    block["timestamp"] = int(time.time())    
    block["tx"] = []

    # add transactions to the block
    num_tx = secrets.randbelow(6) + 2
    for __ctr in range(num_tx):
        trx = make_synthetic_transaction()
        block["tx"].append(trx)

    block["merkle_root"] =  hblockchain.merkle_root(block["tx"], True)
    block["prevblockhash"] =rcrypt.make_uuid()

    return block


@pytest.mark.parametrize("block_height, reward", [
    (0, 50),
    (1, 50),
    (11, 25),
    (29, 12),
    (31, 12),
    (34, 6),
    (115,0 )
])
def test_mining_reward(block_height, reward):
    """
    test halving of mining reward
    """
    # rescale to test
    hconfig.conf["REWARD_INTERVAL"] = 11
    hconfig.conf["MINING_REWARD"] = 50
    assert hmining.mining_reward(block_height) == reward
    hconfig.conf["MINING_REWARD"] = 5_000_000


def test_tx_in_mempool(monkeypatch):
    """
    test do not add transaction to mempool if it is
    already in the mempool
    """
    hmining.mempool.clear()
    monkeypatch.setattr(tx, "validate_transaction", lambda x: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)

    syn_tx = make_synthetic_transaction()
    hmining.mempool.append(syn_tx)
    assert hmining.receive_transaction(syn_tx) == False
    assert len(hmining.mempool) == 1
    hmining.mempool.clear()


def test_tx_in_chainstate(monkeypatch):
    """
    test do not add transaction if it is accounted for in the 
    Chainstate
    """
    hmining.mempool.clear()
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: {"mock": "fragment"})
    syn_tx = make_synthetic_transaction()
    assert hmining.receive_transaction(syn_tx) == True
    hmining.mempool.clear()


def test_invalid_transaction(monkeypatch):
   """
   tests that an invalid transaction is not added to the mempool
   """
   monkeypatch.setattr(hchaindb, "get_transaction", lambda x: False)
   monkeypatch.setattr(tx, "validate_transaction", lambda x: False)
   hmining.mempool.clear()
   syn_tx = make_synthetic_transaction()
   assert hmining.receive_transaction(syn_tx) == False
   assert len(hmining.mempool) == 0


def test_valid_transaction(monkeypatch):
   """
   tests that an valid transaction is added to the mempool
   """
   monkeypatch.setattr(hchaindb, "get_transaction", lambda x: False)
   monkeypatch.setattr(tx, "validate_transaction", lambda x, y: True, False)
   hmining.mempool.clear()
   syn_tx = make_synthetic_transaction()
   assert hmining.receive_transaction(syn_tx) == True
   assert len(hmining.mempool) == 1
   hmining.mempool.clear()


def test_make_from_empty_mempool():
    """
    test cannot make a candidate block when the mempool is empty
    """
    hmining.mempool.clear()
    assert hmining.make_candidate_block() == False
 

def test_future_lock_time(monkeypatch):
    """ 
    test that transactions locked into the future will not be processed"
    """
    monkeypatch.setattr(tx, "validate_transaction", lambda x: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)

    hmining.mempool.clear()
    tx1 = make_synthetic_transaction()
    tx1["locktime"] = int(time.time()) + 86400
    hmining.mempool.append(tx1)

    assert(bool(hmining.make_candidate_block())) == False


def test_no_transactions():
    """ 
    test that candidate blocks with no transactions are not be processed"
    """
    hmining.mempool.clear()
    tx1 = make_synthetic_transaction()
    tx1[tx] = []
    assert hmining.make_candidate_block() == False


def test_add_transaction_fee(monkeypatch):
    """
    tests that a transaction includes a miners transaction fee
    """
    monkeypatch.setattr(tx, "validate_transaction", lambda x: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)
    monkeypatch.setattr(tx, "transaction_fee", lambda x,y: 12_940)
    trx = make_synthetic_transaction()

    trx = hmining.add_transaction_fee(trx, "pubkey")
    vout_list = trx["vout"]
    vout = vout_list[-1]
    assert vout["value"] == 12_940


def test_make_coinbase_transaction():
    """
    tests making a coinbase transaction
    """
    ctx = hmining.make_coinbase_transaction(10, "synthetic pubkey")
    assert len(ctx["vin"]) == 0
    assert len(ctx["vout"]) == 1
    hash = rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash("synthetic pubkey"))
    assert ctx["vout"][0]["ScriptPubKey"][1] == hash


def test_mine_block(monkeypatch):   
    """
    test that a good block can be mined
    """ 
    block = make_synthetic_block()

    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: False)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x: True)
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(blk_index, "put_index", lambda x,y: True)

    # make the mining easier
    hconfig.conf["DIFFICULTY_NUMBER"] = 0.0001
    assert hmining.mine_block(block) != False
    

def test_receive_bad_block(monkeypatch):
    """
    test that received block is not added to the received_blocks
    list if the block is invalid
    """
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: False)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: False)
    hmining.received_blocks.clear()
    block = make_synthetic_block()
    assert hmining.receive_block(block) == False
    assert len(hmining.received_blocks) == 0


def test_receive_stale_block(monkeypatch):
    """
    test that received block is not added to the received_blocks
    list if the block height is old
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
  
    hmining.received_blocks.clear() 
    for ctr in range(50):
        block = make_synthetic_block()
        block["height"] = ctr 
        hblockchain.blockchain.append(block)

    syn_block = make_synthetic_block()
    syn_block["height"] = 47

    assert hmining.receive_block(syn_block) == False
    hblockchain.blockchain.clear()
    

def test_receive_future_block(monkeypatch):
    """
    test that received block is not added to the received_blocks
    list if the block height is too large
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x,y: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)
  
    hmining.received_blocks.clear() 
    for ctr in range(50):
        block = make_synthetic_block()
        block["height"] = ctr 
        hblockchain.blockchain.append(block)

    syn_block = make_synthetic_block()
    syn_block["height"] = 51

    assert hmining.receive_block(syn_block) == False
    hblockchain.blockchain.clear()


def test_bad_difficulty_number(monkeypatch):
    """
    test that the proof of work fails if the difficulty no 
    does not match
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x,y: True)
    monkeypatch.setattr(hmining, "proof_of_work", lambda x: False)

    block= make_synthetic_block()
    block["difficulty_no"] = -1
    block["nonce"] = 60
    assert hmining.proof_of_work(block) == False


def test_invalid_block(monkeypatch):
    """
    test that received block is not added to the received_blocks
    list if the block is invalid
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x,y: False)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)

    hmining.received_blocks.clear() 
    block = make_synthetic_block()
    assert hmining.receive_block(block) == False
    assert len(hmining.received_blocks) == 0


def test_block_receive_once(monkeypatch):

    """
    test that a received block is not added to the received_blocks
    list if the block is already in the list 
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)

    hmining.received_blocks.clear() 
    block1 = make_synthetic_block()
    hmining.received_blocks.append(block1)

    assert hmining.receive_block(block1) == False
    assert len(hmining.received_blocks) == 1
    hmining.received_blocks.clear()


def test_num_transactions(monkeypatch):
    """
    a received block must contain at least two transactions
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)

    hmining.received_blocks.clear() 
    block1 = make_synthetic_block()
    block1["tx"] = []
    block1["tx"].append(make_synthetic_transaction())
 
    hmining.received_blocks.append(block1)

    assert hmining.receive_block(block1) == False
    assert len(hmining.received_blocks) == 1
    hmining.received_blocks.clear()

def test_coinbase_transaction_present(monkeypatch):
    """
    a received block must contain a coinbase transaction
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)

    hmining.received_blocks.clear() 
    block1 = make_synthetic_block()
    block1["tx"] = [] 

    hmining.received_blocks.append(block1)

    assert hmining.receive_block(block1) == False
    assert len(hmining.received_blocks) == 1
    hmining.received_blocks.clear()


def test_block_in_blockchain(monkeypatch):
    """
    test if a received block is in the blockchain
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)

    block1 = make_synthetic_block()
    block2 = make_synthetic_block()
    hblockchain.blockchain.append(block1)
    hblockchain.blockchain.append(block2)
     
    assert len(hblockchain.blockchain) == 2 
    assert hmining.receive_block(block2) == False
    hblockchain.blockchain.clear()


def test_block_in_secondary_blockchain(monkeypatch):
    """
    test if a received block is in the secondary blockchain
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)

    block1 = make_synthetic_block()
    block2 = make_synthetic_block()
    hblockchain.secondary_blockchain.append(block1)
    hblockchain.secondary_blockchain.append(block2)
     
    assert len(hblockchain.secondary_blockchain) == 2 
    assert hmining.receive_block(block2) == False
    hblockchain.secondary_blockchain.clear()

def test_add_block_received_list(monkeypatch):
    """
    add a block to the received blocks list. test for ablock
    coinbase tx
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    #monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x: True)
    monkeypatch.setattr(blk_index, "put_index", lambda x,y: True)

    block = make_synthetic_block()
    trx = make_synthetic_transaction()
    block["tx"].insert(0, trx)
    assert hmining.receive_block(block) == False
    assert len(hblockchain.blockchain) == 0
 
    hmining.received_blocks.clear()
    hblockchain.blockchain.clear()


def test_fetch_received_block(monkeypatch):
    """
    a block in the received_blocks list can be fetched
    for processing
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x: True)
    block = make_synthetic_block()
    hmining.received_blocks.append(block)

    assert hmining.process_received_blocks() == True
    assert len(hmining.received_blocks) == 0
    hmining.received_blocks.clear()
    hblockchain.blockchain.clear()


def test_remove_received_block(): 
    """
    test removal of a received block from the received_blocks list
    """
    block = make_synthetic_block()
    hmining.received_blocks.append(block)

    assert len(hmining.received_blocks) == 1
    assert hmining.remove_received_block(block) == True
    assert len(hmining.received_blocks) == 0


def test_remove_mempool_transaction(): 
    """
    test removal of a transaction in the mempool
    """
    block = make_synthetic_block()
    hmining.mempool.append(block["tx"][0])

    assert len(hmining.mempool) == 1
    assert hmining.remove_mempool_transactions(block) == True
    assert len(hmining.mempool) == 0


def test_fork_primary_blockchain(monkeypatch):
    """
    test forking the primary blockchain
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x: True)

    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()

    block1 = make_synthetic_block()
    block2 = make_synthetic_block()
    block3 = make_synthetic_block()
    block4 = make_synthetic_block()
    block4["prevblockhash"] = hblockchain.blockheader_hash(block2)

    hblockchain.blockchain.append(block1)
    hblockchain.blockchain.append(block2)
    hblockchain.blockchain.append(block3)
    assert len(hblockchain.blockchain) == 3
    
    hmining.received_blocks.append(block4)
    assert len(hmining.received_blocks) == 1

    hmining.process_received_blocks()
    assert len(hblockchain.blockchain) == 4
    assert len(hblockchain.secondary_blockchain) == 0

    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()


def test_append_to_primary_blockchain(monkeypatch):
    """
    test add a received block to the primary blockchain
    """
    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x: True)

    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()

    block1 = make_synthetic_block()
    block2 = make_synthetic_block()
    block3 = make_synthetic_block()
    block4 = make_synthetic_block()
    block4["prevblockhash"] = hblockchain.blockheader_hash(block3)

    hblockchain.blockchain.append(block1)
    hblockchain.blockchain.append(block2)
    hblockchain.blockchain.append(block3)
    assert len(hblockchain.blockchain) == 3
    
    hmining.received_blocks.append(block4)
    assert len(hmining.received_blocks) == 1

    hmining.process_received_blocks()
    assert len(hblockchain.blockchain) == 4
    assert len(hblockchain.secondary_blockchain) == 0

    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()


def test_add_orphan_block(monkeypatch):
    """
    test add_orphan_block
    """
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()
    hmining.orphan_blocks.clear()

    monkeypatch.setattr(hblockchain, "blockheader_hash", lambda x: "mock_hash")
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y : True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x : True)
    monkeypatch.setattr(blk_index, "put_index", lambda x,y : True)


    block0 = make_synthetic_block()
    block1 = make_synthetic_block()
    block1["height"] = block0["height"] + 1
    block1["prevblockhash"] = "mock_hash"

    hblockchain.blockchain.append(block0)
    hmining.received_blocks.append(block1)
    assert len(hmining.received_blocks) == 1

    hmining.process_received_blocks()
    assert len(hmining.orphan_blocks) == 0
    assert len(hblockchain.blockchain) == 2
    assert len(hblockchain.secondary_blockchain) == 0
    
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()


def test_swap_blockchain():
    """
    test swap the primary and secondary blockchains 
    """
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()

    block1 = make_synthetic_block()
    block2 = make_synthetic_block()
    block3 = make_synthetic_block()
    block4 = make_synthetic_block()
    block4["prevblockhash"] = hblockchain.blockheader_hash(block3)

    hblockchain.blockchain.append(block1)
    hblockchain.secondary_blockchain.append(block2)
    hblockchain.secondary_blockchain.append(block3)
    hblockchain.secondary_blockchain.append(block4)
    assert len(hblockchain.blockchain) == 1
    assert len(hblockchain.secondary_blockchain) == 3
    
    hmining.swap_blockchains()
    assert len(hblockchain.blockchain) == 3
    assert len(hblockchain.secondary_blockchain) == 1

    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()


def test_clear_blockchain():
    """
    test clear the secondary blockchains 
    """
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()

    block1 = make_synthetic_block()
    block2 = make_synthetic_block()
    block3 = make_synthetic_block()
    block4 = make_synthetic_block()
    block5 = make_synthetic_block()

    hblockchain.blockchain.append(block1)
    hblockchain.blockchain.append(block2)
    hblockchain.secondary_blockchain.append(block3)
    hblockchain.blockchain.append(block4)
    hblockchain.blockchain.append(block5)
    assert len(hblockchain.secondary_blockchain) == 1
    assert len(hblockchain.blockchain) == 4
    
    hmining.swap_blockchains()
    assert len(hblockchain.blockchain) == 4
    assert len(hblockchain.secondary_blockchain) == 0

    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()


def test_remove_stale_orphans(monkeypatch):
    """
    test to remove old orphan blocks
    """
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()
    hmining.orphan_blocks.clear()

    block1 = make_synthetic_block()
    block1["height"] = 1290
    block2 = make_synthetic_block()
    block2["height"] = 1285

    monkeypatch.setattr(hblockchain, "blockheader_hash", lambda x: "mock_hash")
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y : True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x : True)
    monkeypatch.setattr(blk_index, "put_index", lambda x,y : True)


    hblockchain.blockchain.append(block1)
    assert len(hblockchain.blockchain) == 1
    hmining.orphan_blocks.append(block2)
    assert len(hmining.orphan_blocks) == 1
    

    hmining.handle_orphans()
    assert len(hmining.orphan_blocks) == 0
    assert len(hblockchain.blockchain) == 1
    assert len(hblockchain.secondary_blockchain) == 0
    
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.orphan_blocks.clear()


def test_add_orphan_to_blockchain(monkeypatch):
    """
    test to add orphan block to blockchain
    """
    hmining.orphan_blocks.clear()
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()

    monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(hblockchain, "blockheader_hash", lambda x: "mockvalue")
    monkeypatch.setattr(tx, "validate_transaction", lambda x, y: True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x: True)
    monkeypatch.setattr(blk_index, "put_index", lambda x, y: True)


    block0 = make_synthetic_block()
    block1 = make_synthetic_block()
    block1["height"] = 1290
    block2 = make_synthetic_block()
    block2["height"] = 1291

    hblockchain.blockchain.append(block0)    
    hblockchain.blockchain.append(block1)
    assert len(hblockchain.blockchain) == 2
    hmining.orphan_blocks.append(block2)
    assert len(hmining.orphan_blocks) == 1
    
    block2["prevblockhash"] = "mockvalue"

    hmining.handle_orphans()
    assert len(hmining.orphan_blocks) == 0
    assert len(hblockchain.blockchain) == 3
    assert len(hblockchain.secondary_blockchain) == 0
    
    hblockchain.blockchain.clear()
    hmining.orphan_blocks.clear()


def test_add_orphan_to_secondary_blockchain(monkeypatch):
    """
    test to add orphan block to the secondary blockchain
    """
    hmining.orphan_blocks.clear()
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()

    #monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x, y: True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x: True)
    monkeypatch.setattr(blk_index, "put_index", lambda x, y: True)


    block0 = make_synthetic_block()
    hblockchain.blockchain.append(block0)
    
    block1 = make_synthetic_block()
    block1["height"] = 1290
    block2 = make_synthetic_block()
    block2["height"] = 1291
    block3 = make_synthetic_block()
    block3["height"] = 1292

    block3["prevblockhash"] = hblockchain.blockheader_hash(block2)

    hblockchain.secondary_blockchain.append(block1)
    hblockchain.secondary_blockchain.append(block2)
    assert len(hblockchain.secondary_blockchain) == 2
    hmining.orphan_blocks.append(block3)
    assert len(hmining.orphan_blocks) == 1
    hmining.handle_orphans()
    assert len(hmining.orphan_blocks) == 0
    assert len(hblockchain.secondary_blockchain) == 1
    assert len(hblockchain.blockchain) == 3
    
    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.orphan_blocks.clear()




def test_append_to_secondary_blockchain(monkeypatch):
    """
    test add a received block to the primary blockchain
    """
    #monkeypatch.setattr(hblockchain, "validate_block", lambda x: True)
    monkeypatch.setattr(tx, "validate_transaction", lambda x,y: True)
    monkeypatch.setattr(hchaindb, "get_transaction", lambda x: True)
    monkeypatch.setattr(hchaindb, "transaction_update", lambda x: True)

    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()

    block1 = make_synthetic_block()
    hblockchain.blockchain.append(block1)

    block2 = make_synthetic_block()
    block3 = make_synthetic_block()
    block4 = make_synthetic_block()
    block4["prevblockhash"] = hblockchain.blockheader_hash(block3)

    hblockchain.secondary_blockchain.append(block2)
    hblockchain.secondary_blockchain.append(block3)
    assert len(hblockchain.blockchain) == 1
    assert len(hblockchain.secondary_blockchain) == 2
    block4["height"] = block3["height"] + 1
    block4["prevblockhash"] = hblockchain.blockheader_hash(block3)
    hmining.received_blocks.append(block4)
    assert len(hmining.received_blocks) == 1

    hmining.process_received_blocks()
    assert len(hblockchain.blockchain) == 3
    assert len(hblockchain.secondary_blockchain) == 1

    hblockchain.blockchain.clear()
    hblockchain.secondary_blockchain.clear()
    hmining.received_blocks.clear()


