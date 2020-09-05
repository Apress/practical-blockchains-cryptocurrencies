"""
The tx module defines the structure of Helium transactions and implements basic 
transaction operations.
"""
import hconfig
import hblockchain as hchain
import hchaindb
import json
import rcrypt
import secrets
import pdb
import logging

"""
log debugging messages to the file debug.log
"""
logging.basicConfig(filename="debug.log",filemode="w", format='%(asctime)s:%(levelname)s:%(message)s', 
    level=logging.DEBUG)

"""
Each transaction is modelled as a dictionary:

                 {
                     "transactionid": <string>
                     "version":   <integer>
                     "locktime":  <integer>
                     "vin":       <list<dictionary>>
                     "vout":      <list<<dictionary>>
                }

transactionid is the id of the the present transaction.
vin is a list of spendable inputs that are owned by the entity spending them. 
Each spendable input comes from the vout list of a previous transaction. 
Each vin is a list and each element is a dictionary object with the
following structure:

vin element:

            {
              "txid":              <string>
              "vout_index":        <int>
              "ScriptSig":        <list<string>>
            }
            

txid is the transaction id of a previous transaction. vout_index is an index
into this transaction's vout list.

vout is a list and each element in the vout list is a dictionary with the 
following structure:

vout element:
          {
             "value":  <integer>,
             "ScriptPubKey": <list<string>>

          }
        

"""


def create_transaction(transaction: 'dictionary', zero_inputs: 'boolean'=False) -> 'bool':
    """ 
    creates a transaction. Receives a transaction object and a predicate. 
    zero_inputs is True if the transacton is in the genesis block or if the transaction
    is a coinbase transaction, otherwise zero_inputs is False.
    Returns False if the transaction parameters are invalid. Otherwise returns True
    """
    if validate_transaction(transaction, zero_inputs) == False: return False
    return True


def validate_transaction(trans: "dictionary", zero_inputs: "boolean"=False) -> "bool":
    """
    verifies that a transaction has valid values.  
    receives a transaction and a predicate.
    zero_inputs is True if the transacton is in the genesis block or if the transaction
    is a coinbase transaction, otherwise zero_inputs is False.
.

    The following transaction validation tests are performed:
        (1)  The required attributes are present. 
        (2)  The locktime is greater than or equal to zero.
        (3)  The version number is greater than zero.
        (4)  The transaction ID has a valid format.
        (5)  The vin list have positive length.
        (6)  The vin list is not greater than the maximum allowable length.
        (7)  The vin list has valid format.
        (8)  The vout list has positive length.
        (9)  The vout list is not greater than the maximum allowable length.
        (8)  The vout list elements have valid format.
        (9)  The The vout list implements a p2pkhash script.
        (10) The reference to a previous transaction ID is valid.
        (11) The total value spent is less than or equal to the total spendable value.
        (12) The spent values are greater than zero.
        (13) The index values in the vin array reference valid elements in the
             vout array of the previous transaction.
        (14) The transaction inputs can be spent
        (15) The genesis block does not have any inputs
    """

    try:
        if type(trans) != dict:
            raise(ValueError("not dict type"))

        # Verify that required attributes are present
        if trans.get("transactionid") == None: return False
        if 'version' not in trans: return False
        if trans['locktime'] == None: return False
        if trans['vin'] == None: return False
        if trans['vout'] == None: return False
        
        # validate the format of the transaction id
        if rcrypt.validate_SHA256_hash(trans['transactionid']) == False: 
            raise(ValueError("not SHA-256 hash error"))

        # validate the transaction version and locktime values
        if trans['version'] != hconfig.conf["VERSION_NO"]: 
            raise(ValueError("improper version no"))

        if trans['locktime'] < 0:
            raise(ValueError("invalid locktime"))

        # genesis block or a coinbase transaction do not have any inputs
        if zero_inputs == True and len(trans["vin"]) > 0:
            raise(ValueError("genesis block cannot have inputs"))


        # validate the vin elements
        # there are no vin inputs for a genesis block transaction
        spendable_fragments = []

        for vin_element in trans['vin']:
            if validate_vin(vin_element) == False: return False
            tx_key = vin_element['txid'] + '_' + str(vin_element['vout_index'])

            spendable_fragment = prevtx_value(tx_key)
                
            if spendable_fragment == False:
                raise(ValueError("invalid spendable input for transaction"))
            else:    
                spendable_fragments.append(spendable_fragment)

        # validate the transaction's vout list
        if len(trans['vout']) > hconfig.conf['MAX_OUTPUTS'] or len(trans['vout']) <= 0:
            raise(ValueError("vout list length error"))

        for vout_element in trans['vout']:
            if validate_vout(vout_element) == False: return False          

        # validate the transaction fee
        if zero_inputs == False:
             if (transaction_fee(trans, spendable_fragments)) == False: return False

        # test that the transaction inputs are unlocked 
        ctr = 0
        for vin in trans['vin']:
            if unlock_transaction_fragment(vin, spendable_fragments[ctr]) == False:
                raise(ValueError("failed to unlock transaction"))
            ctr += 1    


    except Exception as err:
        logging.debug('validate_transaction: exception: ' + str(err))
        return False

    return True


def validate_vin(vin_element: 'dictionary') -> bool:
    """
    tests whether a vin element has valid values
    returns True if the vin is valid, False otherwise
    """
    try:
        if vin_element['vout_index'] < 0: return False    
        if len(vin_element['ScriptSig']) != 2: return False
        if len(vin_element['ScriptSig'][0]) == 0: return False
        if len(vin_element['ScriptSig'][1]) == 0: return False
        
        if rcrypt.validate_SHA256_hash(vin_element['txid']) == False:
            raise(ValueError("txid is invalid"))

    except Exception as err:
        
        print("validate_vin exception" + str(err))
        logging.debug('validate_vin: exception: ' + str(err))
        return False

    return True 


def validate_vout(vout_element: 'dictionary') -> bool:
    """
    tests whether a vout element has valid values
    returns True if the vout is valid, False otherwise
    """
    try:
        if vout_element['value'] <= 0: 
            raise(ValueError("value is <= 0"))

        # validate the p2pkhash script
        if len(vout_element["ScriptPubKey"]) != 5:
            raise(ValueError("ScriptPubKey length error"))
    
        if vout_element["ScriptPubKey"][0] != '<DUP>':
            raise(ValueError("ScriptPubKey <DUP> error"))
    
        if vout_element["ScriptPubKey"][1] != '<HASH-160>':
            raise(ValueError("ScriptPubKey <HASH-160> error"))

        if vout_element["ScriptPubKey"][3] != '<EQ-VERIFY>':
            raise(ValueError("ScriptPubKey <EQ-VERIFY> error"))
        
        if vout_element["ScriptPubKey"][4] != '<CHECK-SIG>':
            raise(ValueError("ScriptPubKey <CHECK-SIG> error"))

        if len(vout_element["ScriptPubKey"][2]) == 0: 
            raise(ValueError("ScriptPubKey RIPMD-160 hash error"))

    except Exception as err:
        print("validate_vout exception" + str(err))
        logging.debug('validate_vout: exception: ' + str(err))
        return False

    return True


def prevtx_value(txkey: "string") -> 'bool':
    """
    examines the chainstate database and returns the transaction fragment corresponding to txkey:
         { 
            "pkkhash":  <string>,
            "value":    <int>, 
            "spent":    <bool>, 
            "tx_chain": <string>
         }
    
    receives a transaction fragment key: 
              "previous txid" + "_" + str(prevtx_vout_index)

    Returns False if the transaction if does not exist, or if the
    value has  been spent or if value is not a positive integer 
    otherwise returns the previous transaction fragment data
    """
    try:
        fragment = hchaindb.get_transaction(txkey)
        if fragment == False:
            raise(ValueError("cannot get fragment from chainstate"))

        # return False if the value has been spent or if the value is
        # not positive
        
        if fragment["spent"] == True:
            raise(ValueError("cannot respend fragment in chainstate: " + txkey))

        if fragment["value"] <= 0:
            raise(ValueError("fragment value <= 0"))

    except Exception as err:
        logging.debug('prevtx_value: exception: ' + str(err))
        return False

    return fragment
 

def transaction_fee(trans: 'dictionary', value_list: 'list<dictionary>' ) -> 'integer or bool':
    """
    calculates the transaction fee for a transaction. 
    Receives a transaction and a list of chainstate transaction fragments
    Returns the transaction fee (in helium_cents) or False if there is an error.
    There is no transaction fee for the genesis block or coinbase transactions.
    """
    try:
        spendable_value = 0
        spent_value     = 0

        for val in value_list:
            spendable_value += val["value"]

        for vout in trans['vout']:
            spent_value += vout['value']

        if spendable_value <= 0:
            raise(ValueError("spendable value <= 0 "))

        if spent_value <= 0: 
            raise(ValueError("spent value <= 0 "))
                
        if spendable_value < spent_value:
            raise(ValueError("spendable value < spent value"))
            
    except Exception as err:
        logging.debug('transaction_fee: exception: ' + str(err))
        return False

    return spendable_value - spent_value 


def unlock_transaction_fragment(vinel: "dictionary", fragment: "dictionary") -> "boolean":
    """
    unlocks a previous transaction fragment using the p2pkhash script.
    Executes the script and returns False if the transaction is not unlocked
    Receives: the consuming vin and the previous transaction fragment consumed
    by the vin element.
    """
    try:
        execution_stack = [] 
        result_stack = []

        # make the execution stack for a p2pkhash script 
        # since we only have one type of script in Helium
        # we can use hard-coded values
        execution_stack.append('SIG')
        execution_stack.append('PUBKEY')
        execution_stack.append('<DUP>')
        execution_stack.append('<HASH_160>')
        execution_stack.append('HASH-160')
        execution_stack.append('<EQ-VERIFY>')
        execution_stack.append('<CHECK_SIG>')

        # Run the p2pkhash execution stack 
        result_stack.insert(0, vinel['ScriptSig'][0])    
        result_stack.insert(0, vinel['ScriptSig'][1])    
        result_stack.insert(0, vinel['ScriptSig'][1])    
        
        hash_160 = rcrypt.make_SHA256_hash(vinel['ScriptSig'][1])
        hash_160 = rcrypt.make_RIPEMD160_hash(hash_160)

        result_stack.insert(0, hash_160)    
        result_stack.insert(0, fragment["pkhash"])    
        
        # do the EQ_VERIFY operation
        tmp1 = result_stack.pop(0)
        tmp2 = result_stack.pop(0)
      
        # test for RIPEMD-160 hash match 
        if tmp1 != tmp2:
            raise(ValueError("public key match failure"))

        # test for a signature match
        ret = rcrypt.verify_signature(vinel['ScriptSig'][1], vinel['ScriptSig'][1], vinel['ScriptSig'][0])
        if ret == False:
            raise(ValueError("signature match failure"))
     
    except Exception as err:
        logging.debug('unlock_transaction_fragment: exception: ' + str(err))
        return False

    return True
