"""
hbockchain.py: This module creates and maintains the Helium blockchain
"""
import rcrypt
import hconfig
import hchaindb
import tx
import blk_index as blockindex
import json
import pickle
import pdb
import logging
import os
"""
log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w", format='%(asctime)s:%(levelname)s:%(message)s', 
    level=logging.DEBUG)


"""
A block is a Python dictionary that has the following 
structure. The type of an attribute is denoted in angle delimiters.

               {
                  "prevblockhash":   <string>
                  "version":         <string>
                  "timestamp":       <integer>
                  "difficulty_bits": <integer>
                  "nonce":           <integer>
                  "merkle_root":     <string>
                  "height":          <integer>
                  "tx":              <list>
              }
                 
The blockchain is a list where each list element is a block
This is also referred to as the primary blockchain when used
by miners.
"""
blockchain   = []


"""
secondary block used by mining nodes
"""
secondary_blockchain = []


def add_block(block: "dictionary") -> "bool":
    """
    add_block: adds a block to the blockchain. Receives a block.
    The block attributes are checked for validity and each transaction in the block is
    tested for validity. If there are no errors, the block is written to a file as a 
    sequence of raw bytes. Then the block is added to the blockchain.
    The chainstate database and the blk_index databases are updated.
    returns True if the block is added to the blockchain and False otherwise
    """
    try:
        # validate the received block parameters
        if validate_block(block) == False:
            raise(ValueError("block validation error"))

        # validate the transactions in the block
        # update the chainstate database
     
        for trx in block['tx']:
            # first transaction in the block is a coinbase transaction
            if block["height"] == 0 or block['tx'][0] == trx: zero_inputs = True
            else: zero_inputs = False

            if tx.validate_transaction(trx, zero_inputs) == False: 
                raise(ValueError("transaction validation error"))
                    
            if hchaindb.transaction_update(trx) == False:
                raise(ValueError("chainstate update transaction error"))

        # serialize the block to a file
        if (serialize_block(block) == False):
                raise(ValueError("serialize block error"))

        # add the block to the blockchain in memory
        blockchain.append(block)

        #  update the blk_index
        for transaction in block['tx']:
            blockindex.put_index(transaction["transactionid"], block["height"])

    except Exception as err:
        print(str(err))
        logging.debug('add_block: exception: ' + str(err))
        return False

    return True


def serialize_block(block: "dictionary") -> "bool":
    """
    serialize_block: serializes a block to a file using pickle.
    Returns True if the block is serialized and False otherwise. 
    """
    index = len(blockchain)
    filename = "block_" + str(index) + ".dat"
    
    # create the block file and serialize the block
    try: 
        f = open(filename, 'wb')
        pickle.dump(block, f)

    except Exception as error:
        logging.debug("Exception: %s: %s", "serialize_block", error)
        f.close()
        return False

    f.close()

    return True


def read_block(blockno: 'long') -> "dictionary or False":
    """
    read_block: receives an index into the Helium blockchain.
    Returns a block or False if the block does not exist.
    """
    try:
        block = blockchain[blockno]
        return block

    except Exception as error:
        logging.debug("Exception: %s: %s", "read_block", error)
        return False
    
    return block


def blockheader_hash(block: 'dictionary') -> "False or String":
    """
    blockheader_hash: computes and returns SHA-256 message digest of a block header
    as a hexadecimal string. 
    Receives a block those blockheader hash is to be computed.
    Returns False if there is an error, otherwise returns a SHA-256 hexadecimal string.

    The block header consists of the following block fields:
    (1) version, (2)previous block hash, (3) merkle root 
    (4) timestamp, (5) difficulty_no, and (6) nonce.
    """
   
    try:
        hash = rcrypt.make_SHA256_hash(block['version'] + block['prevblockhash'] +
                                  block['merkle_root'] + str(block['timestamp']) + 
                                  str(block['difficulty_bits']) + str(block['nonce']))

    except Exception as error:
        logging.debug("Exception:%s: %s", "blockheader_hash", error)
        return False

    return hash


def validate_block(block: "dictionary") -> "bool":
    """
    validate_block: receives a block and verifies that all it's attributes have
    valid values. 
    Returns True if the block is valid and False otherwise.
    """
    try:
        if type(block) != dict:
            raise(ValueError("block type error"))

        # validate scalar block attributes
        if type(block["version"]) != str:
            raise(ValueError("block version type error"))

        if block["version"] != hconfig.conf["VERSION_NO"]: 
            raise(ValueError("block wrong version"))
      
        if type(block["timestamp"]) != int: 
            raise(ValueError("block timestamp type error"))

        if block["timestamp"] < 0: 
            raise(ValueError("block invalid timestamp"))
         
        if type(block["difficulty_bits"]) != int: 
            raise(ValueError("block difficulty_bits type error"))

        if block["difficulty_bits"] <= 0: 
            raise(ValueError("block difficulty_bits <= 0"))

        if type(block["nonce"]) != int: 
            raise(ValueError("block nonce type error"))

        if block["nonce"] != hconfig.conf["NONCE"]: 
            raise(ValueError("block nonce is invalid"))

        if type(block["height"]) != int:
            raise(ValueError("block height type error"))

        if block["height"] < 0:
            raise(ValueError("block height < 0"))

        if len(blockchain) == 0 and block["height"] != 0:
            raise(ValueError("genesis block invalid height"))     

        if len(blockchain) > 0:
            if block["height"] != blockchain[-1]["height"] + 1:
                raise(ValueError("block height is not in order"))     

        # The length of the block must be less than the maximum block size that
        # specified in the config module.
        # json.dumps converts the block into a json format string.
        if len(json.dumps(block)) > hconfig.conf["MAX_BLOCK_SIZE"]:
            raise(ValueError("block length error"))

        # validate the previous block by comparing message digests.
        # the genesis block does not have a predecessor block

        if block["merkle_root"] != merkle_root(block["tx"], True):
            raise(ValueError("merkle roots do not match"))

        if block["height"] > 0:    
            if block["prevblockhash"] != blockheader_hash(blockchain[-1]):
                raise(ValueError("previous block header hash does not match"))
        else:
            if block["prevblockhash"] != "":
                raise(ValueError("genesis block has prevblockhash"))

        # genesis block does not have any input transactions
        if block["height"] == 0 and block["tx"][0]["vin"] !=[]:
            raise(ValueError("missing coinbase transaction"))

        # a block other than the genesis block must have at least
        # two transactions: the coinbase transaction and at least
        # one more transaction
        if block["height"] > 0 and len(block["tx"]) < 2:
            raise(ValueError("block only has one transaction"))

      
    except Exception as error:
        logging.error("exception: %s: %s", "validate_block",error)
        return False

    return True


def merkle_root(buffer: "List", start: "bool" = False) -> "bool or string":
    """
    merkle_tree: computes the merkle root for a list of transactions.
    Receives a list of transactions and a boolean flag to indicate whether 
    the function has been called for the first time or whether it is a
    recursive call from within the function.
    Returns the root of the merkle tree or False if there is an error.
    """
    try:
        # if start is False then we verify have a list of SHA-256 hashes
        if start == False:
            for value in buffer:
                if rcrypt.validate_SHA256_hash(value) == False: 
                    raise(ValueError("tx list SHA-256 validation failure"))
                buflen = len(buffer)     
                if buflen != 1 and len(buffer)%2 != 0:
                    buffer.append(buffer[-1])

        # make the merkle leaf nodes if we are entering the function 
        # for the first time 
        if start == True:
            tmp = buffer[:] 
            tmp = make_leaf_nodes(tmp)
            if tmp == False: return False
            buffer = tmp[:] 
              
        # if buffer has one element, we have the merkle root 
        if (len(buffer) == 1): 
            return buffer[0]     

        # construct the list of parent nodes from the child nodes
        index = 0
        parents = []

        while index < len(buffer):
            tmp = rcrypt.make_SHA256_hash(buffer[index] + buffer[index+1])
            parents.append(tmp)
            index += 2

        # recursively call merkle tree
        ret = merkle_root(parents, False)

    except Exception as error:
        logging.error("exception: %s: %s", "merkle_root",error)
        return False

    return ret


def make_leaf_nodes(tx_list: "list") -> "List or False":
    """
    make_leaf_nodes: makes the leaf nodes of a merkle tree.
    Receives a list of transactions. If the number of transactions is an
    odd number, appends the last transaction to the list again so that we 
    can make a balanced tree.
    Computes the hexadecimal string encoded SHA-256 message digest of each
    transaction and appends it to a leaf node list that is initially empty.
    Returns the leaf node list or False if there is an error
    """
    try:
        # cannot have an empty transaction list
        if (len(tx_list) == 0): raise(ValueError("tx list zero length"))

        # verify we have a list type
        if type(tx_list) is not list: raise(ValueError("tx is not a list type")) 

        # verify the type of each transaction is a dict
        for tx in tx_list:
            if type(tx) is not dict: raise(ValueError("tx is not a dict type"))
            
        # must have an even number of transactions    
        if len(tx_list) % 2 == 1 or len(tx_list) == 1:
            tx_list.append(tx_list[- 1] )

        # copy the transaction list
        trx_list = list(tx_list)  
        
        # convert each transaction into a JSON string
        tx = []

        for transaction in trx_list:
            tx.append(json.dumps(transaction)) 

        # make the leaf nodes
        sha256_list = [] 
    
        for transaction in tx:
            sha256_list.append(rcrypt.make_SHA256_hash(transaction))

    except Exception as err:
        logging.debug('make_leaf_nodes: exception: ' + str(err))
        return False


    return sha256_list


