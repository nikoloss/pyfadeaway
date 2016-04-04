The PyFadeaway module
===
##Introduction
Pyfadeaway is a multi-task RPC module also easy to use.
You can build distributed application based on a good performance RPC 
framwork with minimal effort.</br>
Pyfadeaway是一个基于多线程的RPC 的模块，它非常小巧，易读，易用。
你可以轻而易举的使用它来构建高性能的rpc应用
##Installation
```
$> git clone https://github.com/nikoloss/pyfadeaway
$> cd pyfadeaway
$> sudo python setup.py install
```
##Quick Start
#### server
```python
# This is a server demo, it shows a simply way to export a function to the
# outside world by using a decorator, "export".
import time
from fadeaway.core import main
from fadeaway import server

rpc = server.RemoteSrv()

@rpc.export
class Demo(object):
    def hello(self, name):
        time.sleep(5)   # That will show how multi-threads work
        return "Hello, %s" % name

    def hi(self, name):
        return 'Hi, %s' % name

rpc.listen(9151)
main.IOLoop.instance().start()
```
####sync-client
```python
# Sync-Client
# The Client will work in a synchronous way

from fadeaway.client import ServerProxy
from fadeaway.client import Sync 


if __name__ == '__main__':
    ss = ServerProxy(Sync, 'localhost', 9151)
    h = ss.Demo()
    print h.hello('billy') # shall block
    print h.hello('rowland')
    print h.hi('lucy')
```
####async-client
```python
# Async-Client
# The Client will work in an asynchronous way which would not cause any 
# blocking calls which means you have to set callback function to every 
# remote function call
from fadeaway.client import ServerProxy
from fadeaway.client import Async

def callback(res, error=None):
    # Any raised exception will set to the parameter "error"
    print '[callback]', res

if __name__ == '__main__':
    ss = ServerProxy(Async, 'localhost', 9151)
    ss.deploy() # Start ioloop in another thread
    h = ss.Demo()
    h.hello('billy').then(callback, timeout=3) # set a callback, timeout 3 seconds
    h.hello('rowland').then(callback)
    h.hi('lucy').then(callback)
```
## About Log
Just add "fadeaway" logging handler, set it to DEBUG level. it would log all 
the information that every request or response carries.

## License
Due to benefit from zeromq, the PyFadeaway is licensed under the GNU Lesser
General Public License V3 plus, respect.

## Feedback
* mailto(rowland.lan@163.com) or (rowland.lancer@gmail.com)
* QQ(623135465)
* 知乎(https://www.zhihu.com/people/luo-ran-22)
