'''
start a directory server on 127.0.0.69:8081
'''

import hmining
from tornado import ioloop, web
from jsonrpcserver import method, async_dispatch as dispatch
import ipaddress
import json
import threading
import pdb
import logging


# A Fake list of addresses for testing only
address_list = ["127.0.0.10:8081", "127.0.0.11:8081", "127.0.0.12:8081", "127.0.0.13:8081", \
            "127.0.0.14:8081", "127.0.0.15:8081", "127.0.0.16:8081", "127.0.0.17:8081", \
            "127.0.0.18:8081", "127.0.0.19:8081", "127.0.0.20:8081" ]

logging.basicConfig(filename="debug.log",filemode="w",  \
format='server: %(asctime)s:%(levelname)s:%(message)s', level=logging.DEBUG)

@method
async def get_address_list():
    hmining.semaphore.acquire()
    ret = address_list
    hmining.semaphore.release()
    return ret

@method
async def register_address(address: "string"):
    global address_list
    try:
        # validate IP address and port format: addr:port
        if address.find(":") == -1: return "error-invalid address"
        addr_list = address.split(":")
        addr_list[1]=addr_list[1].strip() 
        if len(addr_list[0]) == 0 or len(addr_list[1]) == 0: return "error-invalid address"
        if int(addr_list[1]) <= 0 or int(addr_list[1]) >= 65536: return "error-invalid address"

        _ = ipaddress.ip_address(addr_list[0])
        addr = addr_list[0] + ":" + addr_list[1]
        if addr not in address_list:
            hmining.semaphore.acquire()
            address_list.append(addr) 
            hmining.semaphore.release()
        return address

    except Exception as err:
        logging.debug('directory server::register address - ' + str(err))
        return "error-register address"


class MainHandler(web.RequestHandler):
    async def post(self):
        request = self.request.body.decode()
        logging.debug('decoded server request =  ' + str(request))
        response = await dispatch(request)
        print(response)
        self.write(str(response))


app = web.Application([(r"/", MainHandler)])

# start the network interface for a node on the local loop: 127.0.0.69:8081
if __name__ == "__main__":
    app.listen(address="127.0.0.69", port="8081")
    logging.debug('server running')
    print("directory server started at 127.0.0.69:8081")
    ioloop.IOLoop.current().start()

