# coding : utf8
import time
from fadeaway.core import server

rpc = server.RPCFrontend()

@rpc.export
class Demo(object):
    def hello(self, name):
        time.sleep(5)
        return "Hello, %s" % name

    def hi(self, name):
        return 'Hi, %s' % name


app = server.Application()
rpc.bind(9151)
app.register(rpc)
app.serv_forever()

