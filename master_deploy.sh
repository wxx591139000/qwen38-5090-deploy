#!/usr/bin/env bash
# ============================================================
# Qwen3.8-27B 单卡 RTX 5090 一键部署脚本（llama.cpp llama-server + GGUF）
# 在 AutoDL RTX 5090 (32GB) 实例上执行，推荐「无卡模式」运行本脚本
# （下载/编译不用 GPU，切带卡前先做完，省一半以上 GPU 计费）。
#
# 流程:
#   [1] 并行下载 GGUF 模型（ModelScope，16 线程）
#   [2] 更新 llama.cpp 到最新并编译 llama-server（sm_120, 无卡 -j1）
#   [3] 从 GGUF 提取并修复聊天模板（多轮 thinking 坑 + system 位置容忍）
#   [4] 准备 .api_keys / 启动脚本
#   [5] 安装 systemd 服务（自启 + 崩溃重启）
#
# 用法:
#   bash master_deploy.sh
# ============================================================
set -euo pipefail

BASE=/root/autodl-tmp
MODEL_DIR=$BASE/models
LLAMA_DIR=$BASE/llama.cpp
PORT=6006
SERVER_NAME=qwen3.8-27b
PY="${PYTHON:-/root/miniconda3/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"

step() { echo "==> $*"; }

step "[1/5] 下载 GGUF 模型（Q4_K_M + MTP 头 + mmproj 视觉投影）"
mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL_DIR/parallel_dl.py" ]; then
  cp "$(dirname "$0")/scripts/parallel_dl.py" "$MODEL_DIR/parallel_dl.py"
fi
"$PY" "$MODEL_DIR/parallel_dl.py" --dest "$MODEL_DIR" --jobs 16

step "[2/5] 更新 llama.cpp 并编译（sm_120，无卡模式 -j1 应对 2GB cgroup 内存）"
cd "$LLAMA_DIR"
git fetch --depth 1 origin master
git checkout -f FETCH_HEAD
rm -rf build
cmake -B build -DGGML_CUDA=ON \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=120 \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=OFF -DGGML_CCACHE=OFF \
  -DCUDA_cuda_driver_LIBRARY=/usr/local/cuda/lib64/stubs/libcuda.so \
  -DCMAKE_EXE_LINKER_FLAGS="-lcuda -L/usr/local/cuda/lib64/stubs" \
  -DLLAMA_BUILD_UI=OFF
cmake --build build --config Release -j1 --target llama-server

step "[3/5] 提取并修复聊天模板"
"$PY" -m pip install -q gguf 2>/dev/null || true
"$PY" "$(dirname "$0")/scripts/extract_template.py" \
  "$MODEL_DIR/Qwen3.8-27B-Q4_K_M.gguf" "$BASE/qwen38_template.jinja"

step "[4/5] 准备 API keys 与启动脚本"
if [ ! -s "$BASE/.api_keys" ]; then
  umask 077
  NEW_KEY="sk-$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 48)"
  echo "$NEW_KEY" > "$BASE/.api_keys"
  echo "   生成了新主 key（存于 $BASE/.api_keys）"
fi
cp "$(dirname "$0")/scripts/start_llama_server.sh" "$BASE/start_llama_server.sh"
chmod +x "$BASE/start_llama_server.sh"

step "[5/5] 安装 systemd 服务"
cp "$(dirname "$0")/deploy/qwen38.service" /etc/systemd/system/qwen38.service
systemctl daemon-reload
systemctl enable qwen38 2>/dev/null || true

echo ""
echo "✔ 部署文件准备完成！接下来："
echo "  1. AutoDL 控制台把实例切换为「带卡模式」(RTX 5090)"
echo "  2. 启动服务：  systemctl start qwen38   （或 bash $BASE/start_llama_server.sh）"
echo "  3. 验证：      bash $BASE/verify.sh"
echo "  4. AutoDL「自定义服务」确认 6006 端口映射仍在（公网 HTTPS URL）"
