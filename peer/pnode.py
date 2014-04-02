import config
import socket
import get_version
import get_nodes
import string
import register
import random
import thread
import json
import time

class pNode:
    def __init__(self):
        self.cmds = {
            "get_nodes":get_nodes.get_nodes,
            "get_version":get_version.get_version,
            "register":register.register,
            "get_nodes_count":get_nodes.count,
            }

    def firstrun(self):
        print "Getting nodes..."
        get_nodes.send(True)
        check = config.nodes.find("nodes", "all")
        if not check:
            ip = config.host
            config.nodes.insert("nodes", {"ip":ip, "relay":config.relay, "port":config.port})
            config.nodes.save()
        print "Registering..."
        register.send()

    def relay(self):
        get_nodes.send()
        register.send()
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((config.host, config.port))
        sock.listen(5)
        while True:
            obj, conn = sock.accept()
            thread.start_new_thread(self.handle, (obj, conn[0]))
    def handle(self, obj, ip):
        data = obj.recv(10240)
        if data:
            try:
                data = json.loads(data)
            except:
                obj.close()
                return
            else:
                if "cmd" in data:
                    if data['cmd'] in self.cmds:
                        data['ip'] = ip
                        print data
                        self.cmds[data['cmd']](obj, data)
                        obj.close()

    def normal(self):
        if not config.relay:
            register.send()
        while True:
            get_nodes.count_send()
            time.sleep(60)

def run():
    pn = pNode()
    check = config.nodes.find("nodes", "all")
    if not check:
        pn.firstrun()
    if config.relay:
        print "pNode started as a relay node."
        thread.start_new_thread(pn.normal, ())
        pn.relay()
    else:
        print "pNode started as a normal node."
        pn.normal()


if __name__ == "__main__":
    run()
