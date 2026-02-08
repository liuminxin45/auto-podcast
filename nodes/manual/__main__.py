from protocol.node_runner import run_node_cli
from nodes.manual.node import run
from nodes.manual.config import ManualConfig

if __name__ == "__main__":
    run_node_cli("manual", run, ManualConfig)
