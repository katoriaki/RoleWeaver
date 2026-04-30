import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from tool_runtime import ToolRuntime, ToolRuntimeError, ToolSpec


class ToolRuntimeTestCase(unittest.TestCase):
    def test_register_run_and_log_tool(self):
        with TemporaryDirectory() as temp_dir:
            runtime = ToolRuntime(Path(temp_dir))
            runtime.register(
                ToolSpec(
                    name="runtime.echo",
                    description="Echo input",
                    parameters={
                        "type": "object",
                        "required": ["text"],
                        "properties": {"text": {"type": "string"}},
                        "additionalProperties": False,
                    },
                ),
                lambda args, ctx: {"text": args["text"], "session_id": ctx.session_id},
            )

            record = runtime.run(
                "runtime.echo",
                {"text": "hello"},
                session_id="s1",
                actor="test",
            )

            self.assertEqual(record["status"], "completed")
            self.assertEqual(record["result"]["text"], "hello")
            self.assertEqual(runtime.recent_actions(1)[0]["id"], record["id"])

    def test_validation_rejects_missing_extra_and_wrong_type(self):
        with TemporaryDirectory() as temp_dir:
            runtime = ToolRuntime(Path(temp_dir))
            runtime.register(
                ToolSpec(
                    name="runtime.count",
                    description="Count",
                    parameters={
                        "type": "object",
                        "required": ["value"],
                        "properties": {"value": {"type": "integer"}},
                        "additionalProperties": False,
                    },
                ),
                lambda args, ctx: args,
            )

            with self.assertRaises(ToolRuntimeError):
                runtime.run("runtime.count", {})
            with self.assertRaises(ToolRuntimeError):
                runtime.run("runtime.count", {"value": "1"})
            with self.assertRaises(ToolRuntimeError):
                runtime.run("runtime.count", {"value": 1, "extra": True})


if __name__ == "__main__":
    unittest.main()
