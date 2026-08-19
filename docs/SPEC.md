# 项目目标 SPEC

> 版本：v1.0 ｜ 2026-08-19 ｜ 基于旧项目 qwen36-5090-deploy 升级

## 1. 项目定位与目标

在 **AutoDL RTX 5090（32GB）单卡** 上，用 **llama.cpp llama-server + GGUF**
部署 **Qwen3.8-27B**，对外提供生产级、OpenAI 兼容的 LLM 服务，供本人及
几个朋友（每人一个 API key）的本地 Agent / 工具调用。

核心目标：
- 27B 量级高质量模型（Terminal Bench 2.1 73.0，较 3.6 提升 9.6 分，厂商口径）
- 长上下文（默认 524288 YaRN 扩长；另有 262K 全功能档）
- OpenAI 兼容 API（chat/completions、responses、models、health）
- 生产级：API Key 鉴权、后台守护、健康检查、日志
- 多用户：每人一个独立 API key
- 多模态：图像输入（mmproj 视觉投影器）
- 性能：MTP 推测解码单用户提速 ~1.5x

## 2. 核心功能列表

| 功能 | 说明 | 状态 |
|------|------|------|
| 并行模型下载 | ModelScope 16 线程（~5-10MB/s） | 脚本就绪 |
| llama-server 编译 | sm_120，无卡 -j1 | 脚本就绪 |
| 模板修复 | system 位置容忍 + 多轮空 thinking 块 | 脚本就绪 |
| 多用户 key | `--api-key-file` 读 `.api_keys`（沿用 6 把） | 沿用 |
| systemd 自启 | `deploy/qwen38.service`（崩溃自动重启） | 脚本就绪 |
| 健康检查 | `/health` | 就绪 |
| 公网暴露 | AutoDL 自定义服务 6006 → HTTPS | 依赖控制台 |
| 本地对接 | `.env.example` → `.env`（三要素） | 就绪 |

## 3. 技术栈与架构概览

- **推理引擎**：llama.cpp llama-server（Blackwell sm_120 CUDA 后端，**必须最新构建**）
- **模型**：`ggml-org/Qwen3.8-27B-GGUF` Q4_K_M.gguf（18.97GB）
- **MTP 头**：`mtp-Qwen3.8-27B-Q4_0.gguf`（1.68GB，推测解码）
- **视觉投影**：`mmproj-Qwen3.8-27B-Q8_0.gguf`（0.63GB）
- **量化**：GGUF Q4_K_M（32GB 显存放不下 BF16 52GB，Q4 留足 KV 空间）
- **架构**：qwen35（新 GGUF 架构，16/64 层全注意力 + 48 层 Gated DeltaNet，
  KV 缓存约为传统 27B 的 1/4）
- **编译**：cmake `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120`，CUDA 12.8+
- **暴露**：AutoDL 自定义服务公网 HTTPS + API Key 鉴权

## 4. 关键接口

| 端点 | 用途 |
|------|------|
| `GET /health` | 健康检查（无鉴权） |
| `GET /v1/models` | 模型列表（Bearer 鉴权） |
| `POST /v1/chat/completions` | 对话补全（Bearer 鉴权） |
| `POST /v1/responses` | Responses API（Codex `wire_api="responses"` 用） |

三要素：`base_url = https://<公网URL>/v1`、`api_key = 每人一把`、`model = qwen3.8-27b`

## 5. 已知约束与边界

- 单卡 32GB、`-np 1` 单槽：多人同时调用会排队
- 无每用户限流/配额：需人工控制分发范围
- AutoDL 按量计费：他人调用 = 你的 GPU 成本
- 无卡模式仅能下载/编译，运行必带卡（driver stub 限制）
- 262144 原生上下文 + mmproj + MTP 全开时显存紧张，默认 131072
