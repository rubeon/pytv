#!/usr/bin/python
import ConfigParser
import transmissionrpc

# ini file for configuration options
config = ConfigParser.RawConfigParser()
config.read('pytv.ini')
# test the server

tc = transmissionrpc.Client(**dict(config.items('transmission')))

tc.list

