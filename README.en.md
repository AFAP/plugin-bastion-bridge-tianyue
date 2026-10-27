# TianYue Bastion SSH Bridge · 天玥堡垒机 SSH 桥接器

<div align="center">
  <a href="README.md">中文</a> · <b>English</b>
</div>

> **Let AI operate servers behind a TianYue bastion through a local RESTful API.**
> Turn desktop-only SSH operations into HTTP, SSE, and Socket.IO interfaces.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/AFAP/plugin-bastion-bridge-tianyue)](https://github.com/AFAP/plugin-bastion-bridge-tianyue/releases)
[![Build](https://github.com/AFAP/plugin-bastion-bridge-tianyue/actions/workflows/release.yml/badge.svg)](https://github.com/AFAP/plugin-bastion-bridge-tianyue/actions/workflows/release.yml)

| Audience | Integration |
|---|---|
| **DeepSeek Harness users** | Install the skill in one line, then explicitly invoke `/bastion-tianyue` when server access is needed |
| **Other AI agents or scripts** | Call the local REST, SSE, or Socket.IO API directly, independent of language or framework |

## 0. Version and bastion compatibility

| Item | Current value |
|---|---|
| Bridge version | `1.0.0` |
| Full version marker | `1.0.0-om6.0.4.16603` |
| Supported bastion client | `OMClientPlus 6.0.4.16603` |
| Status | ✅ Baseline build, running stable in production |

The bridge depends on the SecureCRT-style session arguments produced by the bastion client, and
those can change between client versions. Every build therefore records the client version it was
**actually verified against**, using the version scheme `<bridge version>-om<client version>`.

Confirm the running version in any of these ways:

- the startup banner in the console (bridge version plus supported bastion version);
- `tianyue_ssh_bridge.exe --version`;
- the `version`, `bridge_version`, and `bastion` fields returned by `GET /health`.

After upgrading the bastion client, use a new version number (for example
`1.1.0-om<new client version>`) and re-verify. Do not point the current build at an unverified client.

## 1. Problem solved

TianYue Operations Security Gateway can launch local terminals such as SecureCRT for SSH resources,
but those interfaces are designed for people. AI cannot reliably send commands and receive structured results.
This project provides a single-file bridge that can be configured as TianYue's local SSH tool:

1. Receive SecureCRT-style connection arguments from TianYue;
2. Parse the host, port, account, and temporary credential, then connect through Paramiko;
3. Start an API on the local loopback interface;
4. Let authorized AI agents or scripts execute commands, consume streaming output, and send interactive input.

```text
┌────────────────┐ launch + args ┌──────────────────────────┐    SSH    ┌──────────────┐
│ TianYue gateway │ ────────────▶ │ tianyue_ssh_bridge.exe   │ ────────▶ │ target server│
└────────────────┘               └────────────┬─────────────┘          └──────────────┘
                                              │ 127.0.0.1:<port>
                                              │ HTTP / SSE / Socket.IO
                                     ┌────────▼────────┐
                                     │ AI agent / script│
                                     └─────────────────┘
```

## 2. Features

- ✅ **Single-file EXE**: PyInstaller Windows build; no Python installation required on the operator workstation
- ✅ **TianYue argument support**: observed SecureCRT session arguments plus GNU options, SSH URLs, and positional input
- ✅ **Legacy SSH compatibility**: Paramiko 2.12.0 remains compatible with selected older gateways and devices
- ✅ **Complete local API**: health, one-shot execution, SSE streaming, interactive input, and Socket.IO
- ✅ **Automatic port discovery**: defaults to `8765`, increments when busy, and writes `active_port.txt`
- ✅ **Connection keepalive**: runs a configurable harmless command after an idle interval
- ✅ **Readable console**: colored blocks show sanitized launch fields, connection state, commands, exit codes, and server results
- ✅ **Secure defaults**: loopback-only binding; command/result bodies are previewed only in the live console, never in log files
- ✅ **Automated releases**: tags trigger GitHub Actions builds, checksums, and Release publication

## 3. Repository layout

```text
plugin-bastion-bridge-tianyue/
├── main.py                         # Entry point: parse, connect, start API
├── params.py                       # TianYue/SecureCRT argument parser
├── ssh_client.py                   # Paramiko SSH engine
├── api_server.py                   # Flask, SSE, and Socket.IO API
├── connection.py                   # Connection data model
├── config.py                       # Local configuration
├── logger.py                       # Rotating logs
├── version.py                      # Version marker and supported bastion version
├── requirements.txt                # Fully pinned dependencies
├── tianyue_ssh_bridge.spec         # PyInstaller definition
├── skill/bastion-tianyue/          # DeepSeek Harness skill bundle
├── scripts/install.ps1             # Skill installer and optional EXE download
├── scripts/uninstall.ps1           # Skill and optional EXE removal
├── docs/通用桥接器使用说明.md          # Full usage guide in Chinese
├── SECURITY.md                     # Security policy
└── .github/workflows/release.yml   # Automated build and Release
```

Build output, logs, virtual environments, and local configuration are excluded by `.gitignore`.

## 4. Quick start

### 4.1 Install the DeepSeek Harness skill in one line

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/AFAP/plugin-bastion-bridge-tianyue/main/scripts/install.ps1 | iex"
```

The skill is installed to `%USERPROFILE%\.dsh\skills\bastion-tianyue\`, or under `DSH_HOME` when set.
Invoke `/bastion-tianyue` explicitly. The skill stays out of model-facing catalogs and context until then.

### 4.2 Download the bridge

Download both files from [Releases](https://github.com/AFAP/plugin-bastion-bridge-tianyue/releases):

- `tianyue_ssh_bridge.exe`
- `tianyue_ssh_bridge.exe.sha256`

From a local clone, you can install the skill and download the latest bridge together:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -InstallBridge
```

## 5. Deployment and use

### 5.1 Verify the artifact

```powershell
Get-FileHash -Algorithm SHA256 .\tianyue_ssh_bridge.exe
Get-Content .\tianyue_ssh_bridge.exe.sha256
```

Use the EXE only after the hashes match.

### 5.2 Configure TianYue's local tool

In TianYue's local tool settings, point the SSH/SecureCRT executable path to a stable full path for
`tianyue_ssh_bridge.exe`. The installer downloads it to the following location by default:

```text
%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\bin\tianyue_ssh_bridge.exe
```

The UI label can vary between TianYue versions. Follow your organization's existing external SecureCRT tool process.

### 5.3 Connect and verify

Click an authorized SSH resource. After the bridge starts, read:

```text
%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\active_port.txt
```

Its default content is `127.0.0.1:8765`. Use the actual port from the file:

```bash
curl http://127.0.0.1:8765/health
```

The API is ready when it returns `{"status":"ok","connected":true}`. The same response carries
`version`, `bridge_version`, and `bastion`, which identify the exact bridge build and the bastion
client version it was verified against.

## 6. API quick reference

| Operation | Request |
|---|---|
| Health | `GET /health` |
| Execute | `POST /execute` `{"command":"df -h","timeout":30}` |
| Stream | `GET /stream?command=...` |
| Interactive input | `POST /input` `{"data":"y\n"}` |
| Socket.IO | Same Origin, default `/socket.io/` path, events `execute` / `stream` / `input` |

`GET /health` response (the version fields are additive; `status` and `connected` are unchanged):

```json
{
  "status": "ok",
  "connected": true,
  "version": "1.0.0-om6.0.4.16603",
  "bridge_version": "1.0.0",
  "bastion": {"client": "OMClientPlus", "version": "6.0.4.16603"}
}
```

```bash
curl -X POST http://127.0.0.1:8765/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"uname -a","timeout":30}'
```

```json
{"stdout":"Linux ...\n","stderr":"","exit_code":0}
```

See [docs/通用桥接器使用说明.md](docs/通用桥接器使用说明.md) for the full interface guide.

## 7. Configuration

Create `%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\config.json` when customization is needed;
built-in defaults are used when it is absent.

| Key | Default | Description |
|---|---|---|
| `api_host` | `127.0.0.1` | **Never set this to `0.0.0.0`** |
| `api_port` | `8765` | Increments to `8766`, `8767`, and so on when busy |
| `ssh_connect_timeout` | `15` | SSH handshake timeout in seconds |
| `retry_max_attempts` | `3` | Connection attempts |
| `retry_delay_seconds` | `2` | Delay between attempts in seconds |
| `keepalive_enabled` | `true` | Enable idle keepalive |
| `keepalive_interval_seconds` | `60` | Idle seconds before keepalive |
| `keepalive_command` | `ls` | Must be harmless |
| `log_level` | `INFO` | Logging level |
| `console_log` | `true` | Show colored status, command, and response previews in the console |
| `console_verbose` | `false` | Also show detailed INFO/DEBUG technical records in the console |
| `console_output_limit` | `12000` | Per-command or output-field preview limit; full API responses are unaffected |

## 8. Logs and troubleshooting

Logs are stored at `%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\logs\bridge.log`.

The console uses `>>>` for received parameters or commands and `<<<` for server responses,
including source, duration, exit code, and stdout/stderr sizes. Passwords and interactive-input
bodies remain hidden. Command and response bodies are live-console only; `bridge.log` keeps
metadata such as lengths, exit codes, and connection status.

| Symptom | Check |
|---|---|
| No port file after clicking a resource | Verify the local tool path and TianYue invocation arguments |
| API connection refused | Read `active_port.txt` again; do not assume a fixed port |
| `connected: false` | Inspect authentication, network, or parsing errors in the log |
| `exit_code: -1` | SSH is unavailable or disconnected; run health again |
| Antivirus warning | Verify SHA-256 and follow organizational allowlisting, or run from source |

## 9. Security and compliance

- The bridge receives session credentials from TianYue. Use it only in an **authorized environment**.
- The unauthenticated API binds only to loopback, but **any local process may still call it**.
- Passwords remain in process memory only; arguments are redacted, and command/output bodies are never written to log files.
- The console can display sensitive server output. Close it after use and do not share screenshots containing business data.
- The first connection automatically accepts the host key. Confirm this meets your security baseline.
- See [SECURITY.md](SECURITY.md) for the full risk and hardening guidance.

## 10. FAQ

**Q: What is the default port?** `8765`. If it is busy, the bridge increments it; trust `active_port.txt`.

**Q: Which TianYue versions are supported?** The current baseline, version marker
`1.0.0-om6.0.4.16603`, runs stable against `OMClientPlus 6.0.4.16603`. The parser implements the
SecureCRT session style that client produces and several generic formats. Other client versions
need re-verification and their own version marker.

**Q: Is DeepSeek Harness required?** No. Any AI agent or script that can access the local HTTP API can integrate.

**Q: Why is no EXE committed?** Build artifacts stay out of Git. GitHub Actions publishes the EXE and SHA-256 in Releases.

## 11. Development and build

Local verification:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m PyInstaller tianyue_ssh_bridge.spec --clean --noconfirm
.\dist\tianyue_ssh_bridge.exe --version
```

The result is `dist\tianyue_ssh_bridge.exe`, which Git ignores. `--version` must print the same
bridge and bastion versions as [version.py](version.py).

CI flow: push a `v*` tag (for example `v1.0.0-om6.0.4.16603`, matching `VERSION` in `version.py`) →
install pinned dependencies on a Windows runner → build with PyInstaller → generate SHA-256 →
publish a GitHub Release. `workflow_dispatch` supports a build without a tag.

## 12. Related documents

- [docs/通用桥接器使用说明.md](docs/通用桥接器使用说明.md) — API use and troubleshooting
- [SECURITY.md](SECURITY.md) — security design, risks, and reporting
- [README.md](README.md) — Chinese version

## 13. License

[MIT](LICENSE) © plugin-bastion-bridge-tianyue contributors

> Disclaimer: this tool is for authorized operations, security testing, and research only. Users are responsible for ensuring legal authorization for the bastion and target systems. The maintainers are not liable for misuse.
