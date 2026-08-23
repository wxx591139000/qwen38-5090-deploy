#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# Qwen3.8-27B 并发压测（评估生产可同时服务几人）
#
# llama-server 关键约束：当前启动脚本 `-np 1`（单槽），同一刻只处理一个请求，
# 其余在服务端队列等待。本脚本用多线程并发发请求，
# 量化「共享容量」：并发 N 下，聚合吞吐(agg tok/s) + 每请求排队延迟。
#
# 用法：
#   python bench_qwen_concurrency.py                    # 默认并发 [1,2,4,6,8]
#   python bench_qwen_concurrency.py -c 2 4 8          # 指定并发档
#   python bench_qwen_concurrency.py -t 200 -n 3       # 每档 3 轮取均值
#   python bench_qwen_concurrency.py --long            # 长 prompt
#   环境变量：QWEN38_BASE_URL / QWEN38_API_KEY / QWEN38_MODEL
# key：--key > QWEN38_API_KEY > /root/autodl-tmp/.api_keys 首行
# ============================================================
import argparse, concurrent.futures, json, os, statistics, time, urllib.request, urllib.error

DEFAULT_URL = "http://127.0.0.1:6006/v1"
DEFAULT_MODEL = "qwen3.8-27b"
API_KEY_FILE = "/root/autodl-tmp/.api_keys"
SHORT_PROMPT = ("请用不超过150字，分条给出提升小红书视频完播率的3个可落地要点："
                "明确列出动作与执行频率。")
LONG_PROMPT = ("请基于以下长业务资料给出专业建议，逐点分析并落到可执行动作：\n"
               + ("并发与队列策略、内存占用、量化档位、重试机制，评估生产容量瓶颈，"
                  "给出受限统一内存环境的优化路径。\n" * 30))


def read_key(cli):
    if cli: return cli
    e = os.environ.get("QWEN38_API_KEY")
    if e: return e
    if os.path.isfile(API_KEY_FILE):
        with open(API_KEY_FILE) as f:
            first = f.readline().strip()
            if first: return first
    return ""


def one_request(url, key, model, prompt, max_tokens, timeout):
    """单次流式请求，返回 {ttft, latency, tokens}（阻塞直到完成）。"""
    body = {"model": model, "stream": True, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(url + "/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {key}"} if key else {})},
                                 method="POST")
    t0 = time.perf_counter()
    first_ts = None; done_ts = None; comp = 0; sse = 0
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        return {"err": f"HTTP {e.code}: {e.read()[:200]}", "ttft": None, "latency": time.perf_counter()-t0, "tokens": 0}
    except Exception as e:
        return {"err": f"{e.__class__.__name__}", "ttft": None, "latency": time.perf_counter()-t0, "tokens": 0}
    buf = b""
    for raw in resp:
        buf += raw
        while b"\n\n" in buf:
            block, buf = buf.split(b"\n\n", 1)
            for line in block.decode("utf-8", "replace").splitlines():
                if not line.startswith("data:"): continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done_ts = time.perf_counter(); break
                try: obj = json.loads(data)
                except Exception: continue
                if obj.get("usage"):
                    comp = obj["usage"].get("completion_tokens", comp)
                ch = obj.get("choices") or []
                if ch and ch[0].get("delta", {}).get("content"):
                    if first_ts is None: first_ts = time.perf_counter()
                    sse += 1
            if done_ts is not None: break
    resp.close()
    if done_ts is None: done_ts = time.perf_counter()
    if comp == 0: comp = sse
    return {"ttft": (first_ts - t0) if first_ts else None,
            "latency": done_ts - t0,
            "tokens": comp}


def run_level(url, key, model, prompt, max_tokens, concurrency, timeout, timeout_all):
    """并发 concurrency 个请求同时发，返回该档聚合结果。"""
    results = []
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(one_request, url, key, model, prompt, max_tokens, timeout)
                for _ in range(concurrency)]
        for f in concurrent.futures.as_completed(futs, timeout=timeout_all):
            results.append(f.result())
    wall = time.perf_counter() - start
    ok = [r for r in results if r.get("err") is None and r["tokens"] > 0]
    total_tok = sum(r["tokens"] for r in ok)
    agg_tps = total_tok / wall if wall > 0 else 0.0
    ttfts = sorted(r["ttft"] for r in ok if r["ttft"] is not None)
    lats = sorted(r["latency"] for r in ok)
    return {"conc": concurrency, "wall": round(wall, 2), "ok": len(ok),
            "fail": len(results) - len(ok), "total_tok": total_tok,
            "agg_tps": round(agg_tps, 1),
            "ttft_p50": round(ttfts[int(len(ttfts)*.5)], 2) if ttfts else None,
            "ttft_p95": round(ttfts[min(len(ttfts)-1,int(len(ttfts)*.95))], 2) if ttfts else None,
            "lat_p50": round(lats[int(len(lats)*.5)], 2) if lats else None,
            "lat_p95": round(lats[min(len(lats)-1,int(len(lats)*.95))], 2) if lats else None,
            "per_user_tps": round(agg_tps / concurrency, 1) if concurrency else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--concs", type=int, nargs="+", default=[1, 2, 4, 6, 8])
    ap.add_argument("-t", "--max-tokens", type=int, default=200)
    ap.add_argument("-n", "--rounds", type=int, default=2, help="每档轮数取最稳的")
    ap.add_argument("--timeout", type=int, default=240, help="单请求超时")
    ap.add_argument("--timeout-all", type=int, default=900, help="整档超时")
    ap.add_argument("--url", default=os.environ.get("QWEN38_BASE_URL", DEFAULT_URL))
    ap.add_argument("--key", default="")
    ap.add_argument("--model", default=os.environ.get("QWEN38_MODEL", DEFAULT_MODEL))
    ap.add_argument("--long", action="store_true")
    args = ap.parse_args()

    url = args.url.rstrip("/"); key = read_key(args.key)
    if not key: print("⚠️ 未提供 API key（--key / QWEN38_API_KEY / .api_keys），按免鉴权试。")
    prompt = LONG_PROMPT if args.long else SHORT_PROMPT
    print(f"端点 {url} ｜ 模型 {args.model} ｜ prompt={'长' if args.long else '短'}"
          f" ｜ max_tokens={args.max_tokens} ｜ 每档{args.rounds}轮取最稳")
    print(f"{'并发':>4} {'ok/总':>6} {'轮耗时s':>7} {'总token':>8} "
          f"{'聚合tok/s':>9} {'每用户tok/s':>10} {'TTFT-p50':>8} {'TTFT-p95':>8} {'迟延p50s':>8}")
    print("-" * 80)
    # 预热
    one_request(url, key, args.model, "hi", 8, 30)
    for c in args.concs:
        best = None
        for _ in range(args.rounds):
            r = run_level(url, key, args.model, prompt, args.max_tokens, c, args.timeout, args.timeout_all)
            if best is None or r["total_tok"] > best["total_tok"]: best = r
        if best is None: continue
        print(f"{best['conc']:>4} {str(best['ok'])+'/'+str(c):>6} {best['wall']:>7} "
              f"{best['total_tok']:>8} {best['agg_tps']:>9} {best['per_user_tps']:>10} "
              f"{str(best['ttft_p50']):>8} {str(best['ttft_p95']):>8} {str(best['lat_p50']):>8}")

    print("\n=== 解读 ===")
    print("聚合 tok/s 若能随并发提升 → 有并行能力；若持平/下降 → 被 -np 单槽串行化。")
    print("每用户 tok/s = 聚合/并发（真实体感速度）；迟延含排队等待时间。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中断。"); raise SystemExit(130)