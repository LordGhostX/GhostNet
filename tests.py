import sys
import time
import runpy
import random
import multiprocessing
import requests
import networkx as nx
import matplotlib.pyplot as plt


# run a node instance on a given port
def run_node(port):
    # pass the intended port to the sys.argv
    original_argv = sys.argv.copy()
    sys.argv = [sys.argv[0], str(port)]
    
    # run the process
    runpy.run_path("node.py", run_name="__main__")
    
    # reset the sys.argv
    sys.argv = original_argv.copy()


# test functionality of node.py
def test_node():
    # spin up nodes on ports 6970 - 6974
    processes = dict()
    for port in range(6970, 6975):
        processes[port] = multiprocessing.Process(target=run_node, args=(port,))
        processes[port].start()
    time.sleep(5)
        
    # check all the nodes have zero connections
    URL = "http://127.0.0.1:"
    for port in range(6970, 6975):
        r = requests.get(URL + str(port) + "/nodes")
        assert len(r.json()) == 0
        
    # bootstrap some of the nodes
    r = requests.post(URL + "6970/bootstrap", json=[URL + str(6971), URL + str(6972), URL + str(6975)])
    assert sorted(r.json()[0]) == sorted(["http://127.0.0.1:6971", "http://127.0.0.1:6972"])
    assert r.json()[1] == ["http://127.0.0.1:6975"]
    requests.post(URL + "6972/bootstrap", json=[URL + str(6973)])
    requests.post(URL + "6973/bootstrap", json=[URL + str(6974)])
    
    # check the nodes have their intended connections
    assert len(requests.get(URL + "6970/nodes").json()) == 2
    assert len(requests.get(URL + "6971/nodes").json()) == 1
    assert len(requests.get(URL + "6972/nodes").json()) == 2
    assert len(requests.get(URL + "6973/nodes").json()) == 2
    assert len(requests.get(URL + "6974/nodes").json()) == 1
    
    # relay a message from node 6970; accepts any json strucutre
    test_message = {
        "message": "Hello, World!",
        "timestamp": 1234567890
    }
    r = requests.post(URL + "6970/relay", json=test_message)
    assert sorted(r.json()) == sorted(["http://127.0.0.1:6971", "http://127.0.0.1:6972"])
    
    # confirm it was relayed throughout the whole network by attempting again
    for port in range(6970, 6975):
        r = requests.post(URL + str(port) + "/relay", json=test_message)
        assert len(r.json()) == 0
        
    # test dropoff mechanism by killing node 6974 then relay 3 messages
    processes[6974].terminate()
    assert sorted(requests.get(URL + "6973/nodes").json()) == sorted(["http://127.0.0.1:6972", "http://127.0.0.1:6974"])
    requests.post(URL + "6970/relay", json={"msg": "test 1"})
    requests.post(URL + "6970/relay", json={"msg": "test 2"})
    requests.post(URL + "6970/relay", json={"msg": "test 3"})
    assert requests.get(URL + "6973/nodes").json() == ["http://127.0.0.1:6972"]
    
    # test the node sharing mechanism
    assert len(requests.get(URL + "6971/nodes").json()) == 1
    r = requests.get(URL + "6971/node-sharing")
    assert r.json()[0] == ["http://127.0.0.1:6972"]
    assert r.json()[1] == []
    assert len(requests.get(URL + "6971/nodes").json()) == 2


# runs a simulation of the network with 100 nodes and visualizes it
def test_network_simulation(number_of_nodes=100, starting_port=7001, visualize=False):
    full_port_range = range(starting_port, starting_port + number_of_nodes)
    for port in full_port_range:
        process = multiprocessing.Process(target=run_node, args=(port,))
        process.start()
    time.sleep(30)

    # let the first quarter of nodes bootstrap each other in a series
    # A -> B -> C -> D -> E, etc
    URL = "http://127.0.0.1:"
    quarter_port_range = range(starting_port, starting_port + (number_of_nodes // 4) - 1)
    for port in quarter_port_range:
        requests.post(f"{URL}{port}/bootstrap", json=[f"{URL}{port + 1}"])

    # select a sample of the network to run node sharing
    for port in random.sample(quarter_port_range, number_of_nodes // 5):
        requests.get(f"{URL}{port}/node-sharing")

    # let the remaining nodes pick a random node to bootstrap
    for port in range(starting_port + (number_of_nodes // 4), starting_port + number_of_nodes):
        requests.post(f"{URL}{port}/bootstrap", json=[f"{URL}{random.choice(quarter_port_range)}"])

    # relay a message to test the connectivity
    requests.post(f"{URL}{starting_port}/relay", json={"message": "Hello, World!"})

    # map out how each node connects to each other
    node_mapping = dict()
    for port in full_port_range:
        node_mapping[port] = requests.get(f"{URL}{port}/nodes").json()

    # visualize the mapping using an undirected graph
    if visualize:
        G = nx.Graph()
        for node, edges in node_mapping.items():
            for edge in edges:
                edge_port = int(edge.split(":")[2])
                if node < edge_port:
                    G.add_edge(node - starting_port + 1, edge_port - starting_port + 1)
        pos = nx.kamada_kawai_layout(G)
        nx.draw(G, pos, with_labels=True, node_color="lightblue", font_weight="bold", node_size=750, font_size=10)
        plt.show()


if __name__ == "__main__":
    test_node()
    test_network_simulation(100, visualize=True)