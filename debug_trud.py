import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def raw_test():
    server = StdioServerParameters(command="python", args=["trud_mcp.py"])
    async with stdio_client(server) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_refset_by_id",
                {"refset_id": "999002401000000105"}
            )
            print(f"Type: {type(result)}")
            print(f"Length: {len(result)}")
            print(f"First item: {result[0] if result else 'EMPTY'}")

asyncio.run(raw_test())
