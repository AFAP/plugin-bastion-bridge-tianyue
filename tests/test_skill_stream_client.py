"""技能客户端（skill/bastion-tianyue/scripts/bridge.py）流式读取测试。

验证 SSE 用 ``read1`` 逐段读取：小事件（如交互提示）必须立即显示，而不是
等 ``read(n)`` 攒满或连接结束才吐出来。
"""

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skill"
    / "bastion-tianyue"
    / "scripts"
    / "bridge.py"
)

_spec = importlib.util.spec_from_file_location("tianyue_skill_bridge", SCRIPT)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


def _event(name: str, payload: dict) -> bytes:
    return f"event: {name}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")


class _FakeResponse:
    """按 SSE 事件逐条返回的假响应；一旦用了 read() 就直接失败。"""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.read1_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read1(self, size):
        self.read1_calls += 1
        return self._chunks.pop(0) if self._chunks else b""

    def read(self, size):
        raise AssertionError("SSE 不能用 read()，它会把小事件攒到连接结束")


class StreamClientTests(unittest.TestCase):
    def _run(self, chunks, command="echo hi"):
        response = _FakeResponse(chunks)
        stdout, stderr = io.StringIO(), io.StringIO()
        args = SimpleNamespace(base="127.0.0.1:8765", command=command, timeout=5)
        with patch.object(bridge.urllib.request, "urlopen", return_value=response), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            code = bridge.cmd_stream(args)
        return code, stdout.getvalue(), stderr.getvalue(), response

    def test_stream_reads_events_incrementally(self):
        code, out, err, response = self._run(
            [
                _event("start", {"command": "echo hi", "connected": True}),
                _event("stdout", {"data": "hi\n"}),
                _event("exit", {"exit_code": 0}),
                _event("end", {}),
            ]
        )

        self.assertEqual(0, code)
        self.assertEqual("hi\n", out)
        self.assertEqual("", err)
        self.assertGreaterEqual(response.read1_calls, 4)

    def test_output_is_visible_before_the_stream_ends(self):
        stdout = io.StringIO()
        seen = {}

        class _ProbeResponse(_FakeResponse):
            def read1(self, size):
                # 第三次调用之前，前两个事件（start、stdout）已被处理。
                if self.read1_calls == 2:
                    seen["early"] = stdout.getvalue()
                return super().read1(size)

        response = _ProbeResponse(
            [
                _event("start", {"command": "sudo -S id", "connected": True}),
                _event("stdout", {"data": "Password: "}),
                _event("exit", {"exit_code": 1}),
            ]
        )
        args = SimpleNamespace(base="127.0.0.1:8765", command="sudo -S id", timeout=5)
        with patch.object(bridge.urllib.request, "urlopen", return_value=response), \
                redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            bridge.cmd_stream(args)

        self.assertEqual("Password: ", seen.get("early"), "提示必须立刻显示，不能等流结束")

    def test_stderr_events_go_to_stderr(self):
        code, out, err, _ = self._run(
            [
                _event("stderr", {"data": "boom\n"}),
                _event("exit", {"exit_code": 3}),
            ]
        )

        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertEqual("boom\n", err)


if __name__ == "__main__":
    unittest.main()
