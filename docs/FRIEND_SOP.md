# Qwen3.8-27B AI 服务使用说明（朋友版 SOP）

> 这是一台私人部署的 **Qwen3.8-27B** 大模型服务（千问 3.8，27B 参数，RTX 5090 单卡）。
> 提供 OpenAI 兼容 API，支持超长上下文与图片输入。

## 1. 你的专属连接信息（三要素）

| 项 | 值 |
|---|---|
| Base URL | `https://u1068217-f8tl-73e1c220.weste.seetacloud.com:8443/v1` |
| API Key | `<你的专属KEY>`（每人一把，请勿外传） |
| Model | `qwen3.8-27b` |

## 2. 一分钟自测（curl）

```bash
curl https://u1068217-f8tl-73e1c220.weste.seetacloud.com:8443/v1/chat/completions \
  -H "Authorization: Bearer <你的专属KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"你好，用一句话介绍你自己"}]}'
```

能正常返回回复即接入成功。

## 3. 能力说明

- **上下文**：262K tokens（约相当于几十万汉字），多轮长对话不会"失忆"
- **图片输入**：支持截图/图片理解（OpenAI 兼容 `image_url` 格式）
- **多轮记忆**：同一会话内跨轮记住之前的内容
- **API**：OpenAI 兼容（`/v1/chat/completions`、`/v1/responses`、`/v1/models`、`/health`）
- **思考模式**：默认关闭思考（快速响应）；复杂任务可在请求里加 `"enable_thinking":true`

## 4. Python 接入示例

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://u1068217-f8tl-73e1c220.weste.seetacloud.com:8443/v1",
    api_key="<你的专属KEY>",
)

# 普通对话
resp = client.chat.completions.create(
    model="qwen3.8-27b",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)

# 多轮对话（把历史消息一起传）
messages = [
    {"role": "user", "content": "我的名字是小明"},
    {"role": "assistant", "content": "好的，小明！"},
    {"role": "user", "content": "我叫什么名字？"},
]
resp = client.chat.completions.create(model="qwen3.8-27b", messages=messages)
print(resp.choices[0].message.content)

# 图片输入
import base64
b64 = base64.b64encode(open("photo.png", "rb").read()).decode()
resp = client.chat.completions.create(
    model="qwen3.8-27b",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "这张图片里有什么？"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ],
    }],
)
print(resp.choices[0].message.content)
```

## 5. 接入常用工具

支持 OpenAI 兼容接口的工具都可以直接填三要素：

| 工具 | Base URL | Key | Model |
|---|---|---|---|
| Claude Code API 切换器 | 同上 `/v1` | 你的 key | `qwen3.8-27b` |
| Codex / Hermes | 同上 `/v1` | 你的 key | `qwen3.8-27b` |
| 任意 OpenAI SDK | 同上 `/v1` | 你的 key | `qwen3.8-27b` |

## 6. 使用须知（请务必阅读）

- **单卡单槽**：服务器同时只能处理一个请求，多人并发会排队等待，请耐心，不要反复重试
- **按量计费**：这台服务器是按小时租的（真实花钱），请**不要**做批量压测、刷题、跑大量脚本等任务
- **隐私**：你的对话会经过这台自建服务器（仅我本人可访问日志），但仍建议**不要发送机密/敏感内容**
- **Key 安全**：专属 key 不要发群、不要提交到公开仓库；发现泄露请立刻告诉我换新
- **合理用量**：单次任务建议控制在合理 token 范围内；长时间占用的任务请先沟通
- **关机提醒**：服务器不是 7x24 常开，关机期间请求会超时——遇到超时先问一下服务是否在运行

## 7. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 返回 401 | Key 错误或已失效 | 检查 key 是否完整复制 |
| 请求超时 | 服务器繁忙或已关机 | 稍后重试；联系我确认服务状态 |
| 回复慢 | 单卡排队（有其他人在用） | 等待，或错峰使用 |
| 不知道服务是否正常 | - | `curl https://...:8443/health` 返回 `{"status":"ok"}` 即正常 |

## 8. 联系

使用中遇到任何问题、或需要开通更高权限（如暂时开启思考模式/更长输出），直接联系我。
