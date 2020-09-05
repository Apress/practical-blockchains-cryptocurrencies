"""
Implementation of the Helium block index key-value store
Lets us search for the block that contains a transaction
"""
import plyvel
import pdb
import logging
import json
import rcrypt

"""
log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w", format='%(asctime)s:%(levelname)s:%(message)s', 
    level=logging.DEBUG)

# handle to the Helium blk_index key-value store
bDB = None


def open_blk_index(filepath: "string") -> "db handle or False":
    """
    opens the Helium blk_index store and returns a handle to
    the database. Any directories in filepath must exist. The 
    database will be created if it does not exist.
    Returns a handle to the database or False
    """ 
    try: 
        global bDB
        bDB = plyvel.DB(filepath, create_if_missing=True)
        print("blk_index opened")
    except Exception as err:
        print("open_blk_index: exception: " + str(err))
        logging.debug("open_blk_index: exception: " + str(err))
        return False

    return bDB


def close_blk_index() -> "bool":
    """
    close the Helium block index store
    Returns True if the database is closed, False otherwise
    """
    try: 
        bDB.close()
        if bDB.closed != True: return False

    except Exception as err:
        logging.debug("close_blk_index: exception: " + str(err))
        return False

    return True


def get_blockno(txid: "string") -> "False or integer":
    """
    Receives a transaction id (not a transaction fragment id)
    returns the block no. of the block that contains the transaction:
    """
    
    try:
        # get the block no, return False if the
        # transaction does not exist in the store
        block_no = bDB.get(str.encode(txid))
        if block_no == None:
            raise(ValueError("txid does not have a block no."))

        block_no = block_no.decode()
        block_no = int(block_no)

    except Exception as err:
        logging.debug('get_blockno: exception: ' + str(err))
        return False

    return block_no



def put_index(txid: "string", blockno: "integer") -> "bool":
    """
    Returns True if the trainsactionid_block_no key-value pair is created 
    and False otherwise
    """
    try:
        if len(txid.strip()) != 64:
            raise(ValueError("txid invalid length"))
    
        if len(str(blockno).strip()) == 0:
            raise(ValueError("blockno field is empty"))

        if blockno < 0:
            raise(ValueError("negative blockno"))
  
        # save the transactionid-block no pair in the store
        bDB.put(str.encode(txid), str.encode(str(blockno)))

    except Exception as err:
        logging.debug('put_blockno: exception: ' + str(err))
        return False

    return True


def delete_index(txid: "string"):
    """
    deletes a (txid, blockno) pair from the blk_index store
    """
    try:
         bDB.delete(str.encode(txid))
  
    except Exception as err:
        logging.debug('delete_tx_blockno: exception: ' + str(err))
        return False

    return True

