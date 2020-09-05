from tornado import ioloop, web
from jsonrpcserver import method, async_dispatch as dispatch

@method
async def fibonacci(m, n):
     n = n+m
     x1 = 0
     x2 = 1
     while True:
          if x2 >= n: return {"method":"fibonacci", "result": x2, "error": "none"}
          tmp = x2
          x2 = x2 + x1
          x1 = tmp


class MainHandler(web.RequestHandler):
    async def post(self):
        request = self.request.body.decode()
        response = await dispatch(request)
        print(response)
        if response.wanted:
            self.write(str(response))


app = web.Application([(r"/", MainHandler)])

if __name__ == "__main__":
    app.listen(address="127.0.0.24", port="8081")
    ioloop.IOLoop.current().start()

