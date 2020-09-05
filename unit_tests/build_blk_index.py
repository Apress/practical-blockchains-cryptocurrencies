#########################################################################
# build_blk_index: rebuilds the blk_index database from the blockchain
#########################################################################
import blk_index
import pickle
import os.path
import pdb

def startup():
    """
    start/create the blk_index database
    """
    # start the blk_index Database
    ret = blk_index.open_blk_index("hblk_index")
    if ret == False: 
        print("error: failed to start blk_index database")
        return   
    else: print("blk_index Database running")
    return True

def stop():
    """
    stop the blk_index database
    """
    blk_index.close_blk_index()



def build_blk_index():
    '''
    build the blk_index database from the blockchain
    '''
    blockno = 0
    tx_count = 0

    try:
        while True:
            # test whether the block file exists
            block_file = "block" + "_" + str(blockno) + ".dat"
            if os.path.isfile(block_file)== False: break

            # load the block file into a dictionary object
            f = open(block_file, 'rb')
            block = pickle.load(f)

            # process the transactions in the block
            for trx in block["tx"]:
                ret = blk_index.put_index(trx["transactionid"], blockno)                
                tx_count += 1             
                if ret == False: 
                    raise(ValueError("failed to rebuild blk_index. block no: " \
                         + str(blockno))) 

            blockno += 1

    except Exception as err:
        print(str(err))
        return False

    print("transactions processed: " + str(tx_count))
    print("blocks processed: " +  str(blockno))

    return True 

# start the build_index build
print("start build blk_index")
ret = startup()
if ret == False: 
    print("failed to open blk_index")
    os._exit(-1)
build_blk_index()
print("blk_index rebuilt")
stop()

