"""
Unified Node Runner

Provides standard entry point for all nodes to eliminate code duplication.
"""

import sys
import json
from typing import Dict, Any, Callable, Type
from protocol.config_base import NodeConfigBase


def run_node_cli(
    node_name: str,
    run_func: Callable[[Dict[str, Any], Any], Dict[str, Any]],
    config_class: Type[NodeConfigBase]
) -> None:
    """
    Standard CLI entry point for nodes.
    
    Args:
        node_name: Node identifier for error messages
        run_func: The node's run() function
        config_class: The node's config class
    
    Reads JSON state from stdin, executes node, writes result to stdout.
    Exit code 0 on success, 1 on failure.
    """
    try:
        input_data = json.loads(sys.stdin.read())
        config_data = input_data.get("runtime_config", {}).get(node_name, {})
        config = config_class.from_dict(config_data) if config_data else config_class()
        
        result = run_func(input_data, config)
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)
        
    except json.JSONDecodeError as e:
        error_output = {
            "errors": [{
                "node": node_name,
                "message": f"Invalid JSON input: {str(e)}",
                "detail": str(e)
            }]
        }
        print(json.dumps(error_output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
        
    except Exception as e:
        error_output = {
            "errors": [{
                "node": node_name,
                "message": str(e),
                "detail": str(e)
            }]
        }
        print(json.dumps(error_output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
