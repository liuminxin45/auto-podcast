from protocol.node_runner import run_node_cli
from nodes.stages.node import run
from nodes.stages.config import StagesConfig

if __name__ == "__main__":
    run_node_cli("stages", run, StagesConfig)
