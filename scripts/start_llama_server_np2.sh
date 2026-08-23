#!/bin/bash
# Qwen3.8-27B llama-server 启动脚本（测试 -np 2 双槽，262K 全功能）
# 预期显存 ~31GB（27.6 + 2号槽KV 3.7），聚合吞吐或翻倍
BIN=/root/autodl-tmp/llama.cpp/build/bin/llama-server
MODEL=/root/autodl-tmp/models/Qwen3.8-27B-Q4_K_M.gguf
MTP=/root/autodl-tmp/models/mtp-Qwen3.8-27B-Q4_0.gguf
MMPROJ=/root/autodl-tmp/models/mmproj-Qwen3.8-27B-Q8_0.gguf
TEMPLATE=/root/autodl-tmp/qwen38_template.jinja
KEYS=/root/autodl-tmp/.api_keys
pkill -f "build/bin/llama-server" 2>/dev/null
sleep 2
cd /root/autodl-tmp/llama.cpp
nohup $BIN \
  -m $MODEL --alias qwen3.8-27b -ngl 999 -c 262144 -fa on \
  -ctk q4_0 -ctv q4_0 -np 2 --reasoning off --jinja \
  --chat-template-file $TEMPLATE -md $MTP --spec-type draft-mtp \
  --mmproj $MMPROJ --host 0.0.0.0 --port 6006 --api-key-file $KEYS \
  > /root/autodl-tmp/llama_server_np2.log 2>&1 &
echo "llama-server (-np 2) 启动中 PID=$!  log=llama_server_np2.log"
