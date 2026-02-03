"""
LangGraph Studio Entry Point

用于 LangGraph Studio 的入口文件。
"""

from src.graphs.podcast_graph import create_podcast_graph

# 导出图供 LangGraph Studio 使用
graph = create_podcast_graph()

if __name__ == "__main__":
    print("LangGraph Studio Entry Point")
    print("Use LangGraph Studio to visualize and run this graph")
