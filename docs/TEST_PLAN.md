# 项目测试计划 TEST_PLAN

> 版本：v1.0 ｜ 2026-08-19

## 1. 测试范围与策略

部署性项目，测试围绕产物可用性与服务稳定性。方案为 llama.cpp llama-server
+ GGUF（Q4_K_M + MTP + mmproj）。

## 2. 编译产物

| 用例 | 命令 | 预期 |
|------|------|------|
| llama-server 可执行 | `file build/bin/llama-server` | ELF 可执行 |
| 依赖库齐全 | `ldd build/bin/llama-server` | 无 not found |
| 支持 MTP | `llama-server --help` | `--spec-type` / `draft-mtp` |
| 支持 mmproj | `llama-server --help` | `--mmproj` |
| 支持多 key | `llama-server --help` | `--api-key-file` |
| 架构识别 | 启动日志 | 加载 qwen35 架构无报错 |

## 3. 模型完整性

| 用例 | 预期 |
|------|------|
| Q4_K_M.gguf = 18973870432 bytes | 完整 |
| mtp-Q4_0.gguf = 1680271648 bytes | 完整 |
| mmproj-Q8_0.gguf = 629247008 bytes | 完整 |

## 4. 服务功能（带卡模式）

| 用例 | 端点 | 预期 |
|------|------|------|
| 健康检查 | `GET /health` | 200 `{"status":"ok"}` |
| 模型列表 | `GET /v1/models` | 返回 `qwen3.8-27b`（alias） |
| 对话 | `POST /v1/chat/completions` | 正常回复，无 thinking |
| Responses | `POST /v1/responses` | Codex wire_api=responses 可用 |
| 鉴权 | 带/不带 Bearer | 无 key=401，正确=200 |
| 多 key | user1~5 各 key | 6 把全部可用 |
| system 位置 | system 在中间 | 模板修复后不报错 |
| 多轮 | 连续 3+ 轮 | 不出现嵌套空 thinking、不失忆 |
| 多模态 | image_url 输入 | mmproj 加载后返回内容 |
| MTP | 单用户压测 | tok/s 高于无 MTP |

## 5. 已知测试缺口

- 高并发压测（单卡 `-np 1`，多人排队）
- 262144 长上下文端到端（默认 131072）
- 多 key 并发隔离（资源竞争未实测）
