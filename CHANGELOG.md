# Changelog

## [2026-08-23] 生产压测脚本 v1.3

- 新增 `scripts/bench_qwen_production.py`：统一口径测生产三大指标
  （TTFT 首 token 延迟 / 稳定输出 tok/s / 换页监控），跨 Linux(AutoDL)+macOS(M 系) 对齐
- key 读取优先级：`--key` > `QWEN38_API_KEY` > 服务器 `.api_keys` 首行
- 及格线参考：稳定输出 ≥ 20 tok/s、长输入 TTFT < 5s、测期换页 0 增长
- 配套交接：因此时正在**克隆到新服务器**，压测待新服务上线后跑；公网旧 URL 随克隆迁移

## [2026-08-20] 完整归档 v1.2 —— archive-20260820-v2

- 新增 `docs/FRIEND_SOP.md`（朋友版使用 SOP，key 占位符不入库）
- key 分发：朋友 D（user4）已交付，其余待发
- 技能配置：Codex 中恢复全部个人技能，删除 bailian-cli
- 归档标签：`archive-20260820-v2`（完整归档，状态冻结）

## [2026-08-20] 归档 v1.1 —— 部署 + ACP 全链路完成（archive-20260820）

- 服务端：默认 **262K 全功能档**（MTP + mmproj + 图片输入，实测 27.7GB）；
  512K + 视觉档备选（YaRN + 自定义补丁移除 capping，30.4GB）；1M 确认 32GB 卡不可行
- 图片输入双通道实测通过（chat/completions + responses API，Codex 路径）
- VS Code ACP 打通：config.toml provider + settings.json「Codex CLI (Qwen38)」+
  models.json 注册（消除 metadata 警告）+ profile 别名 codex-q38
- ACP 同会话三轮连续推理实测通过（thoughtTokens 0，多轮记忆完好）
- 归档标签：`archive-20260820`

## [2026-08-19] 初始发布 v1.0

- 新建项目：Qwen3.8-27B 单卡 RTX 5090 部署（llama.cpp llama-server + GGUF）
- 方案：官方 `ggml-org/Qwen3.8-27B-GGUF` Q4_K_M + MTP 头 + mmproj 视觉投影
- 关键升级（相对 qwen36-5090-deploy）：
  - llama.cpp 必须最新构建（qwen35 新架构）
  - ModelScope 16 线程并行下载器（`scripts/parallel_dl.py`）
  - 模板修复脚本（`scripts/extract_template.py`）：system 位置容忍 + 多轮空 thinking 块
  - systemd 服务适配 llama-server（`deploy/qwen38.service`）
- 文档 6 份：SPEC / ARCHITECTURE / DEPLOYMENT / TEST_PLAN / PITFALLS / PROGRESS
