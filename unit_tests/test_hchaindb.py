"""
pytest unit tests for the hchaindb module 
"""
import hchaindb as chain
import rcrypt
import pytest
import json
import random
import secrets
import pdb
import os

def setup_module():
    assert bool(chain.open_hchainstate("heliumdb")) == True

def teardown_module():
    assert chain.close_hchainstate() == True
    if os.path.isfile("heliumdb"):
        os.remove("heliumdb")

###############################################
# Globals for a synthetic previous transaction
###############################################
prev_tx = None 
prev_tx_keys = []

def make_keys():
    """ 
    makes a private-public key pair for the synthetic
    previous transaction
    """
    prev_tx_keys.clear()
    key_pair = rcrypt.make_ecc_keys()
    prev_tx_keys.append([key_pair[0],key_pair[1]])
    return

# instantiate a key pair
make_keys()


def make_synthetic_previous_transaction(num_outputs):
    """
    makes synthetic previous transaction with randomized values
    we abstract away the inputs to the previous transaction.
    """
    transaction = {}
    transaction['version'] = 1
    transaction['transactionid'] = rcrypt.make_uuid() 
    transaction['locktime'] = 0
    transaction['vin']  = []
    transaction['vout'] = []

    def make_synthetic_vout():
        """
        make a synthetic vout object.
        returns a vout dictionary item
        """
        vout = {}
        vout['value'] = secrets.randbelow(1000000) + 1000  # helium cents
        
        tmp = []
        tmp.append('<DUP>')
        tmp.append('<HASH-160>')
        tmp.append(prev_tx_keys[0][1])
        tmp.append('<EQ-VERIFY>')
        tmp.append('<CHECK-SIG>')
        vout['ScriptPubKey'] = tmp
        return vout

    ctr = 0
    while ctr < num_outputs:
        ret = make_synthetic_vout()
        transaction['vout'].append(ret)

        ctr += 1
   
    return transaction


##################################
# Synthetic Transaction
##################################
def make_synthetic_transaction(prev_tx: "dictionary"):
    """
    makes a synthetic transaction with randomized values and that
    draws inputs from the previous transaction
    """

    transaction = {}
    transaction['version'] = 1
    transaction['transactionid'] = rcrypt.make_uuid() 
    transaction['locktime'] = 0
    transaction['vin'] = []
    transaction['vout'] = []

    num_outputs = max(1, secrets.randbelow(9))

    ctr = 0
    while ctr < num_outputs:
        vout = make_synthetic_vout()
        transaction['vout'].append(vout)
        ctr += 1

    # randomize how many of the previous transaction outputs
    # are consumed and the order in which they are consumed
    num_inputs = max(secrets.randbelow(len(prev_tx["vout"])), 1)
    indices = list(range(num_inputs))
    random.shuffle(indices)

    for ctr in indices:
        vin = make_synthetic_vin(prev_tx["transactionid"], ctr)
        transaction['vin'].append(vin)
        ctr += 1

    return transaction
   
#############################
# make a synthetic vin list
#############################

def make_synthetic_vin(prev_txid, prev_tx_vout_index):
    """
    make a vin object, receives a previous transaction id 
    and a index into the vout list
    returns the vin elemment
    """
    vin = {}
    vin['txid'] = prev_txid
    vin['vout_index'] = prev_tx_vout_index
    vin['ScriptSig'] = []
    vin['ScriptSig'].append(rcrypt.sign_message(prev_tx_keys[0][0], prev_tx_keys[0][1]))
    vin['ScriptSig'].append(prev_tx_keys[0][1])                                        
    return vin
 
#############################
# make a synthetic vout list
#############################

def make_synthetic_vout():
    """
    make a randomized vout element
    receives a public key
    returns the vout dict element
    """
    vout = {}
    vout['value'] = 1  # helium cents
        
    tmp = []
    tmp.append('<DUP>')
    tmp.append('<HASH-160>')
    tmp.append(secrets.token_hex(64))
    tmp.append('<EQ-VERIFY>')
    tmp.append('<CHECK-SIG>')

    vout['ScriptPubKey'] = tmp
    return vout


def make_transactionid():
    """
    makes a random transaction id
    """
    return rcrypt.make_uuid() 

def make_vout_index():
    """
    makes a random vout index
    """
    return random.randrange(10)

def make_pkhash():
    """
    creates a random pkhash value
    """
    id = rcrypt.make_uuid()
    return rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(id))

def make_value():
    """
    creates a random value
    """
    return random.randrange(1000000)

def make_spent():
    """
    creates a random spent boolean
    """
    sbool = random.randrange(10) % 2
    if sbool: return False
    return True


def test_put_keyvalue():
    """
    put a key-value pair into the chainstate database
    values have already been validated by validate_transaction
    """
    ctr = 0
    while ctr < 10:
        txid = make_transactionid()
        vout_index = make_vout_index()

        keyvalue = {
            "pkhash": make_pkhash(),
            "value":  make_value(),
            "spent":  make_spent(),
            "tx_chain": ""
        }

        assert chain.put_transaction(txid + "_" + str(vout_index), keyvalue) == True
        ctr += 1


def test_get_keyvalue():
    """
    get a key value for an existing key
    """
    txid = make_transactionid()
    vout_index = make_vout_index()

    keyvalue = {
        "pkhash": make_pkhash(),
        "value":  make_value(),
        "spent":  make_spent(),
        "tx_chain": ""
    }

    assert chain.put_transaction(txid + "_" + str(vout_index), keyvalue) == True

    key = txid + "_" + str(vout_index)
    ret = chain.get_transaction(key)
    assert ret != False
    assert type(ret) == dict



def test_get_for_fake_key():
    """
    attempt to get a key value for a fictitous key
    """
    txid = make_transactionid()
    vout_index = make_vout_index()

    keyvalue = {
        "pkhash": make_pkhash(),
        "value":  make_value(),
        "spent":  make_spent(),
        "tx_chain": ""
    }

    assert chain.put_transaction(txid + "_" + str(vout_index), keyvalue) == True

    key = "junk_" + str(vout_index)
    ret = chain.get_transaction(key)
    assert ret == False


def test_transaction_update():
    """
    updates the HeliumDB to reflect a transaction
    """
    # make a synthetic previous transaction
    num_prev_tx_outputs = secrets.randbelow(5) + 1
    previous_tx = make_synthetic_previous_transaction(num_prev_tx_outputs)
    
    #reflect this previous transaction in HeliumDB
    ctr = 0
    for vout in previous_tx["vout"]:
        #pdb.set_trace()
        fragment = {}
        fragment["pkhash"] = vout["ScriptPubKey"][2]
        fragment["spent"] = False 
        fragment["value"] = max(secrets.randbelow(1000000), 10)
        fragment["tx_chain"] = ""
      
        txid = previous_tx["transactionid"] + "_" + str(ctr)
        chain.put_transaction( txid, fragment)
        ctr += 1

    # make a transaction consuming some previous transaction outputs
    trx = make_synthetic_transaction(previous_tx)

    #update the Helium Chainstate
    assert chain.transaction_update(trx) == True


def test_double_spend():
    """ 
     tests transaction update when a previous transaction fragment
     has been spent
    """
    # make a synthetic previous transaction
    num_prev_tx_outputs = secrets.randbelow(5) + 1
    previous_tx = make_synthetic_previous_transaction(num_prev_tx_outputs)
    
    #reflect this previous transaction in HeliumDB
    ctr = 0
    for vout in previous_tx["vout"]:
        #pdb.set_trace()
        fragment = {}
        fragment["pkhash"] = vout["ScriptPubKey"][2]
        fragment["spent"] = True 
        fragment["value"] = max(secrets.randbelow(1000000), 10)
        fragment["tx_chain"] = ""

        txid = previous_tx["transactionid"] + "_" + str(ctr)
        chain.put_transaction( txid, fragment)
        ctr += 1

    # make a transaction consuming some previous transaction outputs
    trx = make_synthetic_transaction(previous_tx)

    #update the Helium Chainstate
    assert chain.transaction_update(trx) == 0
    

def test_previous_tx_non_existent():
    """ 
     tests transaction update when a previous transaction does
     not exist 
    """
    # make a synthetic previous transaction
    num_prev_tx_outputs = secrets.randbelow(5) + 1
    previous_tx = make_synthetic_previous_transaction(num_prev_tx_outputs)
    
    #reflect this previous transaction in HeliumDB
    ctr = 0
    for vout in previous_tx["vout"]:
        #pdb.set_trace()
        fragment = {}
        fragment["pkhash"] = vout["ScriptPubKey"][2]
        fragment["spent"] = False 
        fragment["value"] = max(secrets.randbelow(1000000), 10)
        fragment["tx_chain"] =  ""

        txid = previous_tx["transactionid"] + "_" + str(ctr)
        chain.put_transaction( txid, fragment)
        ctr += 1

    # make a transaction consuming some previous transaction outputs
    trx = make_synthetic_transaction(previous_tx)
    trx["vin"][0]["txid"] = "bad previous tx id"
    #update the Helium Chainstate
    assert chain.transaction_update(trx) == False


