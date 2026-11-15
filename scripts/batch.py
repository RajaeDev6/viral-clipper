#!/usr/bin/env python3
"""Render every clip listed in WORKDIR/moments.json and write OUTDIR/README.md.

usage: batch.py WORKDIR OUTDIR [--jobs N] [--style STYLE.json]

WORKDIR must contain src.mkv and src.en-orig.vtt (see download.sh).
If --style is omitted, WORKDIR/style.json is used when present, else styles/default.json.
Clips that already exist in OUTDIR are skipped, so re-running resumes.
"""
import argparse, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_short import parse_words

ap = argparse.ArgumentParser()
ap.add_argument("workdir"); ap.add_argument("outdir")
ap.add_argument("--jobs", type=int, default=2)
ap.add_argument("--style", default=None)
a = ap.parse_args()
wd, outdir = a.workdir, a.outdir
os.makedirs(outdir, exist_ok=True)
style = a.style or (os.path.join(wd, "style.json") if os.path.exists(os.path.join(wd, "style.json")) else None)

ms = json.load(open(os.path.join(wd, "moments.json")))
vtt = os.path.join(wd, "src.en-orig.vtt")
words = parse_words(vtt) if os.path.exists(vtt) else []
starts = [w[0] for w in words]


def snap(s, e):
    """Snap start to the nearest word start, end to just after the last spoken word."""
    if not words:
        return float(s), float(e)
    near = [t for t in starts if s - 1.0 <= t <= s + 1.0]
    s2 = max(0, (min(near, key=lambda t: abs(t - s)) if near else s) - 0.2)
    last = [w for w in words if s2 <= w[0] < e - 0.3]
    e2 = (last[-1][1] + 0.5) if last else e
    return round(s2, 2), round(max(e2, e - 0.2), 2)


def run(i_m):
    i, m = i_m
    s, e = snap(m["s"], m["e"])
    name = f"{i + 1:02d}_" + re.sub(r"[^A-Za-z0-9]+", "_", m["title"]).strip("_")
    out = os.path.join(outdir, name + ".mp4")
    m.update(file=name + ".mp4", start=s, end=e)
    if not os.path.exists(out):
        cmd = [sys.executable, "-I", os.path.join(HERE, "make_short.py"),
               os.path.join(wd, "src.mkv"), vtt, str(s), str(e), out + ".part.mp4"]
        if style:
            cmd += ["--style", style]
        r = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        if r.returncode != 0:
            print(f"FAILED {name}: {r.stderr.strip()[-500:]}", flush=True)
            return m
        os.replace(out + ".part.mp4", out)
    print(f"done {name}", flush=True)
    return m


with ThreadPoolExecutor(a.jobs) as ex:
    res = list(ex.map(run, enumerate(ms)))

info = {}
ip = os.path.join(wd, "src.info.json")
if os.path.exists(ip):
    try:
        info = json.load(open(ip))
    except Exception:
        pass
fmt = lambda t: f"{int(t // 60):02d}:{t % 60:04.1f}"
md = [f"# {info.get('title', 'Shorts')} · Shorts\n"]
if info.get("webpage_url"):
    md.append(f"Source: {info['webpage_url']}\n")
for i, m in enumerate(res):
    md += [f"## {i + 1}. {m['title']}",
           f"- File: `{m['file']}` · {m['end'] - m['start']:.0f}s · source {fmt(m['start'])} → {fmt(m['end'])}",
           "- Post caption:\n", "```", m.get("caption", ""), "", m.get("tags", ""), "```", ""]
open(os.path.join(outdir, "README.md"), "w").write("\n".join(md))
print("ALL DONE", flush=True)
