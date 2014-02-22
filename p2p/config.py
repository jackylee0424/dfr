## need to specify you and your peer's ip to work


import landerdb
relay = 1
seeds = [{"ip":"192.168.1.122", "port":1217},{"ip":"192.168.1.121", "port":1217}]
version = "0.0.1"
host = "192.168.1.121" # for relay mode
port = 1217 # for relay mode
nodes = landerdb.Connect("nodes.db")
wallet = landerdb.Connect("wallet.db")
db = landerdb.Connect("db.db")
