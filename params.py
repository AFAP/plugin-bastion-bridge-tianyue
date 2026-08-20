"""
Command-line parameter parsing for TianYue SSH Bridge.

The 天玥运维安全网关 (V6.0) invokes the configured external tool with a command
line that is effectively a SecureCRT-style argument string.  This module
normalizes several observed invocation styles into the canonical
``ConnectionParams`` dataclass and returns any unrecognised tokens for
diagnostic purposes.

Supported input styles:

* H3C / SecureCRT placeholder style::

      /SSH2 /L %USER% /P %PASSWORD% %HOST%:%PORT%

* GNU-style key/value options::

      --host x --port y --user z --password p

* SSH URL::

      ssh://user:pass@host:port

* Raw positional ``user@host:port``.

Any unknown or malformed input is logged and never allowed to crash the tool.
"""

import argparse
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from connection import ConnectionParams
from logger import get_logger

logger = get_logger("params")


#: Flags whose following token should be redacted from logs.
_PASSWORD_FLAGS = {
    "/p", "/password", "/pass",
    "--password", "--passwd", "--pass",
}


#: Mapping from common flag aliases to canonical long options.  This is used
#: when rewriting SecureCRT-style slash flags into a form argparse can consume.
#: Note: ``/S`` is intentionally NOT mapped to --host; it is a SecureCRT
#: session/display name used by 天玥.
_FLAG_ALIASES = {
    "/l": "--username",
    "/L": "--username",
    "/u": "--username",
    "/U": "--username",
    "/user": "--username",
    "/p": "--password",
    "/P": "--password",
    "/pass": "--password",
    "/password": "--password",
    "/h": "--host",
    "/H": "--host",
    "/host": "--host",
    "/port": "--port",
}


#: Regex to extract ``user@host:port`` with optional password and port.
_USER_HOST_PORT_RE = re.compile(
    r"^(?:(?P<user>[^:@]+)(?::(?P<pass>[^@]*))?@)?"
    r"(?P<host>[^:\\s]+)"
    r"(?::(?P<port>\d+))?$"
)


def _rewrite_slash_flags(argv: List[str]) -> List[str]:
    """Convert ``/L value`` style flags into ``--option value`` style."""
    rewritten: List[str] = []
    iterator = iter(argv)
    for token in iterator:
        canonical = _FLAG_ALIASES.get(token)
        if canonical:
            rewritten.append(canonical)
            try:
                rewritten.append(next(iterator))
            except StopIteration:
                logger.warning("Flag %s has no associated value; ignoring.", token)
                continue
        elif token.lower().startswith("/ssh"):
            # /SSH, /SSH2, /SSH1 -> protocol hint.
            proto = token.lower().replace("/ssh", "") or "2"
            rewritten.append("--protocol")
            rewritten.append(f"ssh{proto}")
        elif token.lower().startswith("/telnet"):
            rewritten.append("--protocol")
            rewritten.append("telnet")
        else:
            rewritten.append(token)
    return rewritten


def _extract_host_port(token: str) -> Tuple[str, int]:
    """Parse ``host:port`` and return a (host, port) tuple.

    Defaults to port 22 when no port is present.
    """
    if ":" in token:
        host_part, port_part = token.rsplit(":", 1)
        try:
            port = int(port_part)
        except ValueError:
            logger.warning(
                "Could not parse port from %r; defaulting to 22.", token
            )
            port = 22
            host_part = token
        # IPv6 literals can be wrapped in brackets; keep them intact.
        return host_part.strip("[]"), port
    return token, 22


def _parse_ssh_url(url: str) -> Dict[str, Any]:
    """Parse an ``ssh://user:pass@host:port`` URL into a raw dictionary."""
    if not url.startswith("ssh://"):
        url = "ssh://" + url
    parsed = urllib.parse.urlparse(url)

    result: Dict[str, Any] = {"protocol": "ssh2"}
    if parsed.hostname:
        result["host"] = parsed.hostname.strip("[]")
    if parsed.port:
        result["port"] = parsed.port
    if parsed.username:
        result["username"] = parsed.username
    if parsed.password is not None:
        result["password"] = parsed.password
    return result


def _parse_positional(token: str) -> Dict[str, Any]:
    """Parse ``user@host:port`` or ``host:port`` style positional argument."""
    match = _USER_HOST_PORT_RE.match(token)
    if not match:
        return {}

    groups = match.groupdict()
    host, port = _extract_host_port(f"{groups['host']}:{groups['port'] or ''}".rstrip(":"))

    result: Dict[str, Any] = {"host": host, "port": port}
    if groups.get("user"):
        result["username"] = groups["user"]
    if groups.get("pass") is not None:
        result["password"] = groups["pass"]
    return result


def _build_parser() -> argparse.ArgumentParser:
    """Internal argparse instance used for ``--key value`` style arguments."""
    parser = argparse.ArgumentParser(
        prog="TianYueSSHBridge",
        description="Bridge between TianYue bastion gateway and an SSH client.",
        add_help=False,
    )
    parser.add_argument("-h", "--host", "--hostname", dest="host")
    parser.add_argument("-p", "--port", dest="port", type=int)
    parser.add_argument("-l", "--username", "--user", dest="username")
    parser.add_argument("--password", "--passwd", "--pass", dest="password")
    parser.add_argument("--protocol", dest="protocol", default="ssh2")
    parser.add_argument("--key", "--key-path", dest="key_path")
    parser.add_argument("--bastion", "--bastion-host", "--jump", dest="bastion_host")
    return parser


def _mask_inline_secret(token: str) -> str:
    """Redact credentials embedded in an option or SSH-style URL."""
    option_match = re.match(
        r"(?i)^(--(?:password|passwd|pass)|/(?:password|pass|p))=(.*)$",
        token,
    )
    if option_match:
        return f"{option_match.group(1)}=***"

    credential_match = re.match(
        r"(?i)^(ssh://)?([^/@:\s]+):([^@\s]*)@(.+)$",
        token,
    )
    if credential_match:
        scheme = credential_match.group(1) or ""
        return f"{scheme}{credential_match.group(2)}:***@{credential_match.group(4)}"
    return token


def _mask_argv(argv: List[str]) -> List[str]:
    """Mask separate and inline credentials for safe logging."""
    masked: List[str] = []
    skip_next = False
    for token in argv:
        if skip_next:
            masked.append("***")
            skip_next = False
            continue
        if token.lower() in _PASSWORD_FLAGS:
            masked.append(token)
            skip_next = True
        else:
            masked.append(_mask_inline_secret(token))
    return masked


def _parse_securecrt_session(argv: List[str]) -> Optional[Dict[str, Any]]:
    """Parse the SecureCRT session-style invocation used by 天玥.

    Observed format::

        /S <session_display_name> <host> /L <username>
        /PASSWORD <password> /P <port> /F <securecrt_config_dir>

    In this mode the ``/S`` value is a display/session name (e.g.
    ``example(SSH)@203.0.113.10``) and the real SSH target is the bare
    positional argument that follows (commonly ``127.0.0.1`` because the
    gateway establishes a local tunnel).  ``/P`` is the dynamic port in this
    context, while ``/PASSWORD`` carries the credential.

    Returns:
        A dictionary with ``host``, ``port``, ``username``, ``password``,
        ``protocol`` and ``extra`` keys, or ``None`` if this format is not
        detected.
    """
    if "/S" not in argv and "/s" not in argv:
        return None

    result: Dict[str, Any] = {
        "host": None,
        "port": 22,
        "username": None,
        "password": None,
        "protocol": "ssh2",
        "key_path": None,
        "bastion_host": None,
        "extra": {},
    }
    has_password_flag = any(t.lower() == "/password" for t in argv)

    iterator = iter(argv)
    for token in iterator:
        lower = token.lower()
        try:
            if lower == "/s":
                result["extra"]["session_name"] = next(iterator)
            elif lower == "/l":
                result["username"] = next(iterator)
            elif lower == "/password":
                result["password"] = next(iterator)
            elif lower == "/p":
                value = next(iterator)
                if has_password_flag:
                    # In 天玥 mode /P is the dynamic port when /PASSWORD exists.
                    try:
                        result["port"] = int(value)
                    except ValueError:
                        logger.warning("/P value %r is not a valid port; treating as password", value)
                        result["password"] = value
                else:
                    # Legacy/H3C mode: /P is the password.
                    result["password"] = value
            elif lower == "/f":
                result["extra"]["securecrt_config_dir"] = next(iterator)
            elif lower.startswith("/ssh"):
                proto = lower.replace("/ssh", "") or "2"
                result["protocol"] = f"ssh{proto}"
            elif lower.startswith("/telnet"):
                result["protocol"] = "telnet"
            elif not token.startswith("/") and result["host"] is None:
                # First bare positional token after /S is the real target host.
                result["host"] = token
            elif not token.startswith("/"):
                # Additional bare positional tokens; keep for diagnostics.
                result["extra"]["positional"] = result["extra"].get("positional", "") + " " + token
        except StopIteration:
            logger.warning("Flag %s has no associated value; ignoring.", token)
            continue

    if result["host"] is None:
        return None
    return result


def parse_args(argv: List[str]) -> Tuple[ConnectionParams, Dict[str, Any]]:
    """Parse the argument list passed by 天玥 into ``ConnectionParams``.

    Args:
        argv: The raw argument list (usually ``sys.argv[1:]``).

    Returns:
        A tuple of ``(connection_params, raw_diagnostics)``.  The second item
        contains the original argument list plus any intermediate parsing
        artefacts so integration issues can be diagnosed from the log file.
    """
    diagnostics: Dict[str, Any] = {
        "raw_argv": argv,
        "rewritten_argv": None,
        "parser_namespace": None,
        "positional_candidates": [],
        "url_candidates": [],
        "errors": [],
    }

    # Defensive copy and strip obvious placeholders like empty strings.
    cleaned = [str(token) for token in argv if token is not None and str(token) != ""]
    logger.info("Parsing argv: %s", _mask_argv(cleaned))

    # Phase 0: detect 天玥 SecureCRT session-style invocation.
    session_data = _parse_securecrt_session(cleaned)
    if session_data is not None:
        logger.info("Detected 天玥 SecureCRT session-style arguments")
        diagnostics["parser_namespace"] = session_data
        diagnostics["rewritten_argv"] = cleaned
        params = ConnectionParams(
            host=session_data["host"],
            port=session_data["port"],
            username=session_data["username"] or "",
            password=session_data["password"],
            protocol=session_data["protocol"],
            key_path=session_data["key_path"],
            bastion_host=session_data["bastion_host"],
            extra=session_data["extra"],
        )
        diagnostics["final_params"] = params.to_dict()
        diagnostics["valid"] = params.is_valid()
        return params, diagnostics

    # Phase 1: try slash-flag rewriting (H3C/SecureCRT style).
    rewritten = _rewrite_slash_flags(cleaned)
    diagnostics["rewritten_argv"] = rewritten
    logger.debug("Rewritten argv: %s", _mask_argv(rewritten))

    # Phase 2: argparse on the rewritten list.
    parser = _build_parser()
    namespace, unknown = parser.parse_known_args(rewritten)
    diagnostics["parser_namespace"] = vars(namespace)
    if unknown:
        logger.info("Unknown tokens after flag parsing: %s", _mask_argv(unknown))

    # Start with whatever argparse discovered.
    raw: Dict[str, Any] = {
        "host": namespace.host,
        "port": namespace.port,
        "username": namespace.username,
        "password": namespace.password,
        "protocol": namespace.protocol or "ssh2",
        "key_path": namespace.key_path,
        "bastion_host": namespace.bastion_host,
    }

    # If --host was passed as "host:port", split it so we don't end up with
    # a malformed hostname like "127.0.0.1:2222" and a default port 22.
    if raw.get("host") and ":" in raw["host"]:
        host_part, port_part = raw["host"].rsplit(":", 1)
        try:
            raw["host"] = host_part.strip("[]")
            raw["port"] = int(port_part)
        except ValueError:
            logger.warning(
                "Could not split host:port from --host value %r; keeping as-is.",
                raw["host"],
            )

    # Phase 3: scan unknown/leftover tokens for URLs or positional strings.
    for token in unknown:
        stripped = token.strip()
        if not stripped:
            continue

        # URL-style input.
        if stripped.startswith("ssh://") or re.match(
            r"^(?:[^:@]+(?::[^@]*)?@)?[^:/\s]+:\d+$", stripped
        ):
            try:
                url_data = _parse_ssh_url(stripped)
                diagnostics["url_candidates"].append({"token": stripped, "parsed": url_data})
                raw.update(url_data)
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to parse URL candidate %r: %s",
                    _mask_inline_secret(stripped),
                    exc,
                )
                diagnostics["errors"].append(f"URL parse error: {exc}")

        # Positional user@host:port input.
        if "@" in stripped or (":" in stripped and not stripped.startswith("-")):
            try:
                pos_data = _parse_positional(stripped)
                diagnostics["positional_candidates"].append(
                    {"token": stripped, "parsed": pos_data}
                )
                if pos_data:
                    raw.update(pos_data)
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to parse positional candidate %r: %s",
                    _mask_inline_secret(stripped),
                    exc,
                )
                diagnostics["errors"].append(f"Positional parse error: {exc}")

    # Phase 4: if argparse found nothing useful, the whole argv might be a
    # single positional string (e.g. "user@host:port" or "host:port").
    if not raw.get("host") and len(cleaned) == 1:
        try:
            pos_data = _parse_positional(cleaned[0])
            diagnostics["positional_candidates"].append(
                {"token": cleaned[0], "parsed": pos_data}
            )
            raw.update(pos_data)
        except Exception as exc:  # noqa: BLE001
            diagnostics["errors"].append(f"Single positional parse error: {exc}")

    # Phase 5: final normalization and validation.
    host = raw.get("host") or ""
    port = raw.get("port") or 22
    username = raw.get("username") or ""
    password = raw.get("password")
    protocol = str(raw.get("protocol") or "ssh2").lower()
    key_path = raw.get("key_path")
    bastion_host = raw.get("bastion_host")

    # Move anything else we could not map into ``extra`` so it is not lost.
    extra: Dict[str, str] = {}
    for token in unknown:
        stripped = token.strip()
        if stripped.startswith("--") and "=" in stripped:
            key, value = stripped.split("=", 1)
            extra[key.lstrip("-")] = value

    params = ConnectionParams(
        host=host,
        port=port,
        username=username,
        password=password,
        protocol=protocol,
        key_path=key_path,
        bastion_host=bastion_host,
        extra=extra,
    )

    diagnostics["final_params"] = params.to_dict()
    diagnostics["valid"] = params.is_valid()

    if params.is_valid():
        logger.info(
            "Parsed connection parameters: host=%s port=%s user=%s protocol=%s",
            params.host,
            params.port,
            params.username,
            params.protocol,
        )
    else:
        logger.warning(
            "Parsed parameters are incomplete. host=%r user=%r port=%r",
            params.host,
            params.username,
            params.port,
        )

    return params, diagnostics
