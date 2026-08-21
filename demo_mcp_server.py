import logfire
from mcp.server.fastmcp import FastMCP

logfire.configure(service_name="server")
logfire.instrument_mcp()

server = FastMCP("Pydantic AI Server")


@server.tool()
async def echo(msg: str) -> str:
    return msg


if __name__ == "__main__":
    server.run(transport="streamable-http")
