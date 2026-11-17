import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from course_eval.agent import BashArguments


class ActionOutputChecks(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_tool_validates_action_without_executing_it(self):
        root = Path(tempfile.mkdtemp(prefix="mcp-protocol-", dir="work/codebuddy-quota-probe"))
        marker = root.resolve() / "must-not-exist"
        parameters = StdioServerParameters(command=sys.executable,
            args=["-m", "course_eval.action_output", json.dumps(BashArguments.model_json_schema())],
            env={"PYTHONPATH": str(Path.cwd()), "PATH": os.environ["PATH"]})
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertEqual([tool.name for tool in tools.tools], ["StructuredOutput"])
                self.assertEqual(tools.tools[0].inputSchema, BashArguments.model_json_schema())
                action = {"command": "touch " + str(marker)}
                result = await session.call_tool("StructuredOutput", action)
                self.assertFalse(result.isError)
                self.assertEqual(result.structuredContent, action)
                self.assertFalse(marker.exists())
                for invalid in ({"command": False}, {"command": "true", "extra": "forbidden"}):
                    rejected = await session.call_tool("StructuredOutput", invalid)
                    self.assertTrue(rejected.isError)
                self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
