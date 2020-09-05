'''
netnode: implementation of a synchronous RPC-Client node that makes remote
procedure calls to RPC servers using the JSON RPC protocol version 2, and
a JSON-RPC server that responds to requests from RPC client nodes.
'''
import blk_index as blkindex
import hblockchain
import hchaindb
import hmining
import networknode
from   tornado import ioloop, web
from   jsonrpcserver import method, async_dispatch as dispatch
from   jsonrpcclient.clients.http_client import HTTPClient
import ipaddress
import threading
import json
import pdb
import logging
import os
import sys

logging.basicConfig(filename="debug.log",filemode="w",  \
format='server: %(asctime)s:%(levelname)s:%(message)s', level=logging.DEBUG)


##################################
# JSON-RPC Client
##################################

def hclient(remote_server, json_rpc):
     '''
     sends a synchronous request to a remote RPC server
     '''
     try:
          client = HTTPClient(remote_server)

          response = client.send(json_rpc)
          valstr = response.text
          val = json.loads(valstr)
          print("result: " + str(val["result"]))
          print("id:  " + str(val["id"]))
          return valstr

     except Exception as err:
          logging.debug("node_client: " + str(err))
          return '{"jsonrpc": "2.0", "result":"error", "id":"error"}'


#######################################
# JSON-RPC Server
#######################################

address_list = []

@method
async def receive_transaction(trx):
     """
     receives a transaction that is propagating on the Helium network 
     """
     try:
          with hmining.semaphore:
               ret = hmining.receive_transaction(trx)
               if ret == False: return "error: invalid transaction"
          return "ok"
     except Exception as err:
          return "error: " + err


@method
async def receive_block(block):
     """
     receives a block that is propagating on the Helium network 
     """
     try:
          ret = hmining.receive_block(block)
          if ret == False: return "error: invalid block"
          return "ok"
     except Exception as err:
          return "error: " + err


@method
async def get_block(height):
     """
     returns the block with the given height or an error if the block 
     does not exist
     """
     with hmining.semaphore:
          if len(hblockchain.blockchain) == 0:
               return ("error-empty blockchain")

          if height < 0 or height > hblockchain.blockchain[-1]["height"]:
               return "error-invalid block height"

     block = json.dumps(hblockchain.blockchain[height])
     return block


@method
async def get_blockchain_height():
     """ 
     returns the height of the blockchain. Note that the first block has
     height 0 
     """
     with hmining.semaphore:
          if hblockchain.blockchain == []: return -1
          height = hblockchain.blockchain[-1]["height"]
    
     return height

@method
async def clear_blockchain():
     """ 
     clears the primary and secondary blockchains.
     """
     with hmining.semaphore:
          hblockchain.blockchain.clear()
          hblockchain.secondary_blockchain.clear()
     return "ok"


class MainHandler(web.RequestHandler):
    async def post(self):
        request = self.request.body.decode()
        logging.debug('decoded server request =  ' + str(request))
        response = await dispatch(request)
        print(response)
        self.write(str(response))


def startup():
     '''
     start node related systems
     '''
     try:
          # remove any locks
          os.system("rm -rf ../data/heliumdb/*")
          os.system("rm -rf ../data/hblk_index/*")
          # start the Chainstate Database
          ret = hchaindb.open_hchainstate("../data/heliumdb")
          if ret == False: return "error: failed to start Chainstate database"  
          else: print("Chainstate Database running")
          # start the LevelDB Database blk_index
          ret = blkindex.open_blk_index("../data/hblk_index")
          if ret == False: return "error: failed to start blk_index"  
          else: print("blkindex Database running")

     except Exception:      
          return "error: failed to start Chainstate database"  

     return True     


app = web.Application([(r"/", MainHandler)])


######################################################
# start the network interface for the server node on 
# the localhost loop: 127.0.0.19:8081
#####################################################
if __name__ == "__main__":
     app.listen(address="127.0.0.19", port="8081")
     logging.debug('server node is running')
     print("network node starting at 127.0.0.19:8081")
    
    ###############################
    # start this node
    ###############################

     if startup() != True:
          logging.debug('server node resource failure')
          print("stopping")
          sys.exit()

     logging.debug('server node is running')
     print('server node is running')

     ################################
     # start the event loop
     ################################ 
     ioloop.IOLoop.current().start()



