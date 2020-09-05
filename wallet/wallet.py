###########################################################################
# wallet.rb: a command-line wallet for Helium
###########################################################################
import hblockchain
import hchaindb
import rcrypt
import logging
import pdb
import pickle

logging.basicConfig(filename="debug.log",filemode="w", \
     format='%(asctime)s:%(levelname)s:%(message)s', level=logging.DEBUG)


# the state of the wallet
wallet_state = {
                  "keys": [],          # list of private-public key tuples
                  "received": [],      # values received by the wallet holder 
                  "spent": [],         # values transferred away by the wallet holder
                  "received_last_block_scanned": 0,
                  "spent_last_block_scanned": 0
                }


def create_keys():
    key_pair = rcrypt.make_ecc_keys()
    wallet_state["keys"].append(key_pair)


def initialize_wallet():
    wallet_state["received"] = []
    wallet_state["spent"] = []
    wallet_state["received_last_block_scanned"] = 0
    wallet_state["spent_last_block_scanned"] = 0


def value_received(blockno:"integer"= 0) -> "list" :
    """
    obtains all of the helium values received by the wallet-holder by examining
    transactions in the blockchain from and including blockno onwards.
    Updates the wallet state. 
    """
    hreceived = []
    tmp = {}

    try:
    # get values received from the blockchain
        for block in hblockchain.blockchain:
            if block["height"] < blockno: continue

            for transaction in block["tx"]:
                ctr = -1
                for vout in transaction["vout"]:
                    ctr += 1
                    for key_pair in wallet_state["keys"]:
                        if rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(key_pair[1])) \
                             == vout["ScriptPubKey"][2]: 
                            tmp["value"] = vout["value"]
                            tmp["blockno"] = block["height"]             
                            tmp["fragmentid"] = transaction["transactionid"] + "_" + str(ctr)
                            tmp["public_key"] = key_pair[1]         
                            hreceived.append(tmp)
                            break

        # update the wallet state
        last_block = hblockchain.blockchain[-1]                  
        if last_block["height"] > wallet_state["received_last_block_scanned"]:
            wallet_state["received_last_block_scanned"] = last_block["height"]

        for received in hreceived:
            wallet_state["received"].append(received)

    
    except Exception as err:
        print(str(err))
        logging.debug('value_received exception: ' + str(err))
        return False
        

    return


    
def value_spent(blockno:"integer"= 0):
    """
    obtains all of the helium values transferred by the wallet-holder by
    examining transactions in the blockchain from and including blockno.
    onwards. Updates the wallet state. 
    """
    hspent = []
    tvalue = {}

    try:
        # get values spent from  blockchain transactions
        for block in hblockchain.blockchain:
            if block["height"] < blockno: continue

            for transaction in block["tx"]:
                for vin in transaction["vin"]:
                    for key_pair in wallet_state["keys"]:
                        prevtxid =  vin["transactionid"] + "_" + str(vin["vout_index"])
                        fragment = hchaindb.get_transaction(prevtxid)

                        if rcrypt.make_RIPEMD160_hash(rcrypt.make_SHA256_hash(key_pair[1])) \
                             == fragment["pkhash"] : 
                            tvalue["value"] = vin["value"]
                            tvalue["blockno"] = block["height"]             
                            tvalue["fragmentid"] = vin["transactionid"] + "_" \
                                + str(vin["vout_index"])
                            tvalue["public_key"] = key_pair[1]         
                            hspent.append(tvalue)
                            break

        last_block = hblockchain.blockchain[-1]                  
        if last_block["height"] > wallet_state["spent_last_block_scanned"]:
            wallet_state["spent_last_block_scanned"] = last_block["height"]

        for spent in hspent:
            wallet_state["spent"].append(spent)

    except Exception as err:
        print(str(err))
        logging.debug('value_sent: exception: ' + str(err))
        return False

    return        


def save_wallet() -> "bool":
    """
    saves the wallet state to a file
    """
    try:
        f = open('wallet.dat', 'wb')         
        pickle.dump(wallet_state, f)
        f.close()
        return True

    except Exception as error:
        print(str(error))
        return False


def load_wallet() -> "bool":
    """
    loads the wallet state from a file
    """
    try:
        f = open('wallet.dat', 'rb')  
        global wallet_state       
        wallet_state = pickle.load(f)
        f.close()
        return True

    except Exception as error:
        print(str(error))
        return False

    