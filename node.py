import sys
import json
import random
import hashlib
import requests
from flask import *


app = Flask(__name__)
CONNECTED_NODES = set()
PROTOCOL = "http://"
RELAYED_MESSAGES = dict()

# returns the node address for other nodes to connect to
def get_node_address() -> str:
    return PROTOCOL + request.host


# pings a node to check status, adds the request initiator to list of connected nodes
@app.route("/ping", methods=["POST"])
def ping_node() -> str:
    node = request.get_json()["node"]
    CONNECTED_NODES.add(node)
    return node


# bootstraps the node with a list of external nodes
# returns the list of node pings that were unsuccessful
@app.route("/bootstrap", methods=["POST"])
def bootstrap_node() -> list:
    nodes = request.get_json()["nodes"]
    failed_node_pings = list()
    for node in nodes:
        # if the ping to external node is successful, add it to the list of connected nodes
        try:
            r = requests.post(node + url_for("ping_node"), json={
                "node": get_node_address()
            })
            if r.status_code == 200:
                CONNECTED_NODES.add(node)
            else:
                failed_node_pings.append(node)
        except:
            failed_node_pings.append(node)
            
    return failed_node_pings


# returns the list of connected peers
@app.route("/nodes")
def get_connected_nodes() -> list:
    return list(CONNECTED_NODES)


# relay a received message to all connected nodes
@app.route("/relay", methods=["POST"])
def relay_message() -> list:
    message = request.get_json()
    message_hash = hashlib.sha256(json.dumps(message).encode()).hexdigest()
    if RELAYED_MESSAGES.get(message_hash):
        return list()
    else:
        # store the hash of the message so the node doesn't relay more than once
        RELAYED_MESSAGES[message_hash] = 1
        # pick a random set of nodes to relay the message to
        nodes = random.sample(list(CONNECTED_NODES), min(len(CONNECTED_NODES), 5))
        successful_node_relays = list()
        for node in nodes:
            r = requests.post(node + url_for("relay_message"), json=message)
            if r.status_code == 200:
                successful_node_relays.append(node)
        print(message)
        return successful_node_relays


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            NODE_PORT = int(sys.argv[1])
        else:
            NODE_PORT = 6969
    except:
        NODE_PORT = 6969
    app.run(host="0.0.0.0", debug=True, port=NODE_PORT)