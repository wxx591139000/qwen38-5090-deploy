# Changelog

## [2026-08-19] 初始发布 v1.0

- 新建项目：Qwen3.8-27B 单卡 RTX 5090 部署（llama.cpp llama-server + GGUF）
- 方案：官方 `ggml-org/Qwen3.8-27B-GGUF` Q4_K_M + MTP 头 + mmproj 视觉投影
- 关键升级（相对 qwen36-5090-deploy）：
  - llama.cpp 必须最新构建（qwen35 新架构）
  - ModelScope 16 线程并行下载器（`scripts/parallel_dl.py`）
  - 模板修复脚本（`scripts/extract_template.py`）：system 位置容忍 + 多轮空 thinking 块
  - systemd 服务适配 llama-server（`deploy/qwen38.service`）
- 文档 6 份：SPEC / ARCHITECTURE / DEPLOYMENT / TEST_PLAN / PITFALLS / PROGRESS
