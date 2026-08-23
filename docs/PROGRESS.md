# 项目推进进度 PROGRESS

> 版本：v1.2 ｜ 2026-08-23 ｜ 加并发压测 + `-np 2` 实测；服务器已克隆切换(weste:15844)

> **已归档**：`archive-20260820`（2026-08-20）——部署 + ACP 接入全链路完成，进入使用维护期

## 1. 里程碑回顾

| 里程碑 | 状态 |
|--------|------|
| 阅读旧项目 qwen36-5090-deploy，确定升级路线 | ✅ |
| Qwen3.8-27B 方案确认（ggml-org GGUF + MTP + mmproj） | ✅ |
| 本地项目脚手架（脚本/文档/systemd/env） | ✅ |
| GitHub 仓库推送（wxx591139000/qwen38-5090-deploy） | ✅ |
| 服务器无卡模式：并行下载模型（ModelScope 16 线程） | 🔄 下载中（~26%） |
| 服务器无卡模式：llama.cpp 更新（github 直连超时 → 本地 tarball 上传） | ✅ |
| 模型下载完成（Q4_K_M 18.97GB + MTP 1.68GB + mmproj 0.63GB，大小全部校验） | ✅ |
| 模板提取修复（qwen38_template.jinja，两处修复已应用） | ✅ |
| 服务器无卡模式：llama-server sm_120 编译 | ✅ 03:18 完成（-j3 + 97% 时 server-task OOM 后 -j2 续跑） |
| CPU 版全量验证 | ❌ 19GB 模型在 2GB cgroup 下加载被 SIGKILL（页缓存反复回收），改由 GPU 模式验证 |
| 启动脚本 + key 配置（沿用 6 把）+ qwen38.service 安装 | ✅（AutoDL 无 systemd，改用控制台/脚本自启） |
| 二进制验证（ldd 无缺失、CUDA 库 61MB、无卡报 libcuda stub = 正常） | ✅ |
| 切带卡：启动 llama-server（6006 + 公网 8443）+ 端到端验证 | ✅ |
| 多轮连续推理（chat/completions 三轮跨轮记忆 + system 中间容忍） | ✅ |
| Responses API（Codex wire_api=responses 用） | ✅ |
| codex exec 多步代理循环（写文件→读文件→回答） | ✅ |
| VS Code ACP 握手 + 同一会话三轮连续对话（ACP 协议实测） | ✅ thoughtTokens:0 |
| 本地配置：config.toml qwen38 provider + VS Code「Codex CLI (Qwen38)」 | ✅ |
| 512K 上下文（YaRN + 自定义补丁移除 capping）实测通过（n_ctx 524288） | ✅ |
| 262K 全功能档（MTP + mmproj）实测：显存 27.7GB，图片输入 chat/responses 双通道通过 | ✅ |
| 512K + 视觉档实测：显存 30.4GB，capabilities 含 multimodal | ✅ |
| 公网暴露确认（AutoDL 自定义服务 6006） | ⏳ 依赖控制台 |

## 2. 已完成功能清单

- ✅ `scripts/parallel_dl.py`：ModelScope 16 线程并行下载器（断点分块合并）
- ✅ `master_deploy.sh`：一键部署（下载→编译→模板→key→systemd）
- ✅ `scripts/extract_template.py`：模板提取 + system 位置容忍 + 多轮空 thinking 修复
- ✅ `scripts/start_llama_server.sh`：MTP + mmproj + 多 key + reasoning off
- ✅ `deploy/qwen38.service`：systemd 自启（llama-server 版本，旧项目缺口已补）
- ✅ `scripts/verify.sh`：health/models/chat/responses/鉴权验证
- ✅ `scripts/bench_qwen_production.py`：生产压测（TTFT / 稳定 tok/s / 换页），
  跨 AutoDL(Linux)+未来 Mac(Metal) 统一口径，及格线 20 tok/s 且长输入 TTFT<5s
- ✅ 文档 6 份 + README + CHANGELOG
- ✅ GitHub：`https://github.com/wxx591139000/qwen38-5090-deploy`（public, master）
- ✅ llama.cpp 更新到最新 master（github.com 直连超时，本地下载 tarball 后 SFTP 上传）
- ✅ 参数确认：`--spec-type draft-mtp` / `-md` / `--mmproj` / `--reasoning off`
  （`--reasoning off` 会向模板传 `enable_thinking=false`，与模板修复方案吻合）

## 3. 进行中 / 待办

- [ ] 服务器下载完成（Q4_K_M 18.97GB + MTP 1.68GB + mmproj 0.63GB）
- [ ] llama.cpp 最新版 sm_120 编译（无卡 -j1）
- [ ] 模板提取修复 + 上传启动脚本 + systemd 安装
- [ ] 用户切带卡 → 启动 → `verify.sh` 端到端验证
- [ ] 公网 URL 确认（AutoDL 自定义服务）
- [ ] 分发给朋友：每人一把 key + base_url + model
- [ ] **服务器已克隆切换（2026-08-23）**：新实例 weste:15844，别名 `autodl-5090` 已 repoint；
     服务已带卡跑通，生产压测（短/长/并发）✅
- [ ] **并发容量结论（-np 1 实测后二次修正）**：聚合 ~70 tok/s 封顶 = **显存带宽受限**，
     非槽位数；`-np 2`@262K 总池=2×131K，**不加总量、只降排队延迟(TTFT)**，
     显存 28GB 安全。真正提吞吐只能换更快卡/更小模型/名校准，多槽只是减延迟。
     `scripts/bench_qwen_concurrency.py` + `scripts/start_llama_server_np2.sh` 已加
- [ ] 公网 URL 待新实例控制台映射 6006 后更新（config.toml/FRIEND_SOP/.env）

## 4. Roadmap

- 近期：高并发压测、262144 长上下文实测、MTP 开关收益对比
- 中期：用量监控/成本告警、每用户限流（人多则上 LiteLLM 网关）
- 长期：更大精度档位（Q5_K_M/Q8_0）、多实例扩展
