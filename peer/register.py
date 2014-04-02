import socket
import json
import config
import os
import time
import send_command

def register(obj, data):
    while os.path.exists("nodes.lock"):
        time.sleep(0.1)
    open("nodes.lock",'w').close()
##    stuff = config.nodes.find("nodes", {"address":data['address']})
##    if stuff:
##        for x in stuff:
##            config.nodes.remove("nodes", x)
##            config.nodes.save()

    allnodes = config.nodes.find("nodes", "all")
    # do not import duplicates
    tmp = set()
    for i in allnodes:
        print i['ip']
        tmp.add(i['ip'])

    print "nodes:",tmp
    if data['ip'] not in tmp:
        config.nodes.insert("nodes", data)
        config.nodes.save()
    os.remove("nodes.lock")

def send():
##    data = config.wallet.find("data", "all")[0]
    send_command.send({"cmd":"register", "relay":config.relay, "public":"hello world", "port":config.port})
