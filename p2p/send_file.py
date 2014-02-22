import socket
import json
import config
import random

def send():
    nodes = config.nodes.find("nodes", {"relay":1}) # connect to relay nodes
    if not nodes:
        nodes = config.seeds
    for x in nodes:
        print x['ip']
        s = socket.socket()
        try:
            s.connect((x['ip'], 1218))
            f=open ("data//model//model.bin", "rb")
            l = f.read(1024)
            while (l):
                s.send(l)
                l = f.read(1024)
            s.close()
        except:
            s.close()

if __name__ == "__main__":
    send()
