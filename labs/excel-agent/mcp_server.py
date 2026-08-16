from mcp.server.fastmcp import FastMCP

from excel_tool import get_pbc_mismatches


mcp = FastMCP("excel-agent", log_level="ERROR")
mcp.tool()(get_pbc_mismatches)


if __name__ == "__main__":
    mcp.run()
