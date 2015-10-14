======================================================================
The PyFadeaway module
======================================================================

Introduction
---------------------
Pyfadeaway is a multi-task RPC/json-rpc2.0 module also easy to use.
You can build distributed application based on a good performance RPC 
framwork with minimal effort.


Quick Start
---------------------
from fadeaway.core import main
from fadeaway.core import ext

rpc_frontend = ext.RPCFrontend(port=9151)


class Hello(object):

    @rpc_frontend.export
    def hello(self, name, age):
        return {
            'desc': 'Hi!My name is %s, I am %s years old!' % (name, age)
        }

if __name__ == '__main__':
    print 'start...'
    app = main.Application()
    app.register_frontend(rpc_frontend)
    app.serv_forever()



License
---------------------
Due to benefit from zeromq the PyFadeaway is licensed under the GNU Lesser
General Public License V3 plus , respect.