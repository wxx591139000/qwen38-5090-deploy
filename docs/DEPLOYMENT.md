# 部署文档 Qwen3.8-27B 单卡 RTX 5090

> 目标：AutoDL 租 1×RTX 5090（32GB），提供 OpenAI 兼容 LLM 服务，供本人 +
> 几个朋友调用。承接旧项目 qwen36-5090-deploy 的已验证路线（llama.cpp GGUF）。

## 1. 模型与显存账本

| 文件 | 大小 | 说明 |
|------|------|------|
| Qwen3.8-27B-Q4_K_M.gguf | 18.97GB | 主模型（标准 K-quants） |
| mtp-Qwen3.8-27B-Q4_0.gguf | 1.68GB | MTP 推测解码头 |
| mmproj-Qwen3.8-27B-Q8_0.gguf | 0.63GB | 视觉投影器（可选） |

32GB 显存账本（Q4_K_M，全部实测）：
- 权重 ≈ 19GB + MTP 头 ≈ 1.7GB + mmproj ≈ 1GB ≈ **21.7GB**
- KV（q4_0，实测）：131K ≈ 1.9GB、262K ≈ 3.7GB、512K ≈ 7.4GB
- **262K 全功能档（默认）**：MTP + mmproj 全开 ≈ **27.7GB**（图片输入实测通过）
- **512K + 视觉档**：YaRN + mmproj（无 MTP）≈ **30.4GB**（MTP 的 KV 会翻倍导致 OOM）
- 1M：≈38GB，32GB 卡装不下（需 48GB+ 或降到 IQ2 量化）

## 2.5 512K 自定义补丁（必须）

llama-server 默认把槽位上下文封顶在模型训练长度（262144），即使 `-c 524288` 也只给 262K。
已修改 `tools/server/server-context.cpp` 移除该封顶（配合 YaRN 扩长）并重新编译：

```bash
# 改动点：把 capping 分支改为仅告警，不再截断 n_ctx_slot
cd /root/autodl-tmp/llama.cpp
cmake --build build --config Release -j8 --target llama-server
```

## 2. 关键前提

- **llama.cpp 必须最新构建**：Qwen3.8 注册了新 GGUF 架构（qwen35），
  发布周（2026-08-14）之前的构建加载直接报架构错误
- CUDA 12.8+（sm_120 必需）
- 无卡模式 cgroup 内存 2GB：编译必须 `-j1`

## 3. 部署步骤（无卡模式，省一半 GPU 费）

### 3.1 并行下载模型（ModelScope，阿里云内网快）

```bash
mkdir -p /root/autodl-tmp/models
cd /root/autodl-tmp/models
# 上传 scripts/parallel_dl.py 后：
/root/miniconda3/bin/python parallel_dl.py --jobs 16
```

兜底：hf-mirror 单连接 curl（-C - 断点续传）。

### 3.2 更新并编译 llama.cpp

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

### 3.3 提取并修复聊天模板

```bash
/root/miniconda3/bin/python -m pip install gguf
/root/miniconda3/bin/python scripts/extract_template.py \
  /root/autodl-tmp/models/Qwen3.8-27B-Q4_K_M.gguf /root/autodl-tmp/qwen38_template.jinja
```

两处修复：① system 位置检查 → 容忍；② 多轮空 thinking 块 → 仅 reasoning 非空才包裹。

### 3.4 API keys

沿用旧 6 把 key（`/root/autodl-tmp/.api_keys`，每行一个）。
新增：`openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 48`，`sk-` 前缀。

### 3.5 切带卡，启动

```bash
bash /root/autodl-tmp/start_llama_server.sh   # 262K 全功能档（默认）
# 或：bash /root/autodl-tmp/scripts/start_llama_server_512k.sh  # 512K + 视觉
tail -f /root/autodl-tmp/llama_server.log
```

### 3.51 图片输入验证（2026-08-20 实测）

```bash
# 生成纯色测试图并走 chat/completions（蓝色图 → "图片里是蓝色的"）
# 走 Codex 的 responses API（红色图 → "图片是红色"）同样通过
```

图片以 OpenAI 兼容 `image_url`（data URI）传入即可；`/v1/models` capabilities 显示
`["completion","multimodal"]`。

### 3.6 验证

```bash
bash scripts/verify.sh
```

### 3.7 生产化

- **AutoDL 容器无 systemd**（PID 1 = bash，`systemctl` 不可用）：
  - 手动启动：`bash /root/autodl-tmp/start_llama_server.sh`
  - 开机自启：AutoDL 控制台配置（切带卡后自动执行启动脚本）
- **标准 Linux 服务器**：`cp deploy/qwen38.service /etc/systemd/system/ && systemctl enable --now qwen38`
- 公网：AutoDL「自定义服务」把 6006 映射为公网 HTTPS URL（沿用旧映射端口）

## 4. 性能调优

| 手段 | 效果 |
|------|------|
| `-fa on` | 提速 ~3x、省 40% 显存 |
| MTP `--spec-type draft-mtp` | 单用户 ~1.5x |
| KV 量化 `-ctk/-ctv q4_0` | KV 缓存 1/4，长上下文核心 |
| `--reasoning off` | Agent 零思考消耗 |

**MTP 边界**：单用户收益最大；并发高时建议关闭（`-md` 去掉）。

## 5. 成本

- RTX 5090 按量租，价格以控制台实时为准
- 无卡模式下载/编译省一半
- 用完即停，模型在数据盘 `/root/autodl-tmp` 不丢
