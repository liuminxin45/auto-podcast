from protocol.node_runner import run_node_cli
from nodes.source_selector.node import run
from nodes.source_selector.config import SourceSelectorConfig

if __name__ == "__main__":
    run_node_cli("source_selector", run, SourceSelectorConfig)
