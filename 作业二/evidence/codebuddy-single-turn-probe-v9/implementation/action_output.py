import asyncio
import json
import sys

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool, ToolAnnotations


async def main():
    schema = json.loads(sys.argv[1])
    server = Server("course_output")

    @server.list_tools()
    async def list_tools():
        return [Tool(name="StructuredOutput",
            description="Return one structured action for the external, isolated benchmark environment. This tool does not execute the action.",
            inputSchema=schema, outputSchema=schema,
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                       idempotentHint=True, openWorldHint=False))]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name != "StructuredOutput":
            raise ValueError("Unknown action output tool: " + name)
        # SDK验证输入和输出schema；这里不执行模型提供的命令。
        return [TextContent(type="text", text="Action received.")], arguments

    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
