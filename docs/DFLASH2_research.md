# DFlash2（DFlash 块扩散推测解码）调研评估

> 版本：v1.0 ｜ 2026-08-23 ｜ qwen38-5090-deploy 续接调研
> 结论先行：**当前 RTX 5090 + llama.cpp 生产线不推荐硬上 DFlash2**；若未来用 Apple Silicon 走 MLX 后端则是明确可用的无损提速手段。

## 1. 它是什么

**DFlash**（[z-lab/dflash](https://github.com/z-lab/dflash)，5884★，[论文 arXiv:2602.06036](https://arxiv.org/abs/2602.06036)，官方 [Blog](https://z-lab.ai/projects/dflash/)）是一种基于 **Block Diffusion（块扩散）** 的**无损推测解码**（speculative decoding）技术：
- 用一个小草稿模型并行批量推测下一段 token，再用目标模型逐 token 验证；
- 验证通过的 token 无偿生效，质量与单步自回归完全一致（**无损**）；
- 实测约 **3–8 倍**加速（比传统 MTP 的 ~1.5x 更强）。

**DFlash 2** 在 DFlash 基础上新增「grouped dynamic depthwise convolution + candidate selector」两个模块，进一步提速。当前可用 checkpoint 仅两个：**[Muse-Glimmer-30B](https://huggingface.co/z-lab/Muse-Glimmer-30B-DFlash2)** 和 **[Qwen3.8-27B](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2)**。

## 2. 关键：DFlash2 官方点名支持我们部署的 Qwen3.8-27B

DFlash2 首发只支持两个模型，其中就有 **Qwen3.8-27B**（本项目部署的正是它）。llama.cpp 的 DFlash2 支持 PR（[ggml-org/llama.cpp#27342](https://github.com/ggml-org/llama.cpp/pull/27342)）正文实测即 **Qwen3.8-27B Q4_K_M**——与我们的部署一字不差。说明 DFlash2 一代就是为这类混合注意力（Gated DeltaNet）模型优化的，不是凑数。

## 3. 后端支持矩阵 → 决定「在哪能用」

| 后端 | Qwen3.8-27B DFlash2 | 说明 |
|---|---|---|
| **MLX（Apple Silicon）** | ✅ 官方支持 | 作者实测路径（内置 `dflash[local]`） |
| **Transformers（Linux）** | ❌ 仅列 Muse-30B | Linux 下 Qwen3.8 非首选 |
| **SGLang / vLLM（NVIDIA serving）** | ✅ 走 server | NVIDIA 加速路径在这（NVIDIA 官方参与） |
| **llama.cpp** | ⚠️ PR #27342 **未合并**(open) | 实测仅 Apple M5 Pro，无 CUDA/sm_120 验证 |

> 本地推理依赖：MLX（Apple Silicon）+ Transformers（Linux）。NVIDIA 上经 vLLM PR [#52816](https://github.com/vllm-project/vllm/pull/52816) / SGLang PR [#35371](https://github.com/sgl-project/sglang/pull/35371)。

## 4. 对当前 RTX 5090 + llama.cpp 的可用性评估

**结论：不可直接即插即用，不推荐硬上。**

1. **llama.cpp 的 DFlash2 还在 open PR**：`llama.cpp#27342` 未合并进 main，我们 8/19-20 编译的 llama-server（为 qwen35 架构）没有它。
2. **NVIDIA 路径与我们的 sm_120 决策冲突**：DFlash2 在英伟达上走 **vLLM/SGLang**（NVIDIA 工程师贡献，瞄准 DGX Spark sm_121a）。而这台 RTX 5090 当初正是**因 vLLM+NVFP4/FlashInfer 不兼容 sm_120 才弃 vLLM 转 llama.cpp**（见 `PITFALLS.md` #9）。为上 DFlash2 回头跑 vLLM/SGLang，等于把当初的坑重新踩回，混合注意力在 sm_120 上正是难点。
3. **llama.cpp PR 的 CUDA/sm_120 未证实**：作者只在 Apple M5 Pro 上实测（Q4_K_M 64GB），N 卡没人验证。

## 5. 推荐路径

- **现在（RTX 5090 + llama.cpp）**：维持 llama.cpp + MTP（`--spec-type draft-mtp`）现状。MTP 单用户约 1.5x，配合 KV 量化 + 关口思考，生产已实测 75–94 tok/s（见 `bench_qwen_production.py` 基线）。
- **未来换 Apple Silicon（Mac/Metal）**：DFLASH2 是明确最优解——MLX 后端官方支持 Qwen3.8-27B-DFlash2，作者在 Apple M5 Pro 上实测，`pip install "dflash[local]"` + `dflash generate mlx --model ... --draft z-lab/Qwen3.8-27B-DFlash2 ...` 即可。可比 MTP 的 1.5x 提升到 3–8x 无损。
- **非 sm_120 的 NVIDIA（H20/H100/A100）**：走 vLLM/SGLang 用 DFlash2 可行（两个 PR 已提供 OpenAI 兼容服务接入）。

## 6. 后续更新检查点

- `llama.cpp#27342` 何时合并进 main、是否补 CUDA/sm_120 支持与验证；
- `z-lab/Qwen3.8-27B-DFlash2` 是否发布 GGUF 版草稿（当前 README 走 MLX/Transformers/vLLM 加载）；
- DFlash2 collection 是否扩充模型。

## 相关

- 本项目：`qwen38-5090-deploy`（部署方案见 README / DEPLOYMENT.md，踩坑见 PITFALLS.md）
- 生产压测脚本：`scripts/bench_qwen_production.py`（TTFT / 稳定 tok/s / 换页）
- 记忆：`qwen38-clone-switch-20260823`