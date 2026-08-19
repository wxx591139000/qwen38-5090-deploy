#!/bin/bash
# ============================================================
# Qwen3.8-27B 512K 最大上下文档（带卡模式）
# 512K（YaRN 扩长）+ mmproj 视觉；无 MTP（其 KV 会翻倍导致 OOM）
# 显存 ~30.4GB/32.6GB，速度比默认档（MTP）慢约 30-40%
# 用途：追求超长上下文 + 图片输入时使用
# ============================================================
BIN=/root/autodl-tmp/llama.cpp/build/bin/llama-server
MODEL=/root/autodl-tmp/models/Qwen3.8-27B-Q4_K_M.gguf
MMPROJ=/root/autodl-tmp/models/mmproj-Qwen3.8-27B-Q8_0.gguf
TEMPLATE=/root/autodl-tmp/qwen38_template.jinja
KEYS=/root/autodl-tmp/.api_keys

pkill -f "build/bin/llama-server" 2>/dev/null
sleep 2
cd /root/autodl-tmp/llama.cpp
nohup $BIN \
  -m $MODEL \
  --alias qwen3.8-27b \
  -ngl 999 \
  -c 524288 \
  -fa on \
  -ctk q4_0 -ctv q4_0 \
  -b 512 -ub 128 \
  -np 1 \
  --reasoning off \
  --jinja \
  --chat-template-file $TEMPLATE \
  --mmproj $MMPROJ \
  --rope-scaling yarn --yarn-orig-ctx 262144 \
  --host 0.0.0.0 --port 6006 \
  --api-key-file $KEYS \
  > /root/autodl-tmp/llama_server.log 2>&1 &
echo "llama-server (512K+视觉) 启动中 PID=$!"
