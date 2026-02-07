from protocol.node_runner import run_node_cli
from nodes.store.node import run
from nodes.store.config import StoreConfig

if __name__ == "__main__":
    run_node_cli("store", run, StoreConfig)
