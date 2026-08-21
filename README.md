# 天玥堡垒机 SSH 桥接器 · TianYue Bastion SSH Bridge

<div align="center">
  <b>中文</b> · <a href="README.en.md">English</a>
</div>

> **让 AI 通过本地 RESTful API 操作天玥堡垒机中的服务器。**
> 把只能由桌面终端完成的 SSH 运维，转换成 HTTP、SSE 与 Socket.IO 接口。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/AFAP/plugin-bastion-bridge-tianyue)](https://github.com/AFAP/plugin-bastion-bridge-tianyue/releases)
[![Build](https://github.com/AFAP/plugin-bastion-bridge-tianyue/actions/workflows/release.yml/badge.svg)](https://github.com/AFAP/plugin-bastion-bridge-tianyue/actions/workflows/release.yml)

| 使用者 | 接入方式 |
|---|---|
| **DeepSeek Harness 用户** | 一行安装技能；需要操作服务器时输入 `/bastion-tianyue` 手动唤起 |
| **其他 AI、Agent 或脚本** | 直接调用本机 REST、SSE 或 Socket.IO API，不绑定语言与框架 |

## 1. 它解决了什么问题

天玥运维安全网关可把 SSH 资源交给 SecureCRT 等本地终端，但这类界面主要面向人工交互，
AI 难以稳定发送命令并获得结构化结果。本项目提供一个可配置为天玥本地 SSH 工具的单文件桥接器：

1. 接收天玥传入的 SecureCRT 风格连接参数；
2. 解析主机、端口、账号与临时凭证，通过 Paramiko 建立 SSH 会话；
3. 在本机回环地址启动 API；
4. 让获授权的 AI 或脚本执行命令、查看流式输出并发送交互输入。

```text
┌──────────────┐   唤起并传参   ┌──────────────────────────┐    SSH    ┌──────────────┐
│ 天玥运维安全网关 │ ───────────▶ │ tianyue_ssh_bridge.exe   │ ────────▶ │ 目标服务器      │
└──────────────┘               └────────────┬─────────────┘          └──────────────┘
                                            │ 127.0.0.1:<端口>
                                            │ HTTP / SSE / Socket.IO
                                   ┌────────▼────────┐
                                   │ AI 助手 / 脚本    │
                                   └─────────────────┘
```

## 2. 功能特性

- ✅ **单文件 EXE**：PyInstaller Windows 单文件构建，无需在目标终端安装 Python
- ✅ **天玥参数适配**：支持已观察到的 SecureCRT 会话参数，以及 GNU 参数、SSH URL、位置参数
- ✅ **旧 SSH 算法兼容**：锁定 Paramiko 2.12.0，兼容部分旧堡垒机与网络设备
- ✅ **完整本地接口**：健康检查、单次执行、SSE 流式输出、交互输入与 Socket.IO
- ✅ **端口自动发现**：默认 `8765`，占用时顺延并写入 `active_port.txt`
- ✅ **连接保活**：空闲时执行可配置的无害命令，降低会话超时概率
- ✅ **直观控制台**：彩色展示脱敏后的启动参数、连接状态、收到的指令、退出码与服务器返回
- ✅ **安全默认**：仅监听 `127.0.0.1`；命令与返回正文只在当前控制台预览，不写入日志文件
- ✅ **自动发布**：tag 触发 GitHub Actions 构建、校验和生成与 Release 发布

## 3. 目录结构

```text
plugin-bastion-bridge-tianyue/
├── main.py                         # 入口：解析参数、建连、启动 API
├── params.py                       # 天玥/SecureCRT 参数解析
├── ssh_client.py                   # Paramiko SSH 引擎
├── api_server.py                   # Flask、SSE 与 Socket.IO API
├── connection.py                   # 连接参数数据类
├── config.py                       # 本地配置
├── logger.py                       # 滚动日志
├── requirements.txt                # 全量锁版依赖
├── tianyue_ssh_bridge.spec         # PyInstaller 配置
├── skill/bastion-tianyue/          # DeepSeek Harness 技能包
├── scripts/install.ps1             # 技能安装与可选 EXE 下载
├── scripts/uninstall.ps1           # 技能与可选 EXE 卸载
├── docs/通用桥接器使用说明.md          # 完整使用说明
├── SECURITY.md                     # 安全策略
└── .github/workflows/release.yml   # 自动构建与 Release
```

构建产物、日志、虚拟环境与本地配置均由 `.gitignore` 排除，不进入仓库。

## 4. 快速开始

### 4.1 一行安装 DeepSeek Harness 技能

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/AFAP/plugin-bastion-bridge-tianyue/main/scripts/install.ps1 | iex"
```

技能安装到 `%USERPROFILE%\.dsh\skills\bastion-tianyue\`；设置了 `DSH_HOME` 时改用该目录。
安装后输入 `/bastion-tianyue` 手动唤起。该技能不会自动进入模型目录或上下文。

### 4.2 下载桥接器

从 [Releases](https://github.com/AFAP/plugin-bastion-bridge-tianyue/releases) 下载：

- `tianyue_ssh_bridge.exe`
- `tianyue_ssh_bridge.exe.sha256`

也可在本地克隆仓库后安装技能并下载最新桥接器：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -InstallBridge
```

## 5. 部署与使用

### 5.1 校验文件

```powershell
Get-FileHash -Algorithm SHA256 .\tianyue_ssh_bridge.exe
Get-Content .\tianyue_ssh_bridge.exe.sha256
```

确认两边哈希一致后再使用。

### 5.2 配置天玥本地工具

在天玥运维安全网关的本地工具配置中，把 SSH/SecureCRT 工具路径指向
`tianyue_ssh_bridge.exe` 的稳定完整路径。若用安装脚本下载，默认路径为：

```text
%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\bin\tianyue_ssh_bridge.exe
```

界面名称可能因天玥版本不同而变化；请按组织现有的 SecureCRT 外部工具配置流程操作。

### 5.3 建立连接并验证

点击已授权的 SSH 资源。桥接器启动后读取：

```text
%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\active_port.txt
```

默认内容为 `127.0.0.1:8765`。按文件中的实际端口执行：

```bash
curl http://127.0.0.1:8765/health
```

返回 `{"status":"ok","connected":true}` 即可调用命令接口。

## 6. API 速查

| 操作 | 请求 |
|---|---|
| 健康检查 | `GET /health` |
| 执行命令 | `POST /execute` `{"command":"df -h","timeout":30}` |
| 流式输出 | `GET /stream?command=...` |
| 交互输入 | `POST /input` `{"data":"y\n"}` |
| Socket.IO | 同一 Origin，默认路径 `/socket.io/`，事件 `execute` / `stream` / `input` |

```bash
curl -X POST http://127.0.0.1:8765/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"uname -a","timeout":30}'
```

```json
{"stdout":"Linux ...\n","stderr":"","exit_code":0}
```

完整接口见 [docs/通用桥接器使用说明.md](docs/通用桥接器使用说明.md)。

## 7. 配置项

可按需创建 `%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\config.json`；缺失时使用默认值。

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `api_host` | `127.0.0.1` | **切勿设为 `0.0.0.0`** |
| `api_port` | `8765` | 占用时自动顺延 `8766`、`8767` 等 |
| `ssh_connect_timeout` | `15` | SSH 握手超时秒数 |
| `retry_max_attempts` | `3` | 连接重试次数 |
| `retry_delay_seconds` | `2` | 重试间隔秒数 |
| `keepalive_enabled` | `true` | 是否启用空闲保活 |
| `keepalive_interval_seconds` | `60` | 触发保活前的空闲秒数 |
| `keepalive_command` | `ls` | 保活命令，必须无副作用 |
| `log_level` | `INFO` | 日志级别 |
| `console_log` | `true` | 是否显示彩色控制台状态、指令与返回预览 |
| `console_verbose` | `false` | 是否在控制台同时显示详细 INFO/DEBUG 技术日志 |
| `console_output_limit` | `12000` | 单个指令或输出字段的控制台预览上限；不影响 API 返回的完整数据 |

## 8. 日志与排错

日志位置：`%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\logs\bridge.log`。

控制台用 `>>>` 标识收到的参数或指令，用 `<<<` 标识服务器返回，并展示来源、耗时、
退出码以及 stdout/stderr 字符数。密码和交互输入正文始终隐藏；指令与返回正文仅显示在
当前控制台，`bridge.log` 仍只记录长度、退出码和连接状态等元数据。

| 现象 | 排查方向 |
|---|---|
| 点击资源后无端口文件 | 检查本地工具路径与天玥调用参数 |
| API 连接被拒 | 重新读取 `active_port.txt`，不要假定端口固定 |
| `connected: false` | 查看日志中的认证、网络或参数解析错误 |
| `exit_code: -1` | SSH 未连接或已断开，重新健康检查 |
| 杀毒软件误报 | 核对 SHA-256 后按组织流程处理，或从源码运行 |

## 9. 安全与合规

- 桥接器会接收天玥传入的会话凭证，仅可在**已授权环境**使用。
- API 无鉴权但只监听回环地址；**本机任意进程仍可能调用**。
- 密码只存在于进程内存；参数会脱敏，命令与输出正文不写入日志文件。
- 控制台可能展示服务器业务输出；操作结束后请关闭窗口，不要截图或转发敏感内容。
- 主机密钥首次连接使用自动接受策略，请确认符合组织安全基线。
- 详细风险与加固建议见 [SECURITY.md](SECURITY.md)。

## 10. FAQ

**Q：默认端口是多少？** `8765`。端口占用时自动顺延，以 `active_port.txt` 为准。

**Q：支持哪些天玥版本？** 当前解析器按天玥 V6.0 已观察到的 SecureCRT 会话风格实现，
同时兼容多种通用格式。若参数形态不同，请只提交脱敏后的复现信息。

**Q：是否必须使用 DeepSeek Harness？** 不需要。任何能访问本机 HTTP 接口的 AI、Agent 或脚本都可接入。

**Q：仓库为什么没有 EXE？** 构建产物不提交到 Git；GitHub Actions 会在 Release 中提供 EXE 与 SHA-256。

## 11. 开发与构建

本地验证：

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller tianyue_ssh_bridge.spec --clean --noconfirm
```

产物位于 `dist\tianyue_ssh_bridge.exe`，不会被 Git 跟踪。

CI 发布流程：推送 `v*` tag → Windows runner 安装锁定依赖 → PyInstaller 构建 →
生成 SHA-256 → 发布 GitHub Release。`workflow_dispatch` 可用于无 tag 的手动构建验证。

## 12. 相关文档

- [docs/通用桥接器使用说明.md](docs/通用桥接器使用说明.md) —— API 使用与排错
- [SECURITY.md](SECURITY.md) —— 安全设计、风险与报告方式
- [README.en.md](README.en.md) —— English version

## 13. License

[MIT](LICENSE) © plugin-bastion-bridge-tianyue contributors

> 免责声明：本工具仅供授权运维、安全测试与学习研究使用。使用者须保证对目标服务器及堡垒机环境拥有合法操作权限，因滥用造成的后果与项目维护者无关。
