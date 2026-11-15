#!/usr/bin/env python3
"""Render one vertical 9:16 short from a landscape source video.

- Face-tracked crop (OpenCV YuNet): hard cuts follow scene changes, smooth pan inside a scene
- Word-by-word captions from a YouTube auto-caption VTT (word timings), styled by a JSON style file

usage: make_short.py SRC VTT START END OUT.mp4 [--style STYLE.json]
"""
import argparse, html, json, os, re, subprocess, sys, tempfile
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "assets", "face_detection_yunet_2023mar.onnx")
FONTDIR = os.path.join(ROOT, "assets", "fonts")
DEFAULT_STYLE = os.path.join(ROOT, "styles", "default.json")
OUT_W, OUT_H = 1080, 1920
SAMPLE_FPS = 6
DET_W = 640

STYLE_DEFAULTS = {
    "captions": True,            # false = no burned-in captions
    "font": "Anton",             # font family name (must exist in assets/fonts or system)
    "font_size": 132,
    "uppercase": True,
    "text_color": "#FFFFFF",
    "highlight_colors": ["#39FF33", "#FFE600", "#FF4040"],  # cycles per caption chunk; [] = no highlight
    "outline_color": "#000000",
    "outline": 9,
    "shadow": 5,
    "position_y": 0.68,          # vertical centre of captions, fraction of frame height
    "max_words": 3,              # words shown at once
    "max_chars": 16,
    "pop_animation": True,       # small scale-up when a new chunk appears
    "strip_punctuation": True,   # drop trailing . and ,
    "crop": "face",              # "face" = track faces, "center" = static centre crop
}


def load_style(path):
    st = dict(STYLE_DEFAULTS)
    for p in (DEFAULT_STYLE, path):
        if p and os.path.exists(p):
            st.update(json.load(open(p)))
    return st


def ass_color(hexrgb, alpha=0):
    h = hexrgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}&".upper()


def probe(src):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate", "-of", "csv=p=0", src]).decode().strip()
    w, h, r = out.split(",")[:3]
    n, d = r.split("/")
    return int(w), int(h), float(n) / float(d)


# ---------------------------------------------------------------- crop track
def analyze(src, start, dur, W, H):
    dh = int(round(H * DET_W / W / 2) * 2)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", src,
           "-vf", f"fps={SAMPLE_FPS},scale={DET_W}:{dh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    fsz = DET_W * dh * 3
    det = cv2.FaceDetectorYN.create(MODEL, "", (DET_W, dh), 0.6, 0.3, 50)
    scale = W / DET_W
    crop_w_det = DET_W * (H * 9 / 16) / W
    xs, cuts, prev_hist, i = [], [0], None, 0
    while True:
        buf = proc.stdout.read(fsz)
        if len(buf) < fsz:
            break
        f = np.frombuffer(buf, np.uint8).reshape(dh, DET_W, 3)
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        if prev_hist is not None and cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA) > 0.45:
            cuts.append(i)
        prev_hist = hist
        _, faces = det.detect(f)
        if faces is None or len(faces) == 0:
            xs.append(None)
        else:
            faces = sorted(faces, key=lambda r: -r[2] * r[3] * r[14])
            big = faces[0]
            cx = big[0] + big[2] / 2
            group = [r for r in faces if r[2] * r[3] > 0.35 * big[2] * big[3]
                     and abs((r[0] + r[2] / 2) - cx) < crop_w_det * 0.8]
            lo = min(r[0] for r in group); hi = max(r[0] + r[2] for r in group)
            if hi - lo < crop_w_det * 0.9:
                cx = (lo + hi) / 2
            xs.append(cx * scale)
        i += 1
    proc.wait()
    cuts.append(len(xs))
    return xs, cuts


def build_track(xs, cuts, W, H, mode):
    cw = int(H * 9 / 16) // 2 * 2
    centre = W / 2
    track = np.full(len(xs), centre)
    if mode == "face":
        for a, b in zip(cuts[:-1], cuts[1:]):
            seg = xs[a:b]
            vals = [v for v in seg if v is not None]
            if not vals:
                continue
            med = float(np.median(vals))
            filled = np.array([v if v is not None else np.nan for v in seg], float)
            idx = np.arange(len(filled)); good = ~np.isnan(filled)
            filled = np.interp(idx, idx[good], filled[good])
            filled = np.clip(filled, med - cw * 0.6, med + cw * 0.6)
            if len(filled) < SAMPLE_FPS * 1.5:
                filled[:] = med
            else:
                k = max(3, int(SAMPLE_FPS * 1.2) | 1)
                pad = np.pad(filled, k // 2, mode="edge")
                filled = np.convolve(pad, np.ones(k) / k, mode="valid")
                out = filled.copy(); cur = filled[0]
                for j, v in enumerate(filled):
                    if abs(v - cur) > cw * 0.06:
                        cur = cur + (v - cur) * 0.5
                    out[j] = cur
                filled = out
            track[a:b] = filled
    x = np.clip(track - cw / 2, 0, W - cw)
    return x, cw


def write_sendcmd(path, x, cuts, fps):
    t_s = np.arange(len(x)) / SAMPLE_FPS
    nfr = int(len(x) / SAMPLE_FPS * fps)
    t_f = np.arange(nfr) / fps
    seg_id = np.searchsorted(np.array(cuts[1:-1]) / SAMPLE_FPS, t_f, side="right")
    xf = np.zeros(nfr)
    for s, (a, b) in enumerate(zip(cuts[:-1], cuts[1:])):
        m = seg_id == s
        if not m.any() or b <= a:
            continue
        xf[m] = np.interp(t_f[m], t_s[a:b], x[a:b]) if b - a > 1 else x[a]
    lines, last = [], None
    for t, v in zip(t_f, xf):
        v = int(round(v / 2) * 2)
        if v != last:
            lines.append(f"{t:.4f} crop x {v};")
            last = v
    open(path, "w").write("\n".join(lines) + "\n")
    return int(round(xf[0] / 2) * 2) if nfr else 0


# ---------------------------------------------------------------- captions
def ts(s):
    p = s.split(":"); return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])


def parse_words(vtt):
    """Word-level timings from a YouTube auto-caption VTT: list of [start, end, word]."""
    words = []
    txt = open(vtt, encoding="utf-8").read()
    for block in txt.split("\n\n"):
        m = re.search(r"(\d+:\d+:\d+\.\d+) --> (\d+:\d+:\d+\.\d+)", block)
        if not m or "<c>" not in block:
            continue
        cs, ce = ts(m[1]), ts(m[2])
        line = [l for l in block.split("\n") if "<c>" in l][0]
        parts = re.split(r"<(\d+:\d+:\d+\.\d+)>", line)
        t = cs
        for i, p in enumerate(parts):
            if i % 2 == 1:
                t = ts(p); continue
            w = html.unescape(re.sub(r"<[^>]+>", "", p)).replace(">>", "").strip()
            if w and not re.fullmatch(r"\[.*\]|[-♪]+", w):
                words.append([t, None, w])
        if words:
            words[-1][1] = ce
    for i in range(len(words) - 1):
        nxt = words[i + 1][0]
        if words[i][1] is None or words[i][1] > nxt:
            words[i][1] = nxt
        words[i][1] = min(words[i][1], words[i][0] + 0.9)
    if words and words[-1][1] is None:
        words[-1][1] = words[-1][0] + 0.5
    return words


def ass_time(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(path, words, start, end, st):
    ws = [w for w in words if w[0] >= start - 0.05 and w[0] < end - 0.1]
    chunks, cur = [], []
    for w in ws:
        if cur and (len(cur) >= st["max_words"] or w[0] - cur[-1][1] > 0.6 or
                    sum(len(x[2]) for x in cur) + len(w[2]) > st["max_chars"] or re.search(r"[.?!,]$", cur[-1][2])):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur: chunks.append(cur)
    white = ass_color(st["text_color"])
    hls = [ass_color(c) for c in st["highlight_colors"]]
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st["font"]},{st["font_size"]},{white.rstrip("&")},{white.rstrip("&")},{ass_color(st["outline_color"]).rstrip("&")},&H90000000,0,0,0,0,100,100,2,0,1,{st["outline"]},{st["shadow"]},5,60,60,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    pos = f"{{\\pos({OUT_W // 2},{int(OUT_H * st['position_y'])})}}"
    for ci, ch in enumerate(chunks):
        col = hls[ci % len(hls)] if hls else None
        c_end = ch[-1][1]
        if ci + 1 < len(chunks):
            c_end = min(max(c_end, ch[-1][0] + 0.35), chunks[ci + 1][0][0])
        for wi, w in enumerate(ch):
            a = w[0]
            b = ch[wi + 1][0] if wi + 1 < len(ch) else c_end
            if b <= a: continue
            txt = []
            for k, x in enumerate(ch):
                word = x[2].replace("{", "").replace("}", "")
                if st["uppercase"]: word = word.upper()
                if st["strip_punctuation"]: word = re.sub(r"[.,]+$", "", word)
                txt.append(f"{{\\c{col}}}{word}{{\\c{white}}}" if (col and k == wi) else word)
            pop = "{\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)}" if (wi == 0 and st["pop_animation"]) else ""
            ev.append(f"Dialogue: 0,{ass_time(a - start)},{ass_time(b - start)},Cap,,0,0,0,,{pos}{pop}{' '.join(txt)}")
    open(path, "w", encoding="utf-8").write(hdr + "\n".join(ev) + "\n")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("vtt"); ap.add_argument("start", type=float)
    ap.add_argument("end", type=float); ap.add_argument("out")
    ap.add_argument("--style", default=None)
    a = ap.parse_args()
    st = load_style(a.style)
    dur = a.end - a.start
    W, H, fps = probe(a.src)
    if st["crop"] == "face":
        xs, cuts = analyze(a.src, a.start, dur, W, H)
    else:
        xs, cuts = [None] * int(dur * SAMPLE_FPS), [0, int(dur * SAMPLE_FPS)]
    x, cw = build_track(xs, cuts, W, H, st["crop"])
    tmp = tempfile.mkdtemp(prefix="short_")
    cmdf = os.path.join(tmp, "crop.cmd"); assf = os.path.join(tmp, "subs.ass")
    x0 = write_sendcmd(cmdf, x, cuts, fps)
    esc = lambda p: p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    vf = f"sendcmd=f='{esc(cmdf)}',crop={cw}:{H}:{x0}:0,scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1"
    if st["captions"] and a.vtt and os.path.exists(a.vtt):
        write_ass(assf, parse_words(a.vtt), a.start, a.end, st)
        vf += f",ass='{esc(assf)}':fontsdir='{esc(FONTDIR)}'"
    af = f"afade=t=in:d=0.05,afade=t=out:st={max(0, dur - 0.25):.3f}:d=0.25,loudnorm=I=-14:TP=-1.5:LRA=11"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a.start:.3f}", "-t", f"{dur:.3f}", "-i", a.src,
                    "-vf", vf, "-af", af, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                    "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", f"{fps:.3f}",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", a.out], check=True)
    print(f"ok {a.out} ({dur:.1f}s, {len(cuts) - 1} scenes)")


if __name__ == "__main__":
    main()
