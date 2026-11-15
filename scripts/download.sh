#!/usr/bin/env bash
# usage: download.sh URL WORKDIR
# Downloads into WORKDIR:
#   src.mkv           best video up to 1440p + the ORIGINAL-language audio track (not a dub)
#   src.en-orig.vtt   word-timed English auto captions (used for word-by-word captions)
#   src.info.json     video metadata (title, channel, ...)
set -u
URL="$1"; WD="$2"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
YTDLP="$ROOT/.venv/bin/yt-dlp"; [ -x "$YTDLP" ] || YTDLP="yt-dlp"
mkdir -p "$WD"; cd "$WD" || exit 1

JS=()
if command -v deno >/dev/null; then JS=(--js-runtimes deno)
elif command -v node >/dev/null; then JS=(--js-runtimes node)
elif command -v bun >/dev/null; then JS=(--js-runtimes bun); fi
YT=("$YTDLP" "${JS[@]}" --remote-components ejs:github)

# metadata
"${YT[@]}" --skip-download --write-info-json -o "src.%(ext)s" "$URL" >/dev/null 2>&1 || true

# captions: requested separately, because bulk subtitle requests get HTTP 429
"${YT[@]}" --skip-download --write-auto-subs --sub-langs en-orig --sub-format vtt -o "src.%(ext)s" "$URL"
if [ ! -f src.en-orig.vtt ]; then
  sleep 3
  "${YT[@]}" --skip-download --write-auto-subs --sub-langs en --sub-format vtt -o "src.%(ext)s" "$URL"
  [ -f src.en.vtt ] && mv src.en.vtt src.en-orig.vtt
fi
[ -f src.en-orig.vtt ] || echo "WARNING: no English auto captions found; clips will have no captions"

# video: try formats in order (some return 403); audio must be the original track
for f in \
  "bv*[height<=1440]+ba[format_note*=original]" \
  "bv*[height<=1440]+ba[language^=en]" \
  "400+140-20" "271+251-20" "137+140-20" \
  "bv*[height<=1440]+ba" "bv*[height<=1080]+ba" "b" ; do
  echo "== trying format: $f"
  "${YT[@]}" -f "$f" --merge-output-format mkv -o "src.%(ext)s" -N 8 --no-progress "$URL" && [ -f src.mkv ] && break
  rm -f src.f*.* 2>/dev/null
done
[ -f src.mkv ] || { echo "VIDEO DOWNLOAD FAILED"; exit 1; }
ffprobe -v error -show_entries stream=codec_type,width,height:stream_tags=language \
  -show_entries format=duration -of compact src.mkv
echo "DOWNLOAD OK: $WD"
