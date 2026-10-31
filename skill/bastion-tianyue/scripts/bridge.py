#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""天玥堡垒机桥接器客户端，纯标准库实现。

用法：
    python bridge.py health
    python bridge.py port
    python bridge.py exec "uname -a" [--timeout 30]
    python bridge.py stream "dmesg | tail -n 5" [--timeout 300]
    python bridge.py input "y\n"

退出码：
    0  请求或远端命令成功
    1  远端命令失败或桥接器未连接
    2  桥接器不可达或 HTTP 错误
    3  本地参数错误（argparse）
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple


PORT_FILE_WIN = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "sshbridge"
    / "TianYueSSHBridge"
    / "active_port.txt"
)
PORT_FILE_POSIX = (
    Path.home() / ".sshbridge" / "tianyuesshbridge" / "active_port.txt"
)


def ensure_utf8_console() -> None:
    """把可重配置的 stdout/stderr 切换到 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def discover_port() -> Optional[str]:
    """读取桥接器实际监听地址。"""
    for candidate in (PORT_FILE_WIN, PORT_FILE_POSIX):
        try:
            if candidate.is_file():
                value = candidate.read_text(
                    encoding="utf-8", errors="replace"
                ).strip()
                if value:
                    return value
        except OSError:
            continue
    return None


def resolve_base(args: argparse.Namespace) -> Optional[str]:
    """返回不带协议前缀的 host:port。"""
    base = args.base or discover_port()
    if not base:
        return None
    return base.removeprefix("http://").removeprefix("https://").rstrip("/")


def http_json(
    url: str,
    payload: Optional[dict] = None,
    timeout: int = 30,
) -> Tuple[int, dict]:
    """发送 JSON 请求并返回 HTTP 状态码与响应对象。"""
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=max(timeout + 10, 15)
        ) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        body = {"raw": raw}
    return status, body


def fail(message: str, code: int = 2) -> int:
    print(json.dumps({"error": message}, ensure_ascii=False))
    return code


def missing_port() -> int:
    return fail(
        "端口文件不存在：请在天玥堡垒机控制台点击 SSH 资源，等待桥接器启动后再试。"
    )


def cmd_port(args: argparse.Namespace) -> int:
    base = resolve_base(args)
    if not base:
        return missing_port()
    print(base)
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    base = resolve_base(args)
    if not base:
        return missing_port()
    url = f"http://{base}/health"
    try:
        status, body = http_json(url, timeout=10)
    except urllib.error.URLError as exc:
        return fail(f"桥接器不可达 {url}: {exc}")
    print(json.dumps(body, ensure_ascii=False))
    return 0 if status < 400 and body.get("connected") is True else 1


def cmd_exec(args: argparse.Namespace) -> int:
    base = resolve_base(args)
    if not base:
        return missing_port()
    url = f"http://{base}/execute"
    try:
        status, body = http_json(
            url,
            {"command": args.command, "timeout": args.timeout},
            timeout=args.timeout,
        )
    except urllib.error.URLError as exc:
        return fail(f"桥接器不可达 {url}: {exc}")
    print(json.dumps(body, ensure_ascii=False))
    if status >= 400 or "error" in body:
        return 2
    return 0 if body.get("exit_code", -1) == 0 else 1


def _parse_sse_event(raw_event: bytes) -> Tuple[str, str]:
    event_type = ""
    data_lines = []
    text = raw_event.decode("utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
    return event_type, "\n".join(data_lines)


def cmd_stream(args: argparse.Namespace) -> int:
    base = resolve_base(args)
    if not base:
        return missing_port()
    url = f"http://{base}/stream?command={urllib.parse.quote(args.command)}"
    exit_code = -1
    try:
        with urllib.request.urlopen(url, timeout=args.timeout) as response:
            buffer = b""
            # HTTPResponse.read(n) waits for n bytes (or EOF), which would
            # buffer small SSE events such as an interactive "Password:"
            # prompt.  read1 returns as soon as any data is available.
            read_chunk = getattr(response, "read1", None) or response.read
            for chunk in iter(lambda: read_chunk(4096), b""):
                buffer += chunk
                while b"\n\n" in buffer:
                    raw_event, buffer = buffer.split(b"\n\n", 1)
                    event_type, data = _parse_sse_event(raw_event)
                    try:
                        payload = json.loads(data or "{}")
                    except json.JSONDecodeError:
                        payload = {"data": data}

                    if event_type in ("stdout", "stderr"):
                        content = str(payload.get("data", ""))
                        output = sys.stdout if event_type == "stdout" else sys.stderr
                        output.write(content)
                        output.flush()
                    elif event_type == "exit":
                        exit_code = int(payload.get("exit_code", -1))
                    elif event_type == "error":
                        print(f"\n[stream error] {data}", file=sys.stderr)
            return 0 if exit_code == 0 else 1
    except urllib.error.URLError as exc:
        return fail(f"桥接器不可达 {url}: {exc}")


def cmd_input(args: argparse.Namespace) -> int:
    base = resolve_base(args)
    if not base:
        return missing_port()
    url = f"http://{base}/input"
    try:
        status, body = http_json(url, {"data": args.data}, timeout=15)
    except urllib.error.URLError as exc:
        return fail(f"桥接器不可达 {url}: {exc}")
    print(json.dumps(body, ensure_ascii=False))
    return 0 if status < 400 and body.get("status") == "ok" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridge.py",
        description="天玥堡垒机桥接器客户端（自动发现本机端口）",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    port_parser = sub.add_parser("port", help="打印实际监听地址")
    port_parser.set_defaults(func=cmd_port)

    health_parser = sub.add_parser("health", help="健康检查")
    health_parser.set_defaults(func=cmd_health)

    exec_parser = sub.add_parser("exec", help="执行单条命令")
    exec_parser.add_argument("command", help="要执行的命令")
    exec_parser.add_argument("--timeout", type=int, default=30)
    exec_parser.set_defaults(func=cmd_exec)

    stream_parser = sub.add_parser("stream", help="流式执行命令")
    stream_parser.add_argument("command", help="要执行的命令")
    stream_parser.add_argument("--timeout", type=int, default=300)
    stream_parser.set_defaults(func=cmd_stream)

    input_parser = sub.add_parser("input", help="发送交互输入")
    input_parser.add_argument("data", help="要发送的数据")
    input_parser.set_defaults(func=cmd_input)

    for subparser in (
        port_parser,
        health_parser,
        exec_parser,
        stream_parser,
        input_parser,
    ):
        subparser.add_argument(
            "--base",
            default=None,
            help="桥接器地址，如 127.0.0.1:8765（默认自动发现）",
        )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    ensure_utf8_console()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
