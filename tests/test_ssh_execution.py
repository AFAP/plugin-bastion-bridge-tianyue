"""执行通道测试：exec 读取循环、禁止换通道重跑、shell 退出码、配置百分号。"""

import json
import os
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path

import config
import ssh_client
from connection import ConnectionParams


class _ReadChannel:
    """模拟 Paramiko channel：按需给出 stdout，退出状态在数据读完后就绪。"""

    def __init__(self, data=b"", ready_after_read=True):
        self._data = data
        self.ready_after_read = ready_after_read
        self.exit_status_calls = 0
        self.closed = False

    def recv_ready(self):
        return bool(self._data)

    def recv_stderr_ready(self):
        return False

    def recv(self, size):
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk

    def recv_stderr(self, size):
        return b""

    def exit_status_ready(self):
        return self.ready_after_read and not self._data

    def recv_exit_status(self):
        self.exit_status_calls += 1
        return 0

    def close(self):
        self.closed = True


class _FakeTransport:
    def __init__(self, active=True):
        self._active = active

    def is_active(self):
        return self._active


def _bridge(prefer_shell=False):
    return ssh_client.SSHBridge(
        ConnectionParams(host="192.0.2.1", port=22, username="tester"),
        keepalive_enabled=False,
        prefer_shell=prefer_shell,
    )


def _exec_client(channel):
    """返回一个只实现 exec_command 的假 client（stdout/stderr 共用同一 channel）。"""

    class _Client:
        def __init__(self):
            self.calls = 0

        def exec_command(self, command, timeout=None):
            self.calls += 1
            stdin = type("In", (), {"channel": channel})()
            stdout = type("Out", (), {"channel": channel})()
            stderr = type("Err", (), {"read": lambda self: b""})()
            return stdin, stdout, stderr

    return _Client()


class ExecReadTests(unittest.TestCase):
    def test_output_is_read_before_waiting_for_exit_status(self):
        # 200 字节输出：旧实现先 recv_exit_status 会与远端互相等待。
        channel = _ReadChannel(data=b"x" * 200)
        out, err, code, error = ssh_client.SSHBridge._read_exec_output(channel, timeout=2)

        self.assertEqual("x" * 200, out)
        self.assertEqual("", err)
        self.assertEqual(0, code)
        self.assertIsNone(error)

    def test_timeout_returns_error_without_blocking(self):
        channel = _ReadChannel(data=b"", ready_after_read=False)
        started = time.monotonic()
        out, err, code, error = ssh_client.SSHBridge._read_exec_output(channel, timeout=1)
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 2.5)
        self.assertEqual(-1, code)
        self.assertIn("timed out", error)

    def test_endless_exec_output_still_hits_the_deadline(self):
        class _EndlessChannel:
            def recv_ready(self):
                return True

            def recv(self, size):
                time.sleep(0.001)
                return b"x" * min(size, 1024)

            def recv_stderr_ready(self):
                return False

            def recv_stderr(self, size):
                return b""

            def exit_status_ready(self):
                return False

            def recv_exit_status(self):
                return 0

            def close(self):
                pass

        started = time.monotonic()
        out, err, code, error = ssh_client.SSHBridge._read_exec_output(
            _EndlessChannel(), timeout=1
        )
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 2.5)
        self.assertEqual(-1, code)
        self.assertIn("timed out", error)

    def test_empty_output_is_not_a_login_banner(self):
        bridge = _bridge()
        self.assertFalse(bridge._looks_like_login_only(""))
        self.assertTrue(bridge._looks_like_login_only("Last login: today"))


class NoDuplicateExecutionTests(unittest.TestCase):
    """空输出 / 异常都不允许换通道重跑：命令可能已经执行过。"""

    def test_empty_output_is_not_retried_through_shell(self):
        channel = _ReadChannel(data=b"")
        bridge = _bridge()
        client = _exec_client(channel)
        bridge._client = client
        bridge._transport = _FakeTransport()

        shell_calls = []
        bridge._execute_via_shell = lambda command, timeout=30: shell_calls.append(command) or {
            "stdout": "wrong",
            "stderr": "",
            "exit_code": 0,
        }

        result = bridge.execute("systemctl restart nginx")

        self.assertEqual(1, client.calls)
        self.assertEqual([], shell_calls, "空输出不应触发 shell 重跑")
        self.assertEqual(0, result["exit_code"])
        self.assertEqual("", result["stdout"])

    def test_exec_banner_returns_error_without_rerunning_command(self):
        channel = _ReadChannel(data=b"Last login: today from 203.0.113.10")
        bridge = _bridge()
        bridge._client = _exec_client(channel)
        bridge._transport = _FakeTransport()

        shell_calls = []
        bridge._execute_via_shell = lambda command, timeout=30: shell_calls.append(command) or {
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
        }

        result = bridge.execute("id")

        self.assertEqual([], shell_calls, "横幅场景不应自动重跑命令")
        self.assertEqual(-1, result["exit_code"])
        self.assertIn("ssh_prefer_shell", result["error"])

    def test_exec_exception_is_not_retried_through_shell(self):
        class _BoomClient:
            def exec_command(self, command, timeout=None):
                raise RuntimeError("channel gone")

        bridge = _bridge()
        bridge._client = _BoomClient()
        bridge._transport = _FakeTransport()

        shell_calls = []
        bridge._execute_via_shell = lambda command, timeout=30: shell_calls.append(command) or {
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
        }

        result = bridge.execute("touch /tmp/bridge-probe")

        self.assertEqual([], shell_calls, "exec 异常不应自动重跑命令")
        self.assertEqual(-1, result["exit_code"])
        self.assertIn("channel gone", result["error"])

    def test_prefer_shell_uses_only_the_shell_channel(self):
        class _NoExecClient:
            def exec_command(self, command, timeout=None):
                raise AssertionError("exec_command must not be used when prefer_shell is set")

        bridge = _bridge(prefer_shell=True)
        bridge._client = _NoExecClient()
        bridge._transport = _FakeTransport()
        bridge._execute_via_shell = lambda command, timeout=30: {
            "stdout": "ok",
            "stderr": "",
            "exit_code": 0,
        }

        result = bridge.execute("uptime")

        self.assertEqual(0, result["exit_code"])
        self.assertEqual("ok", result["stdout"])


class ShellScriptTests(unittest.TestCase):
    """包装脚本不能把内部行留在终端输入队列里，也不能提前解析退出码。"""

    def _script(self, command="systemctl restart nginx"):
        return ssh_client.SSHBridge._shell_script(
            command,
            "---BRIDGE_END_abc---",
            "---BRIDGE_EXIT_abc---",
            "__BRIDGE_RC_abc",
            "__BRIDGE_TMP_abc",
            "BRIDGE_EOF_abc",
            "bridge_abc.sh",
        )

    def test_command_is_sourced_from_a_temp_file_not_the_terminal_queue(self):
        script = self._script("read answer")
        lines = script.splitlines()

        self.assertIn("cat >", lines[0] + lines[1], "命令要先进临时文件（heredoc）")
        self.assertEqual("read answer", lines[2], "命令在 heredoc 内，不在终端输入队列里")
        self.assertEqual("BRIDGE_EOF_abc", lines[3])

    def test_epilogue_is_a_single_line_that_saves_status_first(self):
        script = self._script()
        epilogue = script.splitlines()[4]

        self.assertIn('. "$__BRIDGE_TMP_abc"', epilogue)
        self.assertIn("__BRIDGE_RC_abc=$?", epilogue)
        self.assertLess(
            epilogue.index("__BRIDGE_RC_abc=$?"),
            epilogue.index("printf '\\001---BRIDGE_END_abc---"),
            "必须先保存 $? 再打印标记",
        )
        self.assertIn("printf '\\001---BRIDGE_EXIT_abc---:%s\\n'", epilogue)

    def test_marker_pattern_waits_for_the_whole_number(self):
        end_pattern, exit_pattern = ssh_client.SSHBridge._marker_patterns(
            "---BRIDGE_END_abc---", "---BRIDGE_EXIT_abc---"
        )
        partial = b"\x01---BRIDGE_END_abc---\r\n\x01---BRIDGE_EXIT_abc---:1"

        self.assertIsNotNone(end_pattern.search(partial))
        self.assertIsNone(exit_pattern.search(partial), "不完整的退出码不能提前匹配")
        self.assertIsNotNone(exit_pattern.search(partial + b"23\r\n"))
        self.assertEqual(b"123", exit_pattern.search(partial + b"23\r\n").group(1))


class _ScriptedShell:
    """假 PTY shell：收到包装脚本后按预设分片返回输出与标记。"""

    def __init__(self, output=b"hello\r\n", exit_code=123, split_exit=False):
        self.sent = []
        self.closed = False
        self._chunks = []  # (available_at, bytes)
        self._timeout = None
        self._queued = False
        self.exit_code = exit_code
        self.output = output
        self.split_exit = split_exit

    def gettimeout(self):
        return self._timeout

    def settimeout(self, value):
        self._timeout = value

    def get_pty(self, **kwargs):
        pass

    def invoke_shell(self):
        pass

    def close(self):
        self.closed = True

    def sendall(self, data):
        self.sent.append(data)
        text = data.decode("utf-8", errors="replace")
        if "---BRIDGE_END_" not in text or self._queued:
            return
        self._queued = True
        uid = re.search(r"---BRIDGE_END_([0-9a-f]+)---", text).group(1)
        end_marker = f"---BRIDGE_END_{uid}---".encode()
        exit_marker = f"---BRIDGE_EXIT_{uid}---".encode()
        now = time.monotonic()
        head = (
            self.output
            + b"\x01" + end_marker + b"\r\n"
            + b"\x01" + exit_marker + b":"
        )
        code = str(self.exit_code).encode()
        if self.split_exit:
            self._chunks = [(now, head + code[:1]), (now + 0.05, code[1:] + b"\r\n")]
        else:
            self._chunks = [(now, head + code + b"\r\n")]

    def send(self, data):  # pragma: no cover - send must not be used any more
        raise AssertionError("Channel.send must not be used (short writes)")

    def recv_ready(self):
        if not self._chunks:
            return False
        available_at, _ = self._chunks[0]
        return time.monotonic() >= available_at

    def recv(self, size):
        if not self._chunks:
            return b""
        _, data = self._chunks.pop(0)
        return data

    def recv_stderr_ready(self):
        return False

    def recv_stderr(self, size):
        return b""


class ShellExecutionTests(unittest.TestCase):
    """shell 通道：退出码完整解析、输入不被命令锁阻塞。"""

    def _bridge_with_shell(self, shell):
        bridge = _bridge(prefer_shell=True)
        bridge._client = object()
        bridge._transport = _FakeTransport()
        bridge._shell = shell
        bridge._open_shell = lambda: None
        return bridge

    def test_exit_marker_split_across_packets_is_parsed_completely(self):
        shell = _ScriptedShell(exit_code=123, split_exit=True)
        bridge = self._bridge_with_shell(shell)

        result = bridge.execute("false", timeout=3)

        self.assertEqual(0, result["stdout"].find("hello"))
        self.assertEqual(123, result["exit_code"], "退出码分两包到达时应等到完整数字")

    def test_shell_uses_sendall_for_the_script(self):
        shell = _ScriptedShell()
        bridge = self._bridge_with_shell(shell)

        bridge.execute("uptime", timeout=3)

        script_writes = [data for data in shell.sent if b"---BRIDGE_END_" in data]
        self.assertTrue(script_writes, "应下发包装脚本")

    def test_input_is_not_blocked_by_a_running_command(self):
        # 假 shell 永远不回标记：execute 会一直等到超时。
        shell = _ScriptedShell()
        shell.sendall = lambda data: shell.sent.append(data)  # 不回包
        bridge = self._bridge_with_shell(shell)

        worker = threading.Thread(target=lambda: bridge.execute("read answer", timeout=2), daemon=True)
        worker.start()
        time.sleep(0.4)
        self.assertTrue(worker.is_alive(), "命令应仍在执行")

        started = time.monotonic()
        sent = bridge.send_input("hello\n")
        elapsed = time.monotonic() - started

        self.assertTrue(sent)
        self.assertLess(elapsed, 1.0, "输入不应等待整条命令结束")
        self.assertTrue(any(b"hello\n" in data for data in shell.sent))
        worker.join(4)

    def test_send_input_reports_failure_on_short_or_failed_write(self):
        class _BrokenShell(_ScriptedShell):
            def sendall(self, data):
                raise OSError("write timeout")

        bridge = self._bridge_with_shell(_BrokenShell())
        self.assertFalse(bridge.send_input("y\n"))


class _ChunkChannel:
    """假 exec 通道：按分片返回 stdout/stderr，最后给出退出码。"""

    def __init__(self, stdout_chunks=(), stderr_chunks=(), exit_code=0):
        self._stdout = list(stdout_chunks)
        self._stderr = list(stderr_chunks)
        self._exit_code = exit_code
        self.executed = None
        self.closed = False

    def exec_command(self, command):
        self.executed = command

    def shutdown_write(self):
        pass

    def recv_ready(self):
        return bool(self._stdout)

    def recv(self, size):
        return self._stdout.pop(0) if self._stdout else b""

    def recv_stderr_ready(self):
        return bool(self._stderr)

    def recv_stderr(self, size):
        return self._stderr.pop(0) if self._stderr else b""

    def exit_status_ready(self):
        return not self._stdout and not self._stderr

    def recv_exit_status(self):
        return self._exit_code

    def close(self):
        self.closed = True


class _StreamTransport:
    def __init__(self, channel):
        self._channel = channel

    def is_active(self):
        return True

    def open_session(self):
        return self._channel


class _StreamClient:
    def __init__(self, transport):
        self._transport = transport

    def get_transport(self):
        return self._transport


def _stream_bridge(channel):
    transport = _StreamTransport(channel)
    bridge = _bridge()
    bridge._client = _StreamClient(transport)
    bridge._transport = transport
    return bridge


class StreamOutputTests(unittest.TestCase):
    """流式路径：登录横幅识别（含长度阈值）与跨包解码。"""

    def test_login_banner_is_not_reported_as_success(self):
        channel = _ChunkChannel(stdout_chunks=[b"Last login: today from 203.0.113.10\r\n"])
        chunks = list(_stream_bridge(channel).stream_execute("id"))

        self.assertEqual("Last login: today from 203.0.113.10\r\n", chunks[0]["data"])
        self.assertTrue(
            any(chunk["type"] == "stderr" and "login banner" in chunk["data"] for chunk in chunks),
            "应明确提示通道不可用",
        )
        self.assertEqual({"type": "exit", "exit_code": -1}, chunks[-1])

    def test_long_output_is_not_mistaken_for_a_banner(self):
        # 开头含 "Last login" 的长日志：整体远超 400 字符阈值，不能判成横幅。
        body = b"Last login: today\r\n" + b"2026-10-31 worker: ok\r\n" * 40
        self.assertGreater(len(body), 400)
        channel = _ChunkChannel(stdout_chunks=[body])

        chunks = list(_stream_bridge(channel).stream_execute("cat app.log"))
        stdout = "".join(chunk["data"] for chunk in chunks if chunk["type"] == "stdout")

        self.assertEqual(body.decode("utf-8"), stdout)
        self.assertFalse(any(chunk["type"] == "stderr" for chunk in chunks))
        self.assertEqual({"type": "exit", "exit_code": 0}, chunks[-1], "长日志不应被判为横幅")

    def test_chinese_split_across_packets_is_decoded_intact(self):
        text = "你好天玥"
        raw = text.encode("utf-8")
        # 在第一个字符中间切开，模拟 SSH 分包。
        channel = _ChunkChannel(stdout_chunks=[raw[:2], raw[2:]])
        chunks = list(_stream_bridge(channel).stream_execute("echo 你好天玥"))

        stdout = "".join(chunk["data"] for chunk in chunks if chunk["type"] == "stdout")
        self.assertEqual(text, stdout)
        self.assertEqual({"type": "exit", "exit_code": 0}, chunks[-1])

    def test_stderr_chinese_split_across_packets_is_decoded_intact(self):
        text = "失败天玥"
        raw = text.encode("utf-8")
        channel = _ChunkChannel(stderr_chunks=[raw[:1], raw[1:]], exit_code=1)
        chunks = list(_stream_bridge(channel).stream_execute("false"))

        stderr = "".join(chunk["data"] for chunk in chunks if chunk["type"] == "stderr")
        self.assertEqual(text, stderr)
        self.assertEqual({"type": "exit", "exit_code": 1}, chunks[-1])


class ConfigPercentTests(unittest.TestCase):
    def test_percent_in_config_does_not_break_loading(self):
        payload = {
            "dangerous_command_guard_patterns": [r"\b100%\b"],
            "keepalive_command": "printf '50%%\\n'",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = config.load_config(path)

        self.assertEqual([r"\b100%\b"], loaded["dangerous_command_guard_patterns"])
        self.assertEqual("printf '50%%\\n'", loaded["keepalive_command"])

    @unittest.skipUnless(os.name == "nt", "Windows style %VAR% expansion")
    def test_windows_style_variable_is_still_expanded(self):
        os.environ["BRIDGE_TEST_DIR"] = r"C:\bridge-test"
        try:
            expanded = config._expand_env(r"%BRIDGE_TEST_DIR%\logs")
        finally:
            del os.environ["BRIDGE_TEST_DIR"]

        self.assertEqual(r"C:\bridge-test\logs", expanded)


if __name__ == "__main__":
    unittest.main()
