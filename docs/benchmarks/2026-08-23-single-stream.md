# 压测：单流（短对话 + 长上下文）

> 2026-08-23 ｜ RTX 5090 32GB ｜ Qwen3.8-27B Q4_K_M ｜ 262K 全功能档（MTP + mmproj）
> 脚本：`scripts/bench_qwen_production.py`

## 1. 短对话（`-n 5`，max_tokens=800）

| 指标 | p50 | p95 |
|---|---|---|
| **TTFT（首 token）** | 0.30s | 0.33s |
| **稳定输出 tok/s** | **75.2** | 78.6 |
| 平均输出长度 | 607 tok/次 | — |

逐次明细：

```
[1] TTFT 0.26s  输出 632tok  稳定 74.1 tok/s
[2] TTFT 0.24s  输出 657tok  稳定 78.6 tok/s
[3] TTFT 0.33s  输出 551tok  稳定 75.2 tok/s
[4] TTFT 0.31s  输出 585tok  稳定 76.4 tok/s
[5] TTFT 0.30s  输出 614tok  稳定 73.5 tok/s
```

## 2. 长上下文（`-n 3 --long`，近 262K prefill 负载）

| 指标 | p50 | p95 |
|---|---|---|
| **TTFT** | 0.14s | 0.87s |
| **稳定输出 tok/s** | **93.7** | 97.5 |
| 平均输出长度 | 800 tok/次 | — |

逐次明细：

```
[1] TTFT 0.87s  输出 800tok  稳定 86.6 tok/s
[2] TTFT 0.14s  输出 800tok  稳定 97.5 tok/s
[3] TTFT 0.12s  输出 800tok  稳定 93.7 tok/s
```

## 3. 及格线判定

| 线 | 阈值 | 短对话 | 长上下文 | 判定 |
|---|---|---|---|---|
| 稳定输出 | ≥ 20 tok/s | 75.2 | 93.7 | ✅ |
| 长输入 TTFT | < 5s | — | p95 0.87s | ✅ |
| 测期换页 | 0 增长 | 0 | 0 | ✅ |

> MTP 冒烟：`draft_n:7, draft_n_accepted:6`，`predicted_per_second: 78.2`（MTP 推测解码生效）。