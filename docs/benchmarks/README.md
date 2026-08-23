# 压测结果基准（benchmarks）

> 汇总入口 ｜ 最近一轮：2026-08-23（服务器克隆切换后新机实测）
> 打点脚本：`scripts/bench_qwen_production.py`（单流）、`scripts/bench_qwen_concurrency.py`（并发）

## 测试环境（2026-08-23）
- 主机：AutoDL RTX 5090 32GB（sm_120）｜ llama.cpp llama-server ｜ Qwen3.8-27B Q4_K_M
- 配置：262K 全功能档（MTP 推测解码 + mmproj 视觉 + `--reasoning off`）｜ 6 key 鉴权 ｜ 端口 6006
- 打点入口：内部 `127.0.0.1:6006`（无公网干扰）

## 结果文件
| 文件 | 内容 |
|---|---|
| [2026-08-23-single-stream.md](2026-08-23-single-stream.md) | 单流：短对话 + 长上下文（TTFT / 稳定 tok/s / 及格线） |
| [2026-08-23-concurrency.md](2026-08-23-concurrency.md) | 并发：`-np 1` vs `-np 2` 全表 + 「可同时几人」结论 |
| [DFLASH2_research.md](DFLASH2_research.md) | DFlash2 块扩散无损推测解码调研（加速技术，当前 RTX5090 不推荐、AppleSilicon/MLX 可用） |

## 一页速览
- **单用户性能优秀**：稳定输出 **75–94 tok/s**（短/长），TTFT p50 **0.14–0.30s**，远超标。
- **并发容量**：聚合 **~70 tok/s 封顶 = 显存带宽受限，非槽位数**；`-np 2` 不加总量、
  只降多用户排队延迟（2 并发 TTFT 2.06s→0.60s）。
- **可同时服务**：建议 **2–4 人**（2人34 / 4人16.6 tok/s）；每人共享 ~70 tok/s 的带宽。

## 复现
```bash
python scripts/bench_qwen_production.py -n 5           # 单流短
python scripts/bench_qwen_production.py -n 3 --long    # 单流长
python scripts/bench_qwen_concurrency.py -c 1 2 4 6 8 -n 2   # 并发
```