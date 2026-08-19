# Qwen3.8-27B 单卡 RTX 5090 生产部署

在 **AutoDL RTX 5090（32GB）单卡** 上，用 **llama.cpp llama-server + GGUF** 部署
**Qwen3.8-27B**，提供生产级 OpenAI 兼容 API（`/v1/chat/completions`、
`/v1/responses`、`/v1/models`、`/health`），供本地 Hermes / Claude Code /
Codex / 自研工具调用，支持**多用户（每人一个 API key）**。

> 本仓库是旧项目 `qwen36-5090-deploy` 的升级版。3.8 是全新的混合注意力
> 架构（`qwen35` GGUF 架构），**llama.cpp 必须用发布后的最新构建**，旧二进制
> 直接报架构错误。

## 方案要点

- **引擎**：llama.cpp llama-server（Blackwell sm_120 兼容最稳，长上下文最优）
- **模型**：官方 `ggml-org/Qwen3.8-27B-GGUF` Q4_K_M（18.97GB，标准 K-quants）
- **MTP 推测解码**：`mtp-Qwen3.8-27B-Q4_0.gguf` + `--spec-type draft-mtp`，单用户提速 ~1.5x
- **多模态**：`mmproj-Qwen3.8-27B-Q8_0.gguf` 视觉投影器（可选，默认加载）
- **上下文**：默认 **262K**（原生）+ MTP + mmproj 全功能（图片输入实测通过）；
  另有 **512K + 视觉档**（YaRN 扩长，无 MTP，见 `start_llama_server_512k.sh`）
- **暴露**：AutoDL 自定义服务公网 HTTPS URL + API Key 鉴权（`.api_keys` 每行一把）
- **成本策略**：无卡模式下并行下载 + 编译，运行才带卡
- **thinking 关闭**：`--reasoning off` + 修复后的官方模板（零思考消耗）

## 与 Qwen3.6 部署的差异

| 项 | Qwen3.6（旧仓库） | Qwen3.8（本仓库） |
|---|---|---|
| GGUF 架构 | qwen3 | **qwen35（新，需最新 llama.cpp）** |
| 注意力 | 全注意力 | 16/64 层全注意力 + 48 层 Gated DeltaNet，KV 缓存约为传统 1/4 |
| 上下文 | 131072 | 默认 262144 全功能（MTP+mmproj+图片）；512K+视觉档可选 |
| 推测解码 | 无 | MTP 头（ggml-org 包自带） |
| 多模态 | 无 | mmproj 视觉投影器（约 0.63GB） |
| 模板坑 | system 位置检查 | system 位置检查 + **多轮空 thinking 块**（已修） |
| 下载 | hf-mirror 单连接 curl（~700KB/s） | **ModelScope 16 线程并行（5-10MB/s）** |

## 快速开始

### 1. 租卡（AutoDL 控制台）

- GPU：RTX 5090（32GB）× 1
- 镜像：CUDA 12.8+（sm_120 必需）
- 先切**无卡模式**再下载/编译（省 GPU 计费），运行前切带卡

### 2. 下载模型（无卡模式）

```bash
cd /root/autodl-tmp/models
/root/miniconda3/bin/python parallel_dl.py --jobs 16
```

或单连接 curl（hf-mirror，慢但可断点续传）：

```bash
curl -L -C - -o Qwen3.8-27B-Q4_K_M.gguf \
  https://hf-mirror.com/ggml-org/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-Q4_K_M.gguf
```

### 3. 编译（无卡模式）

```bash
cd /root/autodl-tmp/llama.cpp
git fetch --depth 1 origin master && git checkout -f FETCH_HEAD
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=OFF -DGGML_CCACHE=OFF \
  -DCUDA_cuda_driver_LIBRARY=/usr/local/cuda/lib64/stubs/libcuda.so \
  -DCMAKE_EXE_LINKER_FLAGS="-lcuda -L/usr/local/cuda/lib64/stubs" -DLLAMA_BUILD_UI=OFF
cmake --build build --config Release -j1 --target llama-server
```

> 无卡模式 cgroup 内存只有 2GB，必须 `-j1`；`-j4` 以上会被 OOM 杀进程。

### 4. 模板（无卡模式）

```bash
/root/miniconda3/bin/python -m pip install gguf
/root/miniconda3/bin/python scripts/extract_template.py \
  /root/autodl-tmp/models/Qwen3.8-27B-Q4_K_M.gguf /root/autodl-tmp/qwen38_template.jinja
```

### 5. 启动（带卡模式）

```bash
bash /root/autodl-tmp/start_llama_server.sh   # 262K 全功能档（6 key 鉴权，端口 6006）
# 或最大上下文（512K + 视觉，无 MTP）：
bash /root/autodl-tmp/scripts/start_llama_server_512k.sh
```

### 6. 验证

```bash
bash scripts/verify.sh
curl http://127.0.0.1:6006/health
curl http://127.0.0.1:6006/v1/models -H "Authorization: Bearer $KEY"
curl http://127.0.0.1:6006/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"你好"}]}'
```

### 7. 生产化

- **公网暴露**：AutoDL 控制台「自定义服务」把 6006 映射为公网 HTTPS URL
- **自启/崩溃重启**：AutoDL 容器无 systemd（PID 1 = bash），
  请在 AutoDL 控制台配置开机自启（执行 `bash /root/autodl-tmp/start_llama_server.sh`）；
  标准 Linux 服务器可用 `deploy/qwen38.service`（`systemctl enable --now qwen38`）
- **本地对接**：复制 `.env.example` → `.env`，填公网 URL 和 key，
  Hermes / Claude Code 用 `base_url + api_key + model=qwen3.8-27b` 直连

### 8. VS Code ACP（Codex 面板，实测通过）

`~/.codex/config.toml` 新增 provider：

```toml
[model_providers.qwen38]
name = "Qwen3.8-27B (AutoDL RTX5090)"
wire_api = "responses"
base_url = "https://<你的AutoDL公网URL>/v1"
experimental_bearer_token = "<.api_keys 里的一把 key>"
```

VS Code `settings.json` → `acp.agents` 新增（改后 `Developer: Reload Window`，
ACP 面板选「Codex CLI (Qwen38)」）：

```json
"Codex CLI (Qwen38)": {
  "command": "codex-acp",
  "args": [],
  "env": {
    "MODEL_PROVIDER": "qwen38",
    "CODEX_CONFIG": "{\"model\":\"qwen3.8-27b\",\"model_provider\":\"qwen38\"}"
  }
}
```

已实测：同一 ACP 会话三轮连续提问，上下文完整保留（记住信息→跨轮复述），
`thoughtTokens: 0`，无思考垃圾文本（qwen3.6 的「无法连续推理」已修复）。

## 项目结构

```
qwen38-5090-deploy/
├── master_deploy.sh            # 一键部署（下载→编译→模板→key→systemd）
├── deploy/
│   └── qwen38.service          # systemd 自启服务（llama-server 版本）
├── scripts/
│   ├── parallel_dl.py          # ModelScope 16 线程并行下载器
│   ├── extract_template.py     # GGUF 模板提取 + 两处修复
│   ├── start_llama_server.sh   # 启动脚本（MTP + mmproj + 多 key）
│   └── verify.sh               # 服务验证（health/models/chat/responses/鉴权）
├── .env.example                # 本地对接配置模板
└── docs/                       # SPEC/ARCHITECTURE/DEPLOYMENT/TEST_PLAN/PITFALLS/PROGRESS
```

## 性能调优要点

- `-fa on`：Flash Attention，30 系及以上必开，约 3x 提速、省 40% 显存
- `-ngl 999`：全层下 GPU
- `-ctk/-ctv q4_0`：KV 缓存量化到 1/4，长上下文核心
- MTP（`--spec-type draft-mtp`）：单用户最高 ~1.5x；高并发建议关闭
- `--reasoning off` + 修复模板：Codex 等 Agent 零思考消耗

## 上下文档位与显存（RTX 5090 32GB 实测）

| 档位 | 配置 | 显存 | 特性 |
|------|------|------|------|
| **262K 全功能（默认）** | `-c 262144` + MTP + mmproj | ~27.7GB | 推测解码 + 视觉（图片实测通过） |
| 512K + 视觉 | `-c 524288` + YaRN + mmproj（无 MTP） | ~30.4GB | 最大上下文 + 视觉 |
| 1M | YaRN factor 4 | >38GB ❌ | 32GB 卡装不下（需 48GB+ 或 IQ2 低质量量化） |

> 512K 需要自定义补丁：llama-server 默认把槽位上下文封顶在模型训练长度（262K），
> 本仓库已打补丁移除该上限（见 PITFALLS #31）。

## 备份 / 兜底

- 无卡模式仅能下载/编译，**运行必须切带卡**（无卡 driver 是 0 字节 stub）
- 完整方案与踩坑见 `docs/DEPLOYMENT.md`、`docs/PITFALLS.md`

## License

MIT
