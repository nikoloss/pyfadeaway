# coding: utf8
import os
from setuptools import setup


NAME = 'fadeaway'
AUTHOR = 'Steven Rowland'
AUTHOR_EMAIL = 'rowland.lan@163.com'
VERSION = "0.9b0"

f = open(os.path.join(os.path.dirname(__file__), 'readme.md'))
long_description = f.read()
f.close()

setup(
    name=NAME,
    version=VERSION,
    description='A Multi-tasking RPC Server apply google\'s json-rpc protocol 2.0',
    long_description=long_description,
    author=AUTHOR,
    install_requires = ['pyzmq'],
    author_email='rowland.lan@163.com',
    url='http://www.zhihu.com/people/luo-ran-22',
    license="LGPLV3",
    packages=['fadeaway', 'fadeaway.core', 'fadeaway.plugins'],
    package_data={
        'fadeaway': [
            "README.txt"
        ]
    },
    classifiers=[
        'Development Status :: 3 - Develop/Unstable',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ]
)
