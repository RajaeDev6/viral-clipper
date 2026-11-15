#!/usr/bin/env bash
# usage: reference.sh SHORT_URL_OR_FILE OUTDIR
# Downloads a reference short (or uses a local file) and makes contact sheets so the
# style (caption font/size/colours/position, pacing, crop) can be copied into a style JSON.
#   OUTDIR/ref.*            the reference video
#   OUTDIR/sheet_full.jpg   one frame every ~2 s across the whole short
#   OUTDIR/sheet_dense.jpg  8 frames, 0.25 s apart, from the middle (shows word-by-word caption timing)
#   OUTDIR/frame_big.jpg    one full-size frame (read caption font and colours)
set -u
SRC="$1"; OUT="$2"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
YTDLP="$ROOT/.venv/bin/yt-dlp"; [ -x "$YTDLP" ] || YTDLP="yt-dlp"
mkdir -p "$OUT"
JS=(); command -v deno >/dev/null && JS=(--js-runtimes deno) || { command -v node >/dev/null && JS=(--js-runtimes node); }

if [ -f "$SRC" ]; then REF="$SRC"; else
  "$YTDLP" "${JS[@]}" --remote-components ejs:github -q -f "bv*[height<=1920]+ba/b" \
    -o "$OUT/ref.%(ext)s" -- "$SRC" || { echo "REFERENCE DOWNLOAD FAILED"; exit 1; }
  REF="$(ls "$OUT"/ref.* | head -1)"
fi
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$REF")
ffprobe -v error -show_entries stream=width,height -of csv=p=0 "$REF" | head -1 | sed 's/^/resolution: /'
echo "duration: $DUR"
N=$(python3 -c "print(max(4,min(12,int(float('$DUR')/2))))")
STEP=$(python3 -c "print(float('$DUR')/($N+1))")
ffmpeg -v error -y -i "$REF" -vf "fps=1/$STEP,scale=240:-1,tile=${N}x1" -frames:v 1 "$OUT/sheet_full.jpg"
MID=$(python3 -c "print(float('$DUR')/2)")
ffmpeg -v error -y -ss "$MID" -i "$REF" -vf "fps=4,scale=240:-1,tile=8x1" -frames:v 1 "$OUT/sheet_dense.jpg"
ffmpeg -v error -y -ss "$MID" -i "$REF" -frames:v 1 -vf "scale=720:-1" "$OUT/frame_big.jpg"
echo "REFERENCE OK: $OUT"
