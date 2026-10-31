# 桥接器 API 参考（天玥堡垒机）

桥接器默认监听 `127.0.0.1:8765`，实际地址以
`%LOCALAPPDATA%\sshbridge\TianYueSSHBridge\active_port.txt` 为准。下文 `<BASE>` 代表实际地址。

## 1. 健康检查

```http
GET <BASE>/health
```

```json
{
  "status": "ok",
  "connected": true,
  "version": "1.1.0-om6.0.7.0",
  "bridge_version": "1.1.0",
  "bastion": {"client": "OMClientPlus", "version": "6.0.7.0"}
}
```

`version` / `bridge_version` / `bastion` 是版本标记：桥接器按该堡垒机客户端版本的参数形态
验证过。旧版本桥接器不返回这些字段，判断可用性仍以 `connected` 为准。

## 2. 执行单次命令

```http
POST <BASE>/execute
Content-Type: application/json

{"command": "uname -a", "timeout": 30}
```

```json
{"stdout": "Linux ...", "stderr": "", "exit_code": 0}
```

`exit_code` 为 `0` 表示成功，非 `0` 表示远端命令失败，`-1` 表示 SSH 未连接或执行异常，
`126` 表示命中桥接器本地危险操作兜底（命令未下发，`stderr` 为提示文案；不要改写命令绕过）。

## 3. 流式输出（SSE）

```http
GET <BASE>/stream?command=dmesg%20%7C%20tail
```

事件序列：`start` → `stdout` / `stderr` → `exit` → `end`。退出事件格式：

```text
event: exit
data: {"exit_code": 0}
```

## 4. 交互输入

```http
POST <BASE>/input
Content-Type: application/json

{"data": "y\n"}
```

交互 shell 不可用时返回 HTTP 503。

## 5. Socket.IO

连接同一 HTTP Origin，默认传输路径为 `/socket.io/`。

| 发送事件 | 载荷 | 接收事件 |
|---|---|---|
| `execute` | `{"command": "...", "timeout": 30}` | `result` |
| `stream` | `{"command": "..."}` | `start` → `output` → `end` |
| `input` | `{"data": "y\n"}` | `input_status` |

连接建立时服务端发送 `status`：`{"status": "connected", "ssh_connected": true}`。

## 6. 错误响应

```json
{"error": "execute failed", "detail": "...", "exception_type": "..."}
```

## 7. 接口选择

| 场景 | 接口 |
|---|---|
| 简单查询 | `POST /execute` |
| 耗时或持续输出 | `GET /stream` 或 Socket.IO `stream` |
| 交互输入 | `POST /input` 或 Socket.IO `input` |
