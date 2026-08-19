#!/usr/bin/env bash
# ============================================================
# 编译中断后续跑 + 带卡启动（AutoDL 4 点自动关机/重启后使用）
#
# 用法（切带卡后）:
#   bash scripts/resume_build_and_start.sh
#
# 说明:
#   - llama.cpp 构建对象在数据盘 /root/autodl-tmp，关机不丢，cmake 会续跑
#   - 无卡模式内存 2GB：-j3 是安全值；GPU 模式内存充足可改 -j8 加速
#   - 二进制就绪且带卡后自动启动 llama-server（6006）
# ============================================================
set -euo pipefail

LLAMA_DIR=/root/autodl-tmp/llama.cpp

if [ ! -x "$LLAMA_DIR/build/bin/llama-server" ]; then
  echo "==> 续跑编译（cmake 增量）"
  cd "$LLAMA_DIR"
  cmake --build build --config Release -j3 --target llama-server
fi

echo "==> 检查 GPU"
if ! nvidia-smi >/dev/null 2>&1; then
  echo "尚未切带卡模式（无卡 driver 是 stub），请先在 AutoDL 控制台切换 GPU 再运行"
  exit 1
fi

echo "==> 启动 llama-server"
bash /root/autodl-tmp/start_llama_server.sh
sleep 5
echo "==> 验证"
bash /root/autodl-tmp/scripts/verify.sh || true
