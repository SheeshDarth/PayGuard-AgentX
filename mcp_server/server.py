"""
MCP tool server for PayGuard-AgentX.

Exposes the ToolKit tools (src/agents/tools.py) as real MCP tools on the demo
laptop. The mcp package is imported lazily inside build_server(), so the repo
imports and tests run without it installed. Run this module directly to start
the server:  python mcp_server/server.py
"""


def build_server():
    from mcp.server.fastmcp import FastMCP
    from src.agents.tools import ToolKit

    kit = ToolKit()
    server = FastMCP("payguard-agentx")

    @server.tool()
    def dq_validate(kind: str, raw_json: str):
        return kit.dq_validate(kind, raw_json)

    @server.tool()
    def sql_query(query: str):
        return kit.sql_query(query)

    @server.tool()
    def graph_query(kind: str, supplier_id: str = ""):
        return kit.graph_query(kind, supplier_id=supplier_id)

    @server.tool()
    def doc_retrieve(text: str, k: int = 3):
        return kit.doc_retrieve(text, k)

    @server.tool()
    def case_recall(text: str, k: int = 3):
        return kit.case_recall(text, k)

    return server


if __name__ == "__main__":
    build_server().run()
