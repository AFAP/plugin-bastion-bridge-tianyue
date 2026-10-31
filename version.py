"""Single source of truth for the bridge version and its bastion compatibility.

The bridge is launched by a bastion client (currently ``OMClientPlus``) that
passes SecureCRT-style session arguments; ``params.py`` implements that format.
A bridge build is therefore only known-good for the client version it was
actually verified against, so the version string carries both halves::

    1.1.0-om6.0.7.0
    └─┬─┘└─────┬─────┘
   bridge   bastion client

The console banner, ``--version``, ``GET /health`` and the release tag all read
from this module, so a version bump or a re-target stays a one-file change.
"""

from __future__ import annotations

from typing import Any, Dict, List

#: Bridge version. Bump this whenever the bridge code or behaviour changes.
BRIDGE_VERSION = "1.1.0"

#: Bastion client this build was verified against.
BASTION_CLIENT_NAME = "OMClientPlus"
BASTION_CLIENT_VERSION = "6.0.7.0"

#: Support statement shown on the console and repeated in the documentation.
BASTION_CLIENT_STATUS = "已验证稳定运行"

#: ``OMClientPlus 6.0.7.0`` — for prose and console output.
BASTION_TARGET = f"{BASTION_CLIENT_NAME} {BASTION_CLIENT_VERSION}"

#: Full version marker, e.g. ``1.1.0-om6.0.7.0``.
VERSION = f"{BRIDGE_VERSION}-om{BASTION_CLIENT_VERSION}"

# 备注（2026-10-31）：1.1.0 = 危险操作兜底（command_guard.py）+ 执行通道修复——
# 空输出不再被当成登录横幅重跑、先读完输出再取退出码、shell 包装改「临时文件 + 单行
# 收尾」（read 不再误读内部行）、输入不再被命令锁阻塞、统一 sendall 防截断、标记跨包
# 完整解析；流式路径同样识别登录横幅但按总长度判定，且用增量解码器保证中文不跨包损坏。
# 客户端 6.0.7.0 传参形态未变，参数解析未改动。


def version_lines() -> List[str]:
    """Return the human-readable version block used by ``--version``."""
    return [
        f"桥接器版本   : {BRIDGE_VERSION}",
        f"完整版本号   : {VERSION}",
        f"适用堡垒机   : {BASTION_TARGET}（{BASTION_CLIENT_STATUS}）",
    ]


def health_fields() -> Dict[str, Any]:
    """Return the version fields added to the ``GET /health`` response."""
    return {
        "version": VERSION,
        "bridge_version": BRIDGE_VERSION,
        "bastion": {
            "client": BASTION_CLIENT_NAME,
            "version": BASTION_CLIENT_VERSION,
        },
    }
