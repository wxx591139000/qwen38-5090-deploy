# 项目详细方案 ARCHITECTURE

> 版本：v1.0 ｜ 2026-08-19 ｜ 方案：llama.cpp llama-server + GGUF（承接旧项目已验证路线）

## 1. 系统架构图（文字描述）

```
┌─────────────────────────────────────────────────────────────┐
│                    本地电脑（Windows）                        │
│  Hermes / Claude Code / Codex / 自研工具（本人 + 几个朋友）    │
│  base_url + api_key + model=qwen3.8-27b                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (Bearer token)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              AutoDL 自定义服务（公网 HTTPS URL）              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │      llama-server (端口 6006)                          │  │
│  │  OpenAI/Responses: /health /v1/responses /chat...     │  │
│  │  --api-key-file .api_keys  ← 多用户鉴权(每行一把)      │  │
│  │  -ngl 999 -c 131072 -fa on -ctk/-ctv q4_0            │  │
│  │  --reasoning off --alias qwen3.8-27b --jinja          │  │
│  │  --chat-template-file qwen38_template.jinja           │  │
│  │  -md mtp-Q4_0 --spec-type draft-mtp（推测解码）        │  │
│  │  --mmproj mmproj-Q8_0（视觉投影）                      │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────┬───────────────────────────┐  │
│  │ 模型(数据盘)               │ 编译产物(数据盘)           │  │
│  │ Q4_K_M.gguf (18.97GB)     │ llama.cpp/build/bin/      │  │
│  │ mtp-Q4_0.gguf (1.68GB)    │ llama-server (sm_120)     │  │
│  │ mmproj-Q8_0.gguf (0.63GB) │ 启动脚本 start_llama_     │  │
│  └───────────────────────────┴── server.sh / qwen38.     │  │
│                                 service / 模板           │  │
└─────────────────────────────────────────────────────────────┘
```

## 2. 模块划分与职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 一键部署 | `master_deploy.sh` | 下载 → 编译 → 模板 → key → systemd |
| 并行下载 | `scripts/parallel_dl.py` | ModelScope 16 线程分块下载 + 断点合并 |
| 启动脚本 | `scripts/start_llama_server.sh` | 带卡模式启动 llama-server |
| systemd | `deploy/qwen38.service` | 生产自启、崩溃自动重启 |
| 模板修复 | `scripts/extract_template.py` | GGUF 模板提取 + 两处修复 |
| 服务验证 | `scripts/verify.sh` | health/models/chat/responses/鉴权 |
| 本地对接 | `.env.example` | Hermes/Claude Code/Codex 三要素模板 |
| 部署文档 | `docs/DEPLOYMENT.md` | 完整部署与调优细节 |

## 3. 数据流 / 调用链路

### 请求链路
```
用户请求 → HTTPS → AutoDL 自定义服务 → llama-server (鉴权)
  → 加载 GGUF (Q4_K_M) + MTP 头 + mmproj
  → FlashAttention + KV 量化(q4_0) → 推测解码生成 → 返回
```

### 部署链路
```
SSH 到实例（无卡省钱）:
  [1] ModelScope 16 线程并行下载 GGUF/MTP/mmproj（~30-45 分钟）
  [2] 更新 llama.cpp → cmake (sm_120, stubs driver, 禁 UI) → -j1 编译
  [3] 提取并修复聊天模板（system 容忍 + 多轮 thinking 修复）
  [4] 切带卡 → 启动 llama-server（6006，6 key）
  [5] AutoDL 自定义服务 6006 → 公网 HTTPS
```

## 4. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 推理引擎 | llama.cpp llama-server | 旧项目已验证 sm_120 兼容最稳、长上下文最优 |
| 模型包 | ggml-org 官方 GGUF | 标准 K-quants + 独立 MTP 头 + mmproj，公开可下 |
| 量化 | Q4_K_M (18.97GB) | Q4 留足显存给 KV 缓存（131072 上下文） |
| 编译架构 | sm_120（CMAKE_CUDA_ARCHITECTURES=120） | RTX 5090 Blackwell 必须指定 |
| 编译并行 | 无卡 -j1 | cgroup 2GB 内存限制，单进程独占才不爆 |
| 链接 driver | toolkit stubs libcuda | 无卡 libcuda 是 0 字节空文件 |
| 下载 | ModelScope 16 线程 | 阿里云内网 5-10MB/s，比 hf-mirror 单连接快 10x |
| 模板 | GGUF 提取 + 修复 | 官方模板两个坑：system 位置检查、多轮空 thinking 块 |
| 多用户 key | `--api-key-file` | 一行一个 key，沿用旧 6 把 |
| 暴露 | AutoDL 自定义服务 | 自带 HTTPS，免备案，key 不裸奔 |
| 成本 | 无卡模式下载/编译 | 下模型/编译不用 GPU，省一半以上 |

## 5. 部署架构（目标状态）

- **数据盘** `/root/autodl-tmp`：模型 3 文件、llama.cpp、`.api_keys`、模板、日志
- **服务**：llama-server，`--host 0.0.0.0 --port 6006`
- **上下文**：`-c 131072` + `-ctk/-ctv q4_0`（混合注意力 KV 本身只有传统 1/4）
- **推理**：`-fa on` + MTP 推测解码 + `--reasoning off`
- **视觉**：`--mmproj` 加载，OpenAI 兼容 image_url 输入
- **公网**：AutoDL 自定义服务 6006 → 公网 HTTPS URL（沿用旧映射）
