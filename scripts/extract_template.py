#!/usr/bin/env python3
"""
从 Qwen3.8-27B GGUF 提取官方聊天模板，并应用两处必要修复：

1. System 消息位置容忍
   llama.cpp 客户端（Codex/Claude Code 等）可能把 system 消息放在历史
   中间，官方模板对此 raise_exception('System message must be at the
   beginning.')，导致请求直接 500。将这一行替换为空操作。

2. 多轮对话空 thinking 块修复
   官方模板把每一个历史 assistant 轮次都包成 <think>..</think>，即使
   reasoning_content 为空，多轮后出现嵌套空块、历史被截断的「失忆」。
   改为：只有 reasoning_content 非空时才包 <think> 块。

用法:
    python extract_template.py <model.gguf> <output.jinja>
"""

import sys


def read_template(gguf_path: str) -> str:
    try:
        from gguf import GGUFReader
    except ImportError as exc:
        sys.exit("缺少 gguf 库，请先: pip install gguf  (%s)" % exc)

    reader = GGUFReader(gguf_path)
    field = reader.get_field("tokenizer.chat_template")
    if field is None:
        sys.exit("GGUF 中找不到 tokenizer.chat_template")

    # gguf 库不同版本的 parts 结构略有差异，做兼容处理
    try:
        idx = field.data[0]
        raw = bytes(field.parts[idx])
    except Exception:  # noqa: BLE001
        raw = b"".join(bytes(p) for p in field.parts)
    return raw.decode("utf-8")


def fix_template(tpl: str) -> str:
    # 1. system 位置检查 → 空操作
    before = "{{- raise_exception('System message must be at the beginning.') }}"
    after = "{#- tolerate system messages anywhere (llama.cpp clients may reorder) -#}"
    if before in tpl:
        tpl = tpl.replace(before, after)
    else:
        print("WARN: 未找到 system 位置检查，跳过修复 1", file=sys.stderr)

    # 2. assistant 轮次只有存在 reasoning 时才包 <think> 块
    before = (
        "{%- if preserve_thinking is undefined or preserve_thinking is true "
        "or loop.index0 > ns.last_query_index %}"
    )
    after = "{%- if reasoning_content %}"
    if before in tpl:
        tpl = tpl.replace(before, after)
    else:
        print("WARN: 未找到 preserve_thinking 分支，跳过修复 2", file=sys.stderr)

    return tpl


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    src, dst = sys.argv[1], sys.argv[2]
    tpl = fix_template(read_template(src))
    with open(dst, "w", encoding="utf-8") as f:
        f.write(tpl)
    print("已写出修复后模板: %s (%d bytes)" % (dst, len(tpl.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
