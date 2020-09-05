"""
Implementation of the Helium chainstate key-value store. This store lets us
access information about transaction fragments through a transaction key.
"""
import hconfig
import rcrypt
import plyvel
import logging
import json
import pdb

"""
log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w", \
     format='%(asctime)s:%(levelname)s:%(message)s', level=logging.DEBUG)

# handle to the Helium Chainstate Database
hDB = None

def open_hchainstate(filepath: "string") -> "db handle or False":
    """
    opens the Helium Chainstate key-value store and returns a handle to
    it.The database will be created if it does not exist.  All of the
    directories in filepath must exist. 
    Returns a handle to the database or False
    """
    try: 
        global hDB
        hDB = plyvel.DB(filepath, create_if_missing=True)

    except Exception as err:
        logging.debug('open_hchainstate: exception: ' + str(err))
        return False

    return hDB


def close_hchainstate() -> "bool":
    """
    close the Helium Chainstate store
    Returns True if the database is closed, False otherwise
    """
    global hDB
    try: 
        hDB.close()
        if hDB.closed != True: return False

    except Exception as err:
        logging.debug('close_hchainstate: exception: ' + str(err))
        return False

    return True


def put_transaction(txkey: "string", tx_fragment: "dictionary") -> "bool":
    """
    creates a key-value pair in the Chainstate Database      
    Receives a transaction key and a transaction_fragment.
    The transaction key is: transactionid + "_" + str(vout_index)
 
    The tx_fragment parameter received is:
    {   
                 “pkhash”:                  <string>
                 “value”:                   <int
                 “spent”:                   <bool>
                 "tx_chain"                 <string>
    }

    Returns True if the key-value pair is created and False otherwise
    """
    try:
        # if transaction key already exists delete because
        # the transaction fragment is going to be updated
        encoded_key = str.encode(txkey)
        hDB.delete(encoded_key)
        
        keyvalue = json.dumps(tx_fragment)
        # save the txkey-fragment pair to the store 
        hDB.put(encoded_key, str.encode(keyvalue))

    except Exception as err:
        print(str(err))
        logging.debug('put_transaction: exception: ' + str(err))
        return False

    return True


def get_transaction(key: "string") -> "False or dictionary":
    """
    Receives a transaction key (transactionid + "_" + str(vout_index))
    for a transaction fragment
    returns False or the key value. The transaction fragment returned has
    form:
    {   
                 “pkhash”:                  <string>
                 “value”:                   <string>
                 “spent”:                   <string>
                 "tx_chain"                 <string>
    }
    """
    
    try:
        # get the transaction fragment corresponding to the transaction
        # key, return False if the key does not exist
        fragment = hDB.get(str.encode(key))
        if fragment == None:
            raise(ValueError("transaction fragment not found"))


        fragment = json.loads(fragment.decode())

    except Exception as err:
        logging.debug('get_transaction: exception: ' + str(err))
        return False

    return fragment


def transaction_update(trx: "transaction")-> "bool":
    """
        receives a transaction. Updates the chainstate database to
        reflect the transaction. Sets previous transaction fragments
        to indicate that they have been spent. Updates these fragments
        to indicate the transaction id of the consuming transaction.
        returns True or False if there is an error
    """  

    try:
        # collect all of the outputs of previous transactions and set them to spent
        # specify the transaction key consuming the previous transaction inputs
        for vin in trx["vin"]:
            # fetch a previous transaction fragment. It must exist
            prev_tx_key = vin["txid"] + "_" + str(vin["vout_index"])

            tx_fragment = get_transaction(prev_tx_key)
            if tx_fragment == False:
                print("vin fragment not found: " + prev_tx_key)
                raise(ValueError("transaction fragment not found"))

            # double spend error
            # should be detected prior to writing to the Chainstate
            if tx_fragment["spent"] == True: 
                print("fragment is double spend error: " + prev_tx_key)
                raise(ValueError("transaction fragment double spend error: " + prev_tx_key))

            # set the spent values to True in the previous transaction
            # fragment
            tx_fragment["spent"] = True

            # set the reference to the consuming transaction
            tx_fragment["tx_chain"] = trx["transactionid"] + "_" + str(vin["vout_index"]) 

            # save to HeliumDB
            ret = put_transaction(prev_tx_key, tx_fragment)
            if ret == False:
                raise(ValueError("failed to update spent tx fragment"))


        # put the fragments of the consuming transaction into the HeliumDB
        ctr = 0
        for vout in trx["vout"]:
            tx_fragment = {}
            txkey = trx["transactionid"] + "_" + str(ctr) 
            tx_fragment["pkhash"] = vout["ScriptPubKey"][2]
            tx_fragment["value"] = vout["value"] 
            tx_fragment["spent"] = False
            tx_fragment["tx_chain"] = ""

            if put_transaction(txkey, tx_fragment) == False:
                raise(ValueError("failed to insert consuming transaction fragment"))

            ctr += 1

    except Exception as err:
        print(str(err))
        logging.debug('transaction_update: exception: ' + str(err))
        return False
 
    return True


