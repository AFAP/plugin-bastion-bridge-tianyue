---
name: tianyue-bastion
description: 通过天玥堡垒机桥接器的本地 REST API，在已连接的目标服务器上执行命令、流式查看输出并发送交互输入。
whenToUse: 用户要求操作天玥堡垒机已连接的服务器，或提到天玥、堡垒机桥接器、sshbridge、8765 端口时。
---

# 天玥堡垒机 SSH 桥接器操作技能

## 背景

用户在天玥运维安全网关中点击 SSH 资源后，本地桥接器会建立 SSH 会话，并在
`127.0.0.1` 启动 HTTP、SSE 与 Socket.IO API。本技能通过该 API 完成获授权的服务器操作。

```text
天玥控制台 ──唤起──▶ tianyue_ssh_bridge.exe ──SSH──▶ 目标服务器
                              ▲
                              └── 127.0.0.1:<端口> ◀── 你（AI）
```

## 第一步：发现端口并健康检查

每次操作前先运行：

```powershell
python "<本技能目录>\scripts\bridge.py" health
```

脚本从以下文件读取实际监听地址：

```text
%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\active_port.txt
```

- `"connected": true`：可以执行命令。
- `connected: false`：SSH 未连接，停止发送命令并排错。
- 端口文件不存在或服务不可达：请用户在天玥控制台重新点击目标 SSH 资源，等待数秒再试。

默认端口是 `8765`，占用时会自动顺延。**端口文件是唯一事实来源，不要沿用旧端口。**

## 第二步：执行命令

```powershell
python "<本技能目录>\scripts\bridge.py" exec "uname -a"
python "<本技能目录>\scripts\bridge.py" exec "df -h" --timeout 30
```

响应字段：

```json
{"stdout": "...", "stderr": "", "exit_code": 0}
```

| `exit_code` | 含义 | 处理 |
|---|---|---|
| `0` | 成功 | 采用输出，即使 `stdout` 为空也可能正常 |
| 非 `0` | 远端命令失败 | 结合 `stderr` 解释原因，不盲目重试 |
| `-1` | SSH 未连接或执行异常 | 先执行 `health`，不要继续发命令 |

## 第三步：长任务与流式输出

```powershell
python "<本技能目录>\scripts\bridge.py" stream "dmesg | tail -n 5"
```

预计 30 秒内完成的命令用 `exec`；耗时较长、持续输出或时间不确定时用 `stream`。
输出过长时只摘取关键片段，并明确告知用户已截断。

## 交互式输入

```powershell
python "<本技能目录>\scripts\bridge.py" input "y`n"
```

除非用户明确授权，绝不自动发送 `y`、密码或任何确认输入。

## 安全红线

1. 本地 API 无鉴权；只在用户明确授权的会话中操作。
2. 不把输出中的密码、私钥、令牌或业务数据写入无保护文件或转发到本机之外。
3. 删除、关机、重启、防火墙变更、磁盘格式化、生产数据库写入等危险操作必须逐条确认。
4. 所有命令应保留在堡垒机审计通道内，不绕过审计、不提权、不清理历史。

## 排错速查

| 现象 | 处理 |
|---|---|
| 端口文件不存在 | 请用户在天玥控制台点击 SSH 资源唤起桥接器 |
| `/health` 为 `connected: false` | 查看 `%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\logs\bridge.log` |
| `exit_code: -1` | 先检查健康状态，必要时请用户重新连接资源 |
| 命令超时 | 增大 `--timeout` 或改用 `stream` |
| 中文乱码 | 使用本技能的 `scripts/bridge.py`，它会把控制台切到 UTF-8 |

详细说明：

- `references/api.md`：REST、SSE、Socket.IO 接口参考
- `references/troubleshooting.md`：完整排错手册
