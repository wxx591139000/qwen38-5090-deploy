# 项目踩坑记录 PITFALLS

> 版本：v1.0 ｜ 2026-08-19 ｜ 含旧项目经验（前 21 条）与新项目新增

格式：`[日期] 问题描述 → 原因 → 解决/规避方案`

## 新增（Qwen3.8 专属）

### 22. [2026-08-19] 旧 llama.cpp 构建直接拒绝 Qwen3.8 模型
Qwen3.6 时代编译的 llama-server（2026-08-06）加载 Qwen3.8 GGUF 报架构错误。
→ Qwen3.8 注册了新 GGUF 架构（qwen35），发布周之前的构建不认识。
→ **llama.cpp 必须更新到发布后最新 master 再编译**（bartowski 等量化包要求 b10419+）。

### 23. [2026-08-19] 官方聊天模板多轮对话「失忆」
官方 Jinja 模板把每个历史 assistant 轮次都包成 `<think>..</think>`，即使
reasoning_content 为空 → 多轮后嵌套空 thinking 块、历史被截断，模型像忘了
之前的对话。
→ `scripts/extract_template.py` 修复：仅当 reasoning_content 非空才包
`<think>` 块（同时保留工具调用 reasoning）。

### 24. [2026-08-19] hf-mirror 单连接下载太慢（~700KB/s，19GB 要 7 小时）
AutoDL 到 hf-mirror 的 CDN 单连接限速严重，且不支持 Range（并行分块无效）。
→ 换 **ModelScope**（阿里云内网）：CDN 支持 Range 请求，
`scripts/parallel_dl.py` 16 线程并行分块下载，实测 5-10MB/s。

### 25. [2026-08-19] 无卡模式内存墙：下载器 + 编译同时跑会 OOM
cgroup `memory.max=2GB` 是容器全局限制，16 线程下载器 + jupyter 等已占满
2GB，此时编译 cc1plus 直接被杀。
→ **下载完成后再编译，严格串行**。

### 26. [2026-08-19] ModelScope 模型文件路径与 HF 不同
ModelScope 上 GGUF 镜像仓库存在（`ggml-org/Qwen3.8-27B-GGUF`），但
`resolve/master/<file>` 实际是 302 到带 auth_key 的 CDN URL；HEAD 看不到
Content-Length，直接测速会被误导。
→ 用 API 端点 `https://modelscope.cn/api/v1/models/<repo>/repo?Revision=master&FilePath=<file>`
（每次重定向拿新 auth_key，分块下载不受 token 过期影响）。

## 旧项目经验（沿用）

### 1. [2026-08-06] conda libmamba solver 缺陷
AutoDL 镜像 conda 装包报 solver 错误 → 改用 venv / 直接 `/root/miniconda3/bin/python`。

### 2-8. 模型仓库选择 / modelscope API / 克隆不完整 / 密钥清理 / scp 密钥
（详见旧仓库 qwen36-5090-deploy，此处不再展开）

### 9. [2026-08-07] vLLM + NVFP4 与 Blackwell sm_120 不兼容（方案转向根因）
FlashInfer 不支持 sm_120 → 弃 vLLM，llama.cpp + GGUF 为最终方案（沿用）。

### 10. [2026-08-07] unsloth auth-gated 404
→ 用官方 `ggml-org` 公开仓库。

### 11. [2026-08-07] 无卡 cgroup 2GB 内存，编译大文件被杀
→ `-j1 --target llama-server`。

### 12. [2026-08-07] nvcc 不在 PATH
→ cmake 显式 `-DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc`。

### 13. [2026-08-07] `-j$(nproc)` 进程数超限被杀
→ 降并行度。

### 14. [2026-08-07] 双编译互删 build 目录
→ 先 `kill -9` 清残留再启动单一编译。

### 15. [2026-08-07] 链接 libggml-cuda 报 cuMemCreate 等 undefined
→ 用 toolkit stubs：`-DCUDA_cuda_driver_LIBRARY=/usr/local/cuda/lib64/stubs/libcuda.so`
+ `-DCMAKE_EXE_LINKER_FLAGS="-lcuda -L/usr/local/cuda/lib64/stubs"`。

### 16. [2026-08-07] 构建卡 "Provisioning UI assets" 下载超时
→ `-DLLAMA_BUILD_UI=OFF`。

### 17. [2026-08-07] 无卡运行 libcuda.so.1: file too short
→ 运行必须切带卡模式。

### 18. [2026-08-07] llama-server 多 key 用 `--api-key-file`
→ `.api_keys` 每行一个，`#` 注释。

### 19. [2026-08-07] Codex 0.146+ 必须 `wire_api="responses"`
→ llama-server `/v1/responses` 端点支持（新版继续验证）。

### 20. [2026-08-07] `--reasoning off` 需 llama.cpp 识别 reasoning 能力
→ 用原版模板（含 thinking 控制）去掉 system 位置检查，`--reasoning off` 才生效。
Qwen3.8 继续沿用此策略（模板修复见 23）。

### 21. [2026-08-07] base64 传 jinja 模板引号损坏
→ 模板用文件方式写入，避免多层 shell 引号嵌套。
