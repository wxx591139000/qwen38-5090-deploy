# 项目推进进度 PROGRESS

> 版本：v1.0 ｜ 2026-08-19

## 1. 里程碑回顾

| 里程碑 | 状态 |
|--------|------|
| 阅读旧项目 qwen36-5090-deploy，确定升级路线 | ✅ |
| Qwen3.8-27B 方案确认（ggml-org GGUF + MTP + mmproj） | ✅ |
| 本地项目脚手架（脚本/文档/systemd/env） | ✅ |
| 服务器无卡模式：并行下载模型（ModelScope 16 线程） | 🔄 下载中 |
| 服务器无卡模式：llama.cpp 更新 + sm_120 编译 | ⏳ 待下载完成 |
| 模板提取修复 + 启动脚本 + key 配置 | ⏳ |
| 切带卡：启动 llama-server + 端到端验证 | ⏳ 依赖用户切带卡 |
| 公网暴露确认（AutoDL 自定义服务 6006） | ⏳ 依赖控制台 |
| GitHub 推送 | ⏳ |

## 2. 已完成功能清单

- ✅ `scripts/parallel_dl.py`：ModelScope 16 线程并行下载器（断点分块合并）
- ✅ `master_deploy.sh`：一键部署（下载→编译→模板→key→systemd）
- ✅ `scripts/extract_template.py`：模板提取 + system 位置容忍 + 多轮空 thinking 修复
- ✅ `scripts/start_llama_server.sh`：MTP + mmproj + 多 key + reasoning off
- ✅ `deploy/qwen38.service`：systemd 自启（llama-server 版本，旧项目缺口已补）
- ✅ `scripts/verify.sh`：health/models/chat/responses/鉴权验证
- ✅ 文档 6 份 + README + CHANGELOG

## 3. 进行中 / 待办

- [ ] 服务器下载完成（Q4_K_M 18.97GB + MTP 1.68GB + mmproj 0.63GB）
- [ ] llama.cpp 最新版 sm_120 编译（无卡 -j1）
- [ ] 模板提取修复 + 上传启动脚本 + systemd 安装
- [ ] 用户切带卡 → 启动 → `verify.sh` 端到端验证
- [ ] 公网 URL 确认（AutoDL 自定义服务）
- [ ] 分发给朋友：每人一把 key + base_url + model

## 4. Roadmap

- 近期：高并发压测、262144 长上下文实测、MTP 开关收益对比
- 中期：用量监控/成本告警、每用户限流（人多则上 LiteLLM 网关）
- 长期：更大精度档位（Q5_K_M/Q8_0）、多实例扩展
