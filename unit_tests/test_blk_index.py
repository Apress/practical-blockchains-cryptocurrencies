"""
pytest unit tests for the blk_index module 
"""
import blk_index as blkindex
import rcrypt
import pytest
import json
import random
import secrets
import pdb
import os


def setup_module():
    assert bool(blkindex.open_blk_index("hblk_index")) == True
    if os.path.isfile("hblk_index"):
        os.remove("hblk_index")

def teardown_module():
    assert blkindex.close_blk_index() == True


@pytest.mark.parametrize("txid, value, ret", [
     ("",  9, False),
     ("abc", "", False),
     ('290cfd3f3e5027420ed483871309d2a0780b6c3092bef3f26347166b586ff89f', 10899, True),
     (rcrypt.make_uuid(), 9, True),
     (rcrypt.make_uuid(), -1, False),
     (rcrypt.make_uuid(), -56019, False),
     (rcrypt.make_uuid(), 90890231, True),
])
def test_put_index(txid, value, ret):
    """
        tests putting valid and invalid transaction_index and blockno pairs
        into the blk_index store
    """
    assert blkindex.put_index(txid, value) == ret


def test_get_existing_tx():
    """
    test getting a block for an existing transaction
    """
    txid = rcrypt.make_uuid()
    blkindex.put_index(txid, 555)
    assert blkindex.get_blockno(txid) == 555


def get_faketx():
    """
    test getting a block for a fake transaction
    """
    assert blkindex.get_blockno("dummy tx") == False


def test_delete_tx():
    txid = rcrypt.make_uuid()
    blkindex.put_index(txid, 555)
    assert blkindex.delete_index(txid) == True
    assert blkindex.get_blockno(txid) == False
