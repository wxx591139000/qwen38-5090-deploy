#!/usr/bin/env python3
"""
Parallel chunked downloader for Qwen3.8-27B GGUF files from ModelScope.

Why:  AutoDL 无卡模式下载大模型，单连接 curl 到 hf-mirror 只有 ~700KB/s；
      ModelScope CDN 支持 Range 请求，16 线程并发可达 5-10MB/s。

Usage:
    python parallel_dl.py [--files Qwen3.8-27B-Q4_K_M.gguf,...] [--jobs 16]

Files are downloaded into /root/autodl-tmp/models (override with --dest).
Chunk parts (.partN) are merged automatically; re-running resumes/skips done files.
"""

import argparse
import os
import sys
import threading
import time
import urllib.parse
import urllib.request

BASE = (
    "https://modelscope.cn/api/v1/models/"
    "ggml-org/Qwen3.8-27B-GGUF/repo?Revision=master&FilePath={}"
)
DEFAULT_DEST = "/root/autodl-tmp/models"
DEFAULT_FILES = [
    ("Qwen3.8-27B-Q4_K_M.gguf", 18973870432),
    ("mtp-Qwen3.8-27B-Q4_0.gguf", 1680271648),
    ("mmproj-Qwen3.8-27B-Q8_0.gguf", 629247008),
]


def get_url(fname: str) -> str:
    return BASE.format(urllib.parse.quote(fname))


def dl_chunk(
    fname: str,
    start: int,
    end: int,
    part: str,
    idx: int,
    progress,
    lock: threading.Lock,
) -> bool:
    """Download one byte range. Each attempt re-resolves the redirect, so a
    fresh (non-expired) ModelScope auth_key is always used."""
    req = urllib.request.Request(
        get_url(fname),
        headers={
            "Range": "bytes=%d-%d" % (start, end),
            "User-Agent": "Mozilla/5.0",
        },
    )
    for attempt in range(20):
        try:
            with urllib.request.urlopen(req, timeout=180) as r, open(part, "wb") as f:
                while True:
                    buf = r.read(1 << 20)
                    if not buf:
                        break
                    f.write(buf)
                    with lock:
                        progress[0] += len(buf)
                        done = progress[0]
                    if idx == 0 and done % (8 << 20) < (1 << 20):
                        print("PROGRESS %s %d" % (fname, done), flush=True)
            return True
        except Exception as exc:  # noqa: BLE001 - keep trying, network is flaky
            with lock:
                print(
                    "RETRY %s chunk%d attempt%d: %s" % (fname, idx, attempt, exc),
                    flush=True,
                )
            time.sleep(3 + attempt * 2)
    return False


def download_file(fname: str, size: int, jobs: int, dest: str) -> bool:
    path = os.path.join(dest, fname)
    if os.path.exists(path) and os.path.getsize(path) == size:
        print("SKIP %s already complete" % fname, flush=True)
        return True
    os.makedirs(dest, exist_ok=True)
    n = min(jobs, max(1, size // (4 << 20)))
    chunk = size // n
    parts = []
    progress = [0]
    lock = threading.Lock()
    threads = []
    for i in range(n):
        start = i * chunk
        end = size - 1 if i == n - 1 else (i + 1) * chunk - 1
        part = "%s.part%d" % (path, i)
        parts.append((part, start))
        t = threading.Thread(
            target=dl_chunk,
            args=(fname, start, end, part, i, progress, lock),
            daemon=True,
        )
        t.start()
        threads.append(t)
    ok = True
    for t in threads:
        t.join(10800)
        if t.is_alive():
            ok = False
    if not ok:
        print("FAIL %s chunk thread timeout" % fname, flush=True)
        return False
    with open(path, "wb") as out:
        for part, _ in sorted(parts, key=lambda x: x[1]):
            with open(part, "rb") as p:
                while True:
                    buf = p.read(4 << 20)
                    if not buf:
                        break
                    out.write(buf)
            os.remove(part)
    if os.path.getsize(path) != size:
        print("FAIL %s size mismatch" % fname, flush=True)
        return False
    print("DONE %s" % fname, flush=True)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--files", default=None, help="comma separated filenames")
    args = ap.parse_args()

    files = DEFAULT_FILES
    if args.files:
        wanted = set(args.files.split(","))
        files = [(f, s) for f, s in DEFAULT_FILES if f in wanted]
    for fname, size in files:
        if not download_file(fname, size, args.jobs, args.dest):
            return 1
    print("ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
