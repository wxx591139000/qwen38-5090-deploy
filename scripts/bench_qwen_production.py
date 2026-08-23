#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# Qwen3.8-27B 生产性能基准脚本（llama-server / OpenAI 兼容端点）
#
# 适用对象：
#   - 当前 AutoDL RTX 5090 服务器（端口 6006，API-key 鉴权）
#   - 未来 Mac（Metal llama-server，同样端点协议）
# 目的：统一口径测出「生产可感知」的三个核心指标，用于跨机器对齐：
#   1. TTFT      首 token 延迟（预填有多快，长上下文主要开销在这）
#   2. 稳定 tok/s 首 token 之后到 `[DONE]` 的输出速度（打字体感）
#   3. SWAP/page-out  跑测期间是否有换页（内存吃不吃的直接证据）
#
# 用法：
#   python bench_qwen_production.py                     # 默认档：5 次，默认短 prompt
#   python bench_qwen_production.py --long              # 长 prompt（贴近长上下文生产）
#   python bench_qwen_production.py -n 8 -t 1200        # 8 次，每次 max_tokens 1200
#   python bench_qwen_production.py --url http://127.0.0.1:6006/v1 --key <KEY>
#   python bench_qwen_production.py --swap-on            # 显式开启 SWAP/page-out 监控
#
# 环境变量（优先级低于命令行参数）：
#   QWEN38_BASE_URL  端点；QWEN38_API_KEY  API key；QWEN38_MODEL 模型名
#
# key 读取优先级：--key > QWEN38_API_KEY > /root/autodl-tmp/.api_keys 首行
# ============================================================
import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

# ---- 与 qwen38 项目约定一致的默认值 ----
DEFAULT_URL = "http://127.0.0.1:6006/v1"
DEFAULT_MODEL = "qwen3.8-27b"
API_KEY_FILE = "/root/autodl-tmp/.api_keys"

# 真实生产 prompt 样式：短（轻量问答）vs 长（长上下文/文档处理）
SHORT_PROMPT = ("请针对以下运营场景给出落地方案，分条编号，每条约120字，至少输出8条："
                "如何提升知识账号在小红书上的视频播放完播率？")
LONG_PROMPT = ("请基于以下长业务资料给出专业的输出建议，逐点分析并落到可执行动作：\n"
               + ("转录服务当前并发策略、内存占用、模型选型与量化档位、排队与重试机制。"
                  "请评估其生产容量瓶颈，并给出在受限统一内存环境下的优化路径。\n" * 40))


def read_api_key(cli_key: str) -> str:
    """按 --key > 环境变量 > 服务器 .api_keys 的顺序解析 key。"""
    if cli_key:
        return cli_key
    env = os.environ.get("QWEN38_API_KEY")
    if env:
        return env
    if os.path.isfile(API_KEY_FILE):
        with open(API_KEY_FILE) as f:
            first = f.readline().strip()
            if first:
                return first
    return ""


class MemoryMonitor:
    """跨平台 SWAP/page-out 采样器。

    Linux  : 读 /proc/vmstat 的 pswpin/pswpout（page in/out 累计值）
    macOS  : 解析 `vm_stat` 的 Pages swapped in/out（注意 macOS 单位是 4KB 页）
    未识别平台或无法读取时降级为仅提示，不阻塞主流程。
    """

    def __init__(self):
        self.ps = None
        if os.name == "posix":
            if os.path.isfile("/proc/vmstat"):
                self.mode = "linux"
            else:
                try:
                    import shutil
                    if shutil.which("vm_stat"):
                        self.mode = "mac"
                    else:
                        self.mode = "none"
                except Exception:
                    self.mode = "none"
        else:
            self.mode = "none"
        self.base = self._read()

    def _read(self) -> dict:
        if self.mode == "linux":
            d = {"pswpin": 0, "pswpout": 0}
            try:
                with open("/proc/vmstat") as f:
                    for line in f:
                        k, _, v = line.partition(" ")
                        k = k.strip()
                        if k in ("pswpin", "pswpout"):
                            d[k] = int(v)
            except Exception:
                pass
            return d
        if self.mode == "mac":
            out = os.popen("vm_stat 2>/dev/null").read()
            for line in out.splitlines():
                k, _, v = line.partition(":")
                k = k.strip()
                if "swap" in k.lower() or "pun" in k.lower():
                    num = v.strip().split()[0]
                    try:
                        self._mac[k] = int(num.replace(".", ""))
                    except Exception:
                        pass
            return getattr(self, "_mac", {})
        return {}

    def snapshot(self) -> str:
        if self.mode == "none":
            return "（跳过：无法读取平台换页统计）"
        now = self._read()
        try:
            if self.mode == "linux":
                pin = now["pswpin"] - self.base.get("pswpin", 0)
                pout = now["pswout"] - self.base.get("pswpout", 0)
                return f"Linux page-in={pin} 页 page-out={pout} 页"
            if self.mode == "mac":
                pin = now.get("Pages swapped in", 0) - self.base.get("Pages swapped in", 0)
                pout = now.get("Pages swapped out", 0) - self.base.get("Pages swapped out", 0)
                return f"macOS swapped-in(page)={pin} swapped-out(page)={pout}"
        except Exception:
            return "（读取换页统计异常）"
        return ""


class QwenBench:
    def __init__(self, url: str, key: str, model: str):
        self.url = url.rstrip("/")
        self.key = key
        self.model = model

    def _headers(self, stream: bool) -> dict:
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def run_once(self, prompt: str, max_tokens: int, timeout: int) -> dict:
        """单次流式请求，返回 TTFT、输出 token、稳定 tok/s。"""
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "max_tokens": max_tokens,
        }
        payload = json.dumps(body).encode()
        req = urllib.request.Request(
            self.url + "/chat/completions",
            data=payload,
            headers=self._headers(True),
            method="POST",
        )
        t_request = time.perf_counter()
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:300]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"网络错误: {e.reason}")

        first_token_ts = None   # 首 token 到达时间
        last_chunk_ts = None    # 最后一个内容块时间
        sse_tokens = 0          # SSE delta 块数量（近似 token 数）
        completion_tokens = 0   # 最终 usage 里的准确 token 数
        done_ts = None
        buf = b""

        for raw in resp:
            buf += raw
            while b"\n\n" in buf:
                block, buf = buf.split(b"\n\n", 1)
                for line in block.decode("utf-8", "replace").splitlines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        done_ts = time.perf_counter()
                        break
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    usage = obj.get("usage")
                    if usage:
                        completion_tokens = usage.get("completion_tokens", completion_tokens)
                    choices = obj.get("choices") or []
                    if choices and choices[0].get("delta", {}).get("content"):
                        if first_token_ts is None:
                            first_token_ts = time.perf_counter()
                        last_chunk_ts = time.perf_counter()
                        sse_tokens += 1
                # 若本块已收到 [DONE]，直接结束整个流
            if done_ts is not None:
                break
        resp.close()

        if done_ts is None:
            done_ts = time.perf_counter()
        ttft = (first_token_ts - t_request) if first_token_ts else None
        if completion_tokens == 0:
            completion_tokens = sse_tokens  # 无 usage 时退化用 SSE 块数
        # 稳定输出时间 = 首 token 之后到 DONE（去掉预填的 TTFT）
        steady_gen_s = None
        if first_token_ts is not None:
            steady_gen_s = done_ts - first_token_ts
            out_tokens = max(1, completion_tokens - 1)  # 首个 delta 属预填尾，不计
            tps = out_tokens / steady_gen_s if steady_gen_s > 0 else 0.0
        else:
            tps = None
        return {"ttft": ttft, "tps": tps, "completion_tokens": completion_tokens}


def pct(sorted_vals, p: float):
    if not sorted_vals:
        return float("nan")
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * p))
    return sorted_vals[idx]


def main():
    ap = argparse.ArgumentParser(description="Qwen3.8-27B 生产性能基准")
    ap.add_argument("-n", "--runs", type=int, default=5, help="测试次数（默认5）")
    ap.add_argument("-t", "--max-tokens", type=int, default=800, help="每次 max_tokens")
    ap.add_argument("--timeout", type=int, default=600, help="单次请求超时(秒)")
    ap.add_argument("--long", action="store_true", help="使用长 prompt（长上下文生产场景）")
    ap.add_argument("--url", default=os.environ.get("QWEN38_BASE_URL", DEFAULT_URL))
    ap.add_argument("--key", default="")
    ap.add_argument("--model", default=os.environ.get("QWEN38_MODEL", DEFAULT_MODEL))
    ap.add_argument("--swap-on", dest="swap_on", action="store_true",
                    help="显式开启 SWAP/page-out 监控")
    ap.add_argument("--gap", type=float, default=2.0, help="各次之间间隔秒（模拟真实用户）")
    args = ap.parse_args()

    key = read_api_key(args.key)
    if not key:
        print("⚠️  未提供 API key（--key / 环境变量 / .api_keys），将按免鉴权请求。")
        print("    llama-server 若配了 --api-key-file 则必须给 key。")
    prompt = LONG_PROMPT if args.long else SHORT_PROMPT

    # SWAP 监控：macOS(M 系) 默认开；Linux 服务端默认关（无 SWAP 意义，但可开看 page out）
    mm = MemoryMonitor()
    want_swap = args.swap_on or ("mac" in mm.mode)
    if want_swap:
        print(f"[内存监控] {mm.mode} 模式 —— 测试期间记录换页情况\n")

    bench = QwenBench(args.url, key, args.model)
    print(f"端点  : {bench.url}")
    print(f"模型  : {bench.model}")
    print(f"模式  : {'长上下文(close to 262K prefill)' if args.long else '短对话'}")
    print(f"次数  : {args.runs} 次, max_tokens={args.max_tokens}, 间隔={args.gap}s\n")

    tft, tps, toks = [], [], []
    # 先发一个空健康/握手请求，排除服务首次加载 jitter
    try:
        bench.run_once("hi", 8, 30)
    except Exception:
        pass

    for i in range(1, args.runs + 1):
        start_foot = time.time()
        print(f"  [{i}/{args.runs}] 请求中 ...", end="", flush=True)
        try:
            r = bench.run_once(prompt, args.max_tokens, args.timeout)
            tft.append(r["ttft"]); toks.append(r["completion_tokens"])
            if r["tps"] is not None:
                tps.append(r["tps"])
            print(f"  TTFT≈{r['ttft']:.2f}s  输出≈{r['completion_tokens']}tok  "
                  f"稳定≈{r['tps']:.1f}tok/s")
        except RuntimeError as e:
            print(f"  ❌ {e}")
        except Exception as e:
            print(f"  ❌ 异常: {e}")
        # 补足间隔（模拟真实用户思考/编辑时间，避免把 CPU 顶满虚高）
        spend = time.time() - start_foot
        if spend < args.gap:
            time.sleep(args.gap - spend)

    print("\n=========== 生产性能汇总 ===========")
    if tft:
        tf = sorted(tft)
        print(f"TTFT(首token延迟)  p50={tf[int(len(tf)*.5)]:.2f}s   "
              f"p95={tf[min(len(tf)-1,int(len(tf)*.95))]:.2f}s")
    if tps:
        ts = sorted(tps)
        print(f"稳定输出token/s    p50={ts[int(len(ts)*.5)]:.1f}   "
              f"p95={ts[min(len(ts)-1,int(len(ts)*.95))]:.1f}")
    if toks:
        print(f"平均输出长度       {int(sum(toks)/len(toks))} tok/次")
    if want_swap:
        print(f"[换页快照] {mm.snapshot()}")

    print("\n=== 及格线参考（跑满转录服务的生产标准）===")
    med_tps = sorted(tps)[int(len(tps)*.5)] if tps else float("nan")
    med_ttft = sorted(tft)[int(len(tft)*.5)] if tft else float("nan")
    print(f"  稳定输出 ≥ 20 tok/s         -> 当前 p50={med_tps:.1f}  {'✅ 合格' if med_tps>=20 else '⚠️ 达标中'}")
    print(f"  最大输入 TTFT < 5s          -> 当前 p50={med_ttft:.2f}s")
    print(f"  跑测期间换页 0 增长          -> 见上方[换页快照]（Mac 上 page-out>0 = 内存不够/在 SWAP）")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(130)