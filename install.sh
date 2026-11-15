#!/usr/bin/env bash
# viral-clipper installer
#   - installs system tools if missing (ffmpeg, node, python3) via your package manager
#   - creates .venv with opencv, numpy, yt-dlp
#   - downloads the face-detection model and caption fonts into assets/
#   - links this folder into ~/.claude/skills/viral-clipper so Claude Code can use it
#
# usage: ./install.sh            (full install)
#        ./install.sh --no-system (skip package-manager installs)
#        ./install.sh --no-link   (don't link into ~/.claude/skills)
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
NO_SYSTEM=0; NO_LINK=0
for a in "$@"; do
  case "$a" in --no-system) NO_SYSTEM=1 ;; --no-link) NO_LINK=1 ;; esac
done
say() { printf "\033[1;36m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!!\033[0m %s\n" "$*"; }

# ---------------------------------------------------------------- system packages
need=()
command -v python3 >/dev/null || need+=(python)
command -v ffmpeg  >/dev/null || need+=(ffmpeg)
command -v node >/dev/null || command -v deno >/dev/null || command -v bun >/dev/null || need+=(node)
command -v curl    >/dev/null || need+=(curl)

if [ ${#need[@]} -gt 0 ]; then
  if [ $NO_SYSTEM = 1 ]; then
    warn "missing: ${need[*]} (skipped because of --no-system)"
  else
    say "installing system packages: ${need[*]}"
    SUDO=""; [ "$(id -u)" != 0 ] && command -v sudo >/dev/null && SUDO="sudo"
    map() { # generic name -> package name per manager
      case "$1:$2" in
        python:apt) echo "python3 python3-venv python3-pip" ;; python:pacman) echo "python python-pip" ;;
        python:dnf) echo "python3 python3-pip" ;; python:brew) echo "python" ;;
        node:apt|node:dnf) echo "nodejs" ;; node:pacman) echo "nodejs" ;; node:brew) echo "node" ;;
        *) echo "$1" ;;
      esac
    }
    if command -v brew >/dev/null; then pm=brew; inst="brew install"
    elif command -v apt-get >/dev/null; then pm=apt; $SUDO apt-get update -y; inst="$SUDO apt-get install -y"
    elif command -v pacman >/dev/null; then pm=pacman; inst="$SUDO pacman -S --needed --noconfirm"
    elif command -v dnf >/dev/null; then pm=dnf; inst="$SUDO dnf install -y"
    elif command -v zypper >/dev/null; then pm=zypper; inst="$SUDO zypper install -y"
    else pm=""; fi
    if [ -z "$pm" ]; then
      warn "no supported package manager found. Please install: ${need[*]}"
    else
      pkgs=""; for n in "${need[@]}"; do pkgs="$pkgs $(map "$n" "$pm")"; done
      $inst $pkgs
    fi
  fi
fi

command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
command -v ffmpeg  >/dev/null || { echo "ffmpeg is required"; exit 1; }
ffmpeg -hide_banner -filters 2>/dev/null | grep -q " ass " || warn "your ffmpeg has no libass ('ass' filter): captions will fail. Install a full ffmpeg build."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "python 3.9+ required"; exit 1; }

# ---------------------------------------------------------------- python venv
say "creating python environment (.venv)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt

# ---------------------------------------------------------------- assets
mkdir -p assets/fonts
dl() { [ -s "$2" ] || { curl -fsSL -o "$2.tmp" "$1" && mv "$2.tmp" "$2"; }; }
say "downloading face-detection model"
dl "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" \
   assets/face_detection_yunet_2023mar.onnx
say "downloading caption fonts"
GF="https://github.com/google/fonts/raw/main"
for f in ofl/anton/Anton-Regular.ttf ofl/bebasneue/BebasNeue-Regular.ttf ofl/poppins/Poppins-ExtraBold.ttf \
         ofl/bangers/Bangers-Regular.ttf apache/luckiestguy/LuckiestGuy-Regular.ttf; do
  dl "$GF/$f" "assets/fonts/$(basename "$f")"
done
chmod +x scripts/*.sh scripts/*.py

# ---------------------------------------------------------------- self-test
say "self-test"
.venv/bin/python -c "
import cv2, numpy
d = cv2.FaceDetectorYN.create('assets/face_detection_yunet_2023mar.onnx', '', (320, 320))
print('  opencv', cv2.__version__, '- face detector OK')" 2>&1 | grep -v WARN
echo "  yt-dlp $(.venv/bin/yt-dlp --version)"
echo "  $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"

# ---------------------------------------------------------------- link skill
if [ $NO_LINK = 0 ]; then
  SK="$HOME/.claude/skills/viral-clipper"
  mkdir -p "$HOME/.claude/skills"
  if [ "$(cd "$SK" 2>/dev/null && pwd -P)" = "$(pwd -P)" ]; then
    say "already installed at $SK"
  elif [ -e "$SK" ] && [ ! -L "$SK" ]; then
    warn "$SK exists and is not a link; leaving it alone"
  else
    ln -sfn "$ROOT" "$SK"
    say "linked $SK -> $ROOT"
  fi
fi

say "done. In Claude Code run:  /viral-clipper <youtube-url> [output-folder]"
