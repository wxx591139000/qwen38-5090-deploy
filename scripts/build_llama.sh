#!/usr/bin/env bash
# ============================================================
# 编译 llama-server（Blackwell sm_120，无卡模式）
# 用法: bash scripts/build_llama.sh
# 注意: 无卡模式 cgroup 内存 2GB，必须 -j1（-j4 以上会被 OOM 杀）
# ============================================================
set -euo pipefail

LLAMA_DIR=/root/autodl-tmp/llama.cpp
cd "$LLAMA_DIR"

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

echo ""
echo "✔ 编译完成: $LLAMA_DIR/build/bin/llama-server"
./build/bin/llama-server --version
