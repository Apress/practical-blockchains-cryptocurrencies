###############################################################################
# build_chainstate: Builds the chainstate database from the blockchain files.
###############################################################################
import hblockchain
import hchaindb
import pickle
import os.path
import pdb

def startup():
    """
    start the chainstate database
    """
    # start the Chainstate Database
    ret = hchaindb.open_hchainstate("heliumdb")
    if ret == False: 
        print("error: failed to start Chainstate database")
        return   
    else: print("Chainstate Database running")


def stop():
    """
    stop the chainstate database
    """
    hchaindb.close_hchainstate()


def build_chainstate():
    '''
    build the Chainstate database from the blockchain files
    '''
    blockno  = 0
    tx_count = 0

    try:
        while True:
            # test whether the block file exists
            block_file = "block" + "_" + str(blockno) + ".dat"
            if os.path.isfile(block_file)== False: break

            # load the block file into a dictionary object
            f = open(block_file, 'rb')
            block = pickle.load(f)

            # process the vout and vin arrays for each block transaction
            for trx in block["tx"]:
                ret = hchaindb.transaction_update(trx)  
                tx_count += 1             
                if ret == False: 
                    raise(ValueError("failed to rebuild chainstate. block no: " + str(blockno))) 

            blockno += 1

    except Exception as err:
        print(str(err))
        return False

    print("transactions processed: " + str(tx_count))
    print("blocks processed: " +  str(blockno))

    return True 

# start the chainstate build
print("start build chainstate")
startup()
build_chainstate()
print("chainstate rebuilt")
stop()
