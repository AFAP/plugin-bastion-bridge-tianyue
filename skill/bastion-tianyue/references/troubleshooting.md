# 排错手册（天玥堡垒机桥接器）

## 症状与处理

| 现象 | 排查方向 |
|---|---|
| `active_port.txt` 不存在 | 桥接器未被唤起；请用户在天玥控制台点击 SSH 资源 |
| API 连接被拒 | 重新读取端口文件；端口占用时会从 `8765` 自动顺延 |
| `/health` 为 `connected: false` | 查看日志末尾的认证、网络或参数解析错误 |
| `exit_code: -1` | SSH 已断开或未连接；先健康检查，必要时重新连接资源 |
| 命令超时 | 增大 `timeout` 或使用 `/stream` |
| `no acceptable kex algorithm` | 当前版本保留 Paramiko 2.12.0 兼容旧算法；如仍失败，请提交已脱敏日志 |
| 中文乱码 | 使用 `scripts/bridge.py`，不要在非 UTF-8 终端手工拼请求 |
| 提示 `SecureCRT工具版本太低` | 客户端版本高于桥接器标注的版本，换用对应 `-om` 版本包 |
| 杀毒软件报毒 | 校验 Release SHA-256 后按组织流程加白，或使用源码运行 |

## 日志位置

```text
%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\logs\bridge.log
```

日志会滚动保留。密码与内嵌凭证会脱敏，命令和输出正文不会写入日志文件。
桥接器控制台默认用 `>>>` / `<<<` 分块展示指令与服务器返回；交互输入正文始终隐藏。

## 配置文件

```text
%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\config.json
```

配置文件可按需创建；缺失时使用内置默认值。

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `api_host` | `127.0.0.1` | **切勿改为 `0.0.0.0`** |
| `api_port` | `8765` | 被占用时自动顺延 |
| `ssh_connect_timeout` | `15` | SSH 握手超时秒数 |
| `retry_max_attempts` | `3` | 连接失败重试次数 |
| `keepalive_enabled` | `true` | 空闲保活开关 |
| `keepalive_interval_seconds` | `60` | 空闲多久触发保活 |
| `keepalive_command` | `ls` | 保活命令，必须无副作用 |
| `log_level` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

## 天玥参数适配

桥接器支持天玥/SecureCRT 会话风格参数、GNU 风格参数、SSH URL 与 `user@host:port`。
若新版网关传参不同，请只提供脱敏后的参数形态，并在 `params.py` 增加解析分支。
