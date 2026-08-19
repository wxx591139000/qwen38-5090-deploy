#!/usr/bin/env bash
# Qwen3.8-27B 服务验证脚本（带卡模式、服务启动后执行）
set -euo pipefail

PORT="${1:-6006}"
MODEL_NAME="${2:-qwen3.8-27b}"
BASE_URL="http://127.0.0.1:$PORT"
KEY="$(head -1 /root/autodl-tmp/.api_keys 2>/dev/null || echo '')"
PY="${PYTHON:-/root/miniconda3/bin/python}"
[ -x "$PY" ] || PY="python3"

echo "==> 健康检查"
curl -sf "$BASE_URL/health" && echo " [OK]" || { echo " [FAIL]"; exit 1; }

echo "==> 模型列表"
curl -sf "$BASE_URL/v1/models" -H "Authorization: Bearer $KEY" | head -c 300
echo

echo "==> 鉴权反向（无 key 应 401）"
code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/v1/models")"
echo "无 key 状态码: $code"
[ "$code" = "401" ] || { echo " [FAIL] 无 key 未返回 401"; exit 1; }

echo "==> 对话测试（chat/completions，thinking 关闭）"
curl -sf "$BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL_NAME\",\"messages\":[{\"role\":\"user\",\"content\":\"用一句话介绍你自己\"}],\"enable_thinking\":false,\"max_tokens\":100}" \
  | "$PY" -c "import sys,json; d=json.load(sys.stdin); print('回复:', d['choices'][0]['message']['content'][:200])" \
  || echo "（对话测试失败，请检查模型名/日志）"

echo "==> Responses API 测试（Codex wire_api=responses 用）"
curl -sf "$BASE_URL/v1/responses" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL_NAME\",\"input\":\"1+1=?\",\"max_output_tokens\":50}" \
  | "$PY" -c "import sys,json; d=json.load(sys.stdin); print('回复:', d.get('output_text','')[:200])" \
  || echo "（responses 测试失败，llama.cpp 版本可能过旧）"

echo "==> 完成"
