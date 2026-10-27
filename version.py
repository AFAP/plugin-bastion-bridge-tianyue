"""Single source of truth for the bridge version and its bastion compatibility.

The bridge is launched by a bastion client (currently ``OMClientPlus``) that
passes SecureCRT-style session arguments; ``params.py`` implements that format.
A bridge build is therefore only known-good for the client version it was
actually verified against, so the version string carries both halves::

    1.0.0-om6.0.4.16603
    └─┬─┘└─────┬─────┘
   bridge   bastion client

The console banner, ``--version``, ``GET /health`` and the release tag all read
from this module, so a version bump or a re-target stays a one-file change.
"""

from __future__ import annotations

from typing import Any, Dict, List

#: Bridge version. Bump this whenever the bridge code or behaviour changes.
BRIDGE_VERSION = "1.0.0"

#: Bastion client this build was verified against.
BASTION_CLIENT_NAME = "OMClientPlus"
BASTION_CLIENT_VERSION = "6.0.4.16603"

#: Support statement shown on the console and repeated in the documentation.
BASTION_CLIENT_STATUS = "已验证稳定运行"

#: ``OMClientPlus 6.0.4.16603`` — for prose and console output.
BASTION_TARGET = f"{BASTION_CLIENT_NAME} {BASTION_CLIENT_VERSION}"

#: Full version marker, e.g. ``1.0.0-om6.0.4.16603``.
VERSION = f"{BRIDGE_VERSION}-om{BASTION_CLIENT_VERSION}"

# 备注（2026-10-27）：1.0.0 是长期平稳运行的基线版本 —— 参数解析、SSH 建连、
# 控制台展示与本地 API 均已按 OMClientPlus 6.0.4.16603 实测通过。
# 堡垒机客户端升级后，传入的参数形态可能变化，请新建版本号（例如
# 1.1.0-om<新客户端版本>）并重新验证，不要把本版本直接用于未验证的客户端。


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
