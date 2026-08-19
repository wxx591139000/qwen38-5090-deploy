#!/bin/bash
# ============================================================
# Qwen3.8-27B llama-server 启动脚本（带卡模式运行）
# 默认档：262K 上下文（原生）+ MTP 推测解码 + mmproj 视觉（全功能，显存 ~27.7GB）
#   想要最大上下文（512K，无 MTP，保留视觉）：start_llama_server_512k.sh
# 端口 6006（AutoDL 自定义服务映射端口），多用户 key 鉴权
# ============================================================
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
  -m $MODEL \
  --alias qwen3.8-27b \
  -ngl 999 \
  -c 262144 \
  -fa on \
  -ctk q4_0 -ctv q4_0 \
  -np 1 \
  --reasoning off \
  --jinja \
  --chat-template-file $TEMPLATE \
  -md $MTP --spec-type draft-mtp \
  --mmproj $MMPROJ \
  --host 0.0.0.0 --port 6006 \
  --api-key-file $KEYS \
  > /root/autodl-tmp/llama_server.log 2>&1 &
echo "llama-server (262K 全功能) 启动中 PID=$!（日志: /root/autodl-tmp/llama_server.log）"
