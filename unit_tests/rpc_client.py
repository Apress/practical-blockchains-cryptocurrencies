from jsonrpcclient.clients.http_client import HTTPClient
import json

try:
     client = HTTPClient("http://127.0.0.24:8081")
     print("RPC client is ready")
  
     response = client.send('{"jsonrpc": "2.0", "method": "fibonacci", \
              "params":{ "m":100, "n":200}, "id":31 }')
     print("have json fibonacci response from server: " + response.text)

     val = response.text
     val = json.loads(val)
     print("result: " + str(val["result"]))
     print("id:  " + str(val["id"]))
     print("fibonacci number is: " + str(val["result"]["result"]))

except Exception as error:
     print(error)
