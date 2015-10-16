# coding : utf8
import time
from fadeaway.core import server

rpc = server.RPCFrontend()


class Demo(object):

    @rpc.export
    def hello(self, name):
        time.sleep(5)
        return "Hello, %s" % name

    @rpc.export
    def hi(self, name):
        return 'Hi, %s' % name


app = server.Application()
rpc.bind(9151)
app.register(rpc)
app.serv_forever()

