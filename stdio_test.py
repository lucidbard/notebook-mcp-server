import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command="python", args=["notebook_server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", sorted(t.name for t in tools.tools))

            res = await session.call_tool(
                "create_notebook", {"name": "smoke", "description": "stdio test"}
            )
            print("create_notebook ok:", not res.isError)

            res = await session.call_tool(
                "create_note",
                {"notebook": "smoke", "title": "Hello", "content": "stdio smoke note",
                 "tags": ["smoke"]},
            )
            print("create_note ok:", not res.isError)

            res = await session.call_tool("search_notes", {"query": "smoke", "tag": "smoke"})
            print("search ok:", not res.isError and "Hello" in res.content[0].text)

            res = await session.call_tool("read_note", {"note_id": 9999})
            print("missing note reported as isError:", res.isError)


asyncio.run(main())
