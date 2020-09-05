"""
test_tx.py: implements unit tests for the transactions module
"""
import rcrypt
import hconfig
import hblockchain as bchain 
import tx
import pytest
import pdb
import secrets
import random

previous_tx = None
prev_tx_keys = []
num_prev_tx_outputs = 0

##################################
# Synthetic Previous Transaction
##################################

def make_synthetic_previous_transaction(num_outputs):
    """
    makes synthetic previous transaction with randomized values
    we abstract away the inputs to the previous transaction.
    """
    transaction = {}
    transaction['version'] = 1
    transaction['transactionid'] = rcrypt.make_uuid() 
    transaction['locktime'] = 0
    transaction['vin'] = []
    transaction['vout'] = []

    def make_synthetic_vout():
        """
        make a synthetic vout object.
        returns a vout dictionary item
        """
        key_pair = rcrypt.make_ecc_keys()
        global prev_tx_keys
        prev_tx_keys.append([key_pair[0],key_pair[1]])
        vout = {}
        vout['value'] = secrets.randbelow(1000000) + 1000  # helium cents
        
        tmp = []
        tmp.append('<DUP>')
        tmp.append('<HASH-160>')
        tmp.append(key_pair[1])
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
def make_synthetic_transaction(num_outputs):
    """
    makes a synthetic transaction with randomized values
    """

    transaction = {}
    transaction['version'] = 1
    transaction['transactionid'] = rcrypt.make_uuid() 
    transaction['locktime'] = 0
    transaction['vin'] = []
    transaction['vout'] = []

    ctr = 0
    while ctr < num_outputs:
        vout = make_synthetic_vout()
        transaction['vout'].append(vout)
        ctr += 1

    # randomize how many of the previous transaction outputs
    # are consumed and the order in which they are consumed
    num_inputs = secrets.randbelow(num_prev_tx_outputs) + 1
    indices = list(range(num_inputs))
    random.shuffle(indices)

    for ctr in indices:
        vin = make_synthetic_vin(previous_tx["transactionid"], ctr)
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
 
    global prev_tx_keys

    vin['ScriptSig'].append(rcrypt.sign_message(prev_tx_keys[prev_tx_vout_index][0],
                                            prev_tx_keys[prev_tx_vout_index][1]))
    vin['ScriptSig'].append(prev_tx_keys[prev_tx_vout_index][1])                                        
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

#############################
# randomize access to a list
#############################

def randomize_list(lst: "list"):
    """
    randomly shuffles the indexes into a list
    returns the randomized index list 
    """
    ctr = len(lst)
    p = 0
    index = []
    while p < ctr: index.append(p);p += 1
    random.shuffle(index) 
    return index

########################################
# Make a synthetic previous transaction
########################################

num_prev_tx_outputs = secrets.randbelow(3) + 1
previous_tx = make_synthetic_previous_transaction(num_prev_tx_outputs)

"""
test the transactions
"""
def test_type_transaction():
    """
    test transaction type
    """
    assert tx.validate_transaction([]) == False


def test_missing_transactionid():
    """
    test missing transaction id
    """
    trns = make_synthetic_transaction(1)
    del trns["transactionid"]
    assert tx.validate_transaction(trns) == False


def test_bad_transactionid():
    """
    test transaction id with an invalid length
    """
    trns = make_synthetic_transaction(1)
    # replace the last char with an invalid char
    trns["transactionid"] = trns["transactionid"][:-1] + "z"
    assert tx.validate_transaction(trns) == False


def test_zero_version_number():
    """
    test zero version no
    """
    trns = make_synthetic_transaction(1)
    trns["version"] = 0
    assert tx.validate_transaction(trns) == False


def test_negative_locktime():
    """
    test for a negative locktime
    """
    trns = make_synthetic_transaction(1)
    trns["locktime"] = -1
    assert tx.validate_transaction(trns) == False


def test_invalid_vout_length():
    """
    test that the vout list length is not greater than
    the maximum allowed by the Helium config
    """
    trn = make_synthetic_transaction(11)
    assert tx.validate_transaction(trn) == False


def test_no_prev_tx_reference():
    """
    test that the transaction's vin element has a
    reference to a previous transaction.
    """
    txn = make_synthetic_transaction(1)
    indices = randomize_list(txn["vin"]) 
    
    for ctr in list(range(len(indices))):
        txn['vin'][indices[ctr]]['txid'] = ""
        assert tx.validate_transaction(txn) == False


def test_empty_scriptSig():
    """
    test that ScriptPubKey element is not empty
    """
    txn = make_synthetic_transaction(8)
    indices = randomize_list(txn['vin'])

    for ctr in list(range(len(indices))):
        txn['vin'][indices[ctr]]['ScriptSig'] = []
        vin = txn['vin'][indices[ctr]]
        assert tx.validate_vin(vin) == False


def test_scriptsig_length_error():
    """
    test if the ScriptSig list has invalid length
    """
    txn = make_synthetic_transaction(2)
    indices = randomize_list(txn['vin'])
    keys = rcrypt.make_ecc_keys()

    for ctr in list(range(len(indices))):
        txn["vin"][indices[ctr]]['ScriptSig'].append(keys[1])
        assert tx.validate_vin(txn['vin'][indices[ctr]]) == False


def test_empty_scriptSig_sig():
    """
    test that ScriptSig signature field is not empty
    """ 
    txn = make_synthetic_transaction(2)
    indices = randomize_list(txn['vin'])

    for ctr in list(range(len(indices))):
        txn['vin'][indices[ctr]]['ScriptSig'][0] = ''
        vin = txn['vin'][indices[ctr]]
        assert tx.validate_vin(vin) == False


def test_empty_scriptSig_pubkey():
    """
    test that ScriptSig public key field is not empty
    """
    txn = make_synthetic_transaction(2)
    indices = randomize_list(txn['vin'])

    for ctr in list(range(len(indices))):
        txn['vin'][indices[ctr]]['ScriptSig'][1] = ''
        assert tx.validate_transaction(txn) == False


def test_scriptpubkey_length_error():
    """
    test that ScriptPubKey list has a valid length
    """
    txn = make_synthetic_transaction(4)
    indices = randomize_list(txn['vout'])

    for ctr in list(range(len(indices))):
        element = txn['vout'][indices[ctr]]['ScriptPubKey'][1] 
        txn['vout'][indices[ctr]]['ScriptPubKey'].append(element)
        assert tx.validate_transaction(txn) == False


@pytest.mark.parametrize("index, value, ret", [
     (0, 'DUP', False),
     (0, '<DUP>', True),
     (1, '<HASH-160',False),
     (1, '<HASH-160<',False),
     (1, '<HASH-160>',True),
     (1, '<HASH160>',  False),
     (3, '<VERIFY>',  False),
     (3, '<EQ-VERIFY>',  True),
     (4, '<CHECKSIG>', False),
     (4, '<CHECK-SIG>', True),
])
def test_bad_scriptpubkey_script(monkeypatch, index, value, ret):
    """
    test if ScriptPubKey has an invalid element
    """
    monkeypatch.setattr(tx, "transaction_fee", 5)
    monkeypatch.setattr(tx, "unlock_transaction_fragment", True)

    txn = make_synthetic_transaction(7)
    indices = randomize_list(txn['vout'])

    txn['vout'][indices[0]]['ScriptPubKey'][index] = value 
    assert tx.validate_vout(txn['vout'][indices[0]]) == ret


def test_pubkeyhash():
    """
    test a public key hash in scriptpubkey for a 
    valid RIPEMD-160 format
    """
    txn = make_synthetic_transaction(5)

    indices = randomize_list(txn['vout'])

    for ctr in list(range(len(indices))):
        val = txn['vout'][indices[ctr]]['ScriptPubKey'][2]
        val = rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(val)) 
        assert rcrypt.validate_RIPEMD160_hash(val) == True
    

def test_invalid_txid():
    """
    test the format of a previous transaction
    """
    txn = make_synthetic_transaction(2)
    id = rcrypt.make_uuid()
    id = "j" + id[1:]

    indices = randomize_list(txn['vin'])

    ctr = secrets.randbelow(len(indices))
    txn['vin'][indices[ctr]]['txid'] = id
    assert tx.validate_transaction(txn) == False


def test_invalid_txid_length():
    """
    test a previous transaction id for length
    """
    txn = make_synthetic_transaction(2)
    id = rcrypt.make_uuid()
    id = "p" + id[0:]
    indices = randomize_list(txn['vin'])

    ctr = secrets.randbelow(len(indices))
    txn['vin'][indices[ctr]]['txid'] = id
    assert tx.validate_transaction(txn) == False


def test_bad_transaction_inputs(monkeypatch):
    """
    tests that the inputs received are valid.
    fails if the previous transaction does not exist,
    or previous value has been spent, or is negative  
    """
    monkeypatch.setattr(tx, 'prevtx_value', lambda x: False)
    assert tx.prevtx_value("stubbed function") == False


def test_transaction_inputs(monkeypatch):
    """
    tests that the inputs received are valid
    fails if the previous transaction does not exist,
    or previous value has been spent, or is negative  
    """
    txn = make_synthetic_transaction(2)
    monkeypatch.setattr(tx, 'prevtx_value', lambda x:
            [{
            "txid_vout": txn['vin'][0]['txid'] + '_' + str(txn['vin'][0]['vout_index']),
            "value": 210,
            "pkhash": previous_tx['vout'][0]['ScriptPubKey'][2],
            "block": 100,
            "spent": False 
        },
        
        {
            "txid_vout": txn['vin'][0]['txid'] + '_' + str(txn['vin'][0]['vout_index']),
            "value": 38,
            "pkhash": previous_tx['vout'][0]['ScriptPubKey'][2],
            "block": 29,
            "spent": False 
        }]
    )
    
    assert bool(tx.prevtx_value(txn)) == True


def test_zero_output_value(monkeypatch):
    """
    test a zero transaction output value 
    """
    txn = make_synthetic_transaction(4)
    
    indices = randomize_list(txn['vout'])
    ctr = secrets.randbelow(len(indices))

    monkeypatch.setitem(txn['vout'][indices[ctr]], 'value', 0 )
    assert tx.validate_transaction(txn) == False
    

def test_negative_output_value(monkeypatch):
    """
    test a negative transaction output value 
    """
    txn = make_synthetic_transaction(4)

    indices = randomize_list(txn['vout'])
    ctr = secrets.randbelow(len(indices))

    monkeypatch.setitem(txn['vout'][indices[ctr]], 'value', -456712)
    assert tx.validate_transaction(txn) == False
  

def test_transaction_fee(monkeypatch):
    """
    test various transaction fees
    """
    txn = make_synthetic_transaction(2)
    txn['vout'][0]["value"] = 10 
    txn['vout'][1]["value"] = 203 

    value_list = [{
        "txid_vout": txn['vin'][0]['txid'] + '_' + str(txn['vin'][0]['vout_index']),
        "value": 210,
        "pkhash": previous_tx['vout'][0]['ScriptPubKey'][2],
        "block": 100,
        "spent": False 
    },
    
    {
        "txid_vout": txn['vin'][0]['txid'] + '_' + str(txn['vin'][0]['vout_index']),
        "value": 38,
        "pkhash": previous_tx['vout'][0]['ScriptPubKey'][2],
        "block": 29,
        "spent": False 
    }
    ]

    assert tx.transaction_fee(txn, value_list) != False


def test_negative_transaction_fee(monkeypatch):
    """
    test a negative transaction fee
    """
    txn = make_synthetic_transaction(3)
    monkeypatch.setitem(txn['vout'][0], 'value', 10000)

    value_list = [{
        "txid_vout": txn['vin'][0]['txid'] + '_' + str(txn['vin'][0]['vout_index']),
        "value": 210,
        "pkhash": previous_tx['vout'][0]['ScriptPubKey'][2],
        "block": 100,
        "spent": False 
    },
    
    {
        "txid_vout": txn['vin'][0]['txid'] + '_' + str(txn['vin'][0]['vout_index']),
        "value": 38,
        "pkhash": previous_tx['vout'][0]['ScriptPubKey'][2],
        "block": 29,
        "spent": False 
    }
    ]

    assert tx.transaction_fee(txn, value_list) == False


def test_unlock_bad_hash(monkeypatch):
    """ 
    test unlocking previous transaction output with
    bad RIPEMD-160 hash p2pkhash value
    """
    global prev_tx_keys

    prev_tx_keys.clear()
    txn1 = make_synthetic_previous_transaction(4)
    txn2 = make_synthetic_transaction(2)

    # make a transaction fragment where the first vin element
    # of txn2 consumes the value of the first vout element of txn1

    # synthetic consuming vin element in tx2
    vin = {}
    vin['txid'] = txn1["transactionid"]
    vin['vout_index'] = 0
    vin['ScriptSig'] = {}

    signature = rcrypt.sign_message(prev_tx_keys[1][0], prev_tx_keys[1][1])
    pubkey = prev_tx_keys[1][1]  
    sig = []
    sig.append(signature)
    sig.append(pubkey + "corrupted")
    vin['ScriptSig'] = sig
                                        
    # use the wrong public key hash in txn2
    key_pair = rcrypt.make_ecc_keys()
    ripemd_hash = rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(key_pair[1])) 

    fragment = {
        "value": 210,
        "pkhash": ripemd_hash,
        "spent": False,
        "tx_chain": txn2["transactionid"] + "_" + "0",
        "checksum":   rcrypt.make_SHA256_hash(txn1["transactionid"])
    }
    
    assert tx.unlock_transaction_fragment(vin, fragment) == False


def test_unlock_bad_signature(monkeypatch):
    """ 
    test unlocking a transaction with a bad signature
    """
    global prev_tx_keys

    prev_tx_keys.clear()
    txn1 = make_synthetic_previous_transaction(4)
    txn2 = make_synthetic_transaction(2)

    # make a transaction fragment where the first vin element
    # of txn2 consumes the value of the first vout element of txn1

    # synthetic consuming vin element in tx2
    vin = {}
    vin['txid'] = txn1["transactionid"]
    vin['vout_index'] = 0
    vin['ScriptSig'] = {}

    # use wrong private key to sign 
    key_pair = rcrypt.make_ecc_keys()

    signature = rcrypt.sign_message(key_pair[0], prev_tx_keys[1][1])
    pubkey = prev_tx_keys[1][1]  
    sig = []
    sig.append(signature)
    sig.append(pubkey + "corrupted")
    vin['ScriptSig'] = sig
                                        
    # public key hash in txn2
    ripemd_hash = rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(prev_tx_keys[1][1])) 

    fragment = {
        "value": 210,
        "pkhash": ripemd_hash,
        "spent": False,
        "tx_chain": txn2["transactionid"] + "_" + "0",
        "checksum":   rcrypt.make_SHA256_hash(txn1["transactionid"])
    }
    
    assert tx.unlock_transaction_fragment(vin, fragment) == False



def test_unlock_bad_pubkey():
    """ 
    test unlocking a transaction with a bad public key
    """
    global prev_tx_keys

    prev_tx_keys.clear()
    txn1 = make_synthetic_previous_transaction(4)
    txn2 = make_synthetic_transaction(2)

    # make a transaction fragment where the first vin element
    # of txn2 consumes the value of the first vout element of txn1

    # synthetic consuming vin element in tx2
    vin = {}
    vin['txid'] = txn1["transactionid"]
    vin['vout_index'] = 0
    vin['ScriptSig'] = {}

    signature = rcrypt.sign_message(prev_tx_keys[1][0], prev_tx_keys[1][1])
    pubkey = prev_tx_keys[1][1]  
    sig = []
    sig.append(signature)
    sig.append(pubkey + "corrupted")
    vin['ScriptSig'] = sig
                                        
    # public key hash in txn2
    ripemd_hash = rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(prev_tx_keys[1][1])) 

    fragment = {
        "value": 210,
        "pkhash": ripemd_hash,
        "spent": False,
        "tx_chain": txn2["transactionid"] + "_" + "0",
        "checksum":   rcrypt.make_SHA256_hash(txn1["transactionid"])
    }
    
    assert tx.unlock_transaction_fragment(vin, fragment) == False


def test_unlock_good():
    """ 
    test unlocking a transaction with a good private-public key pair
    """
    global prev_tx_keys

    prev_tx_keys.clear()
    txn1 = make_synthetic_previous_transaction(4)
    txn2 = make_synthetic_transaction(2)

    # make a transaction fragment where the first vin element
    # of txn2 consumes the value of the first vout element of txn1

    # synthetic consuming vin element in tx2
    vin = {}
    vin['txid'] = txn1["transactionid"]
    vin['vout_index'] = 0
    vin['ScriptSig'] = {}

    signature = rcrypt.sign_message(prev_tx_keys[1][0], prev_tx_keys[1][1])
    pubkey = prev_tx_keys[1][1]  
    sig = []
    sig.append(signature)
    sig.append(pubkey)
    vin['ScriptSig'] = sig
                                        
    # public key hash in txn2
    ripemd_hash = rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(prev_tx_keys[1][1])) 

    fragment = {
        "value": 210,
        "pkhash": ripemd_hash,
        "spent": False,
        "tx_chain": txn2["transactionid"] + "_" + "0",
        "checksum":   rcrypt.make_SHA256_hash(txn1["transactionid"])
    }
    
    assert tx.unlock_transaction_fragment(vin, fragment) == True



