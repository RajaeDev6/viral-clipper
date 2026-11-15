# viral-clipper

A [Claude Code](https://claude.com/claude-code) skill that turns one long YouTube video into **many ready-to-post vertical shorts**: TikTok, YouTube Shorts and Instagram Reels.

Give it a link. Claude reads the whole transcript, picks the moments most likely to go viral, and renders each one as a 1080×1920 clip with:

- **a face-tracked crop**: the 9:16 frame follows the people on screen and cuts with the scenes, with no blurred bars
- **word-by-word captions**: big bold text with the word being spoken highlighted, in the style of popular clip channels
- **levelled audio**: loudness normalised for social platforms
- **a README of post captions and hashtags** for every clip

It can also **copy the style of any short you show it**: give it a reference and it matches the caption font, colours, size, position and pacing.

```
/viral-clipper https://www.youtube.com/watch?v=VIDEO_ID my-clips
```

---

## Requirements

| | Needed for | Installed by `install.sh`? |
|---|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | runs the skill | no, install it first |
| Python 3.9+ | rendering scripts | yes (via your package manager) |
| ffmpeg with libass | cutting, cropping, captions | yes (via your package manager) |
| Node.js, Deno or Bun | yt-dlp needs a JS runtime for YouTube | yes (installs Node.js) |
| yt-dlp | downloading videos | yes (into `.venv`, always the latest) |
| OpenCV + NumPy | face detection for the crop | yes (into `.venv`) |
| YuNet face model, caption fonts | crop and captions | yes (downloaded into `assets/`) |

Works on **Linux** (apt, pacman, dnf, zypper) and **macOS** (Homebrew). On Windows, use WSL.

Hardware: any modern CPU works, and no GPU is needed. Rendering takes about 2–4 minutes per clip on a 4-core machine. Keep about 3 GB of disk free for each source video.

---

## Install

```bash
git clone https://github.com/RajaeDev6/viral-clipper.git
cd viral-clipper
./install.sh
```

`install.sh` does all of this:
1. installs any missing system tools (ffmpeg, Node.js, Python) with your package manager. It may ask for your sudo password.
2. creates a private Python environment in `.venv/` with OpenCV, NumPy and yt-dlp
3. downloads the face-detection model and five caption fonts into `assets/`
4. runs a quick self-test
5. links the folder into `~/.claude/skills/viral-clipper` so Claude Code finds it

Options: `./install.sh --no-system` skips the package-manager step, and `./install.sh --no-link` skips linking into `~/.claude/skills`.

**To update:** `git pull && ./install.sh`. Re-running the installer is safe and also updates yt-dlp, which matters because YouTube changes often.

---

## Usage

Open Claude Code in the folder where you want the clips, then:

```
/viral-clipper <youtube-url> [output-folder] [options]
```

Or just ask in plain words:

> clip this into viral shorts https://www.youtube.com/watch?v=VIDEO_ID

### Examples

```bash
# as many clips as possible, default style, saved to ./mrbeast/
/viral-clipper https://www.youtube.com/watch?v=q6fgVVmdpgY mrbeast

# copy the look of a short you like
/viral-clipper https://www.youtube.com/watch?v=VIDEO_ID podcast --ref https://www.youtube.com/shorts/SHORT_ID

# use a built-in preset
/viral-clipper https://www.youtube.com/watch?v=VIDEO_ID podcast --style yellow-single-word

# extra wishes in plain English
/viral-clipper https://www.youtube.com/watch?v=VIDEO_ID gaming 10 clips, all under 60 seconds
/viral-clipper https://www.youtube.com/watch?v=VIDEO_ID interview show me the list first, I'll pick
```

### What you get

```
my-clips/
├── 01_He_called_his_MOM_mid_fight.mp4
├── 02_They_named_their_alliance_CORN.mp4
├── ...
├── README.md      # title, length, source timestamps and a ready-to-paste caption + hashtags per clip
└── .work/         # source video, captions, clip list (safe to delete afterwards)
```

---

## Using your own reference style

There are three ways, from easiest to most control:

**1. Point at a short.** Any YouTube Shorts / TikTok URL or a local video file works:

```
/viral-clipper <url> my-clips --ref https://www.youtube.com/shorts/SHORT_ID
/viral-clipper <url> my-clips --ref ~/Downloads/style-i-like.mp4
```
Claude downloads it, studies its frames (caption font, size, colours, position, words per line, length and pacing), writes a matching style, renders one clip, compares it with the reference and adjusts. Say *"save this style as `my-style`"* to reuse it later with `--style my-style`.

**2. Pick a preset** with `--style <name>`:

| Preset | Look |
|---|---|
| `default` | Bold Anton uppercase, 1–3 words, current word cycles green / yellow / red, pop-in |
| `yellow-single-word` | One huge word at a time, yellow highlight (podcast style) |
| `clean-white` | White sentence-case Poppins in the lower third, no highlight |
| `no-captions` | Just the face-tracked vertical crop |

**3. Write your own** JSON file in `styles/`. Include only the keys you want to change:

```json
{
  "font": "Bebas Neue",
  "font_size": 140,
  "highlight_colors": ["#00E5FF"],
  "position_y": 0.5,
  "max_words": 2
}
```

| Key | Meaning | Default |
|---|---|---|
| `captions` | burn in captions | `true` |
| `font` | font family. Bundled: `Anton`, `Bebas Neue`, `Poppins ExtraBold`, `Bangers`, `Luckiest Guy`. For another font, add its `.ttf` to `assets/fonts/` | `Anton` |
| `font_size` | size in px on the 1080×1920 frame | `132` |
| `uppercase` | ALL CAPS | `true` |
| `text_color` | `#RRGGBB` | `#FFFFFF` |
| `highlight_colors` | colour(s) for the spoken word, cycled per caption. `[]` = off | `["#39FF33","#FFE600","#FF4040"]` |
| `outline_color` / `outline` / `shadow` | text stroke colour, stroke px, shadow px | `#000000` / `9` / `5` |
| `position_y` | vertical position, 0 = top, 0.5 = middle, 1 = bottom | `0.68` |
| `max_words` / `max_chars` | how much text shows at once | `3` / `16` |
| `pop_animation` | small scale-in on each new caption | `true` |
| `strip_punctuation` | remove trailing `.` and `,` | `true` |
| `crop` | `face` (track people) or `center` | `face` |

---

## Using the scripts without Claude

The skill is a thin layer over plain scripts, which you can run yourself:

```bash
# 1. download video + word-timed captions
scripts/download.sh "https://www.youtube.com/watch?v=VIDEO_ID" work/

# 2. write work/moments.json yourself
#    [{"s": 75, "e": 108, "title": "My clip", "caption": "...", "tags": "#shorts"}]

# 3. render everything (resumes if interrupted)
.venv/bin/python scripts/batch.py work/ clips/ --jobs 2 --style styles/default.json

# or render a single clip
.venv/bin/python scripts/make_short.py work/src.mkv work/src.en-orig.vtt 75 108 out.mp4 --style styles/clean-white.json
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `HTTP Error 403` / `Requested format is not available` | Run `./install.sh` again to update yt-dlp. `download.sh` already tries several formats. |
| `HTTP Error 429: Too Many Requests` | YouTube is rate-limiting you. Wait a few minutes and try again. |
| Clip audio is in the wrong language | The video has AI dubs. `download.sh` picks the original track. If it still picks a dub, tell Claude which language you want. |
| No captions on the clips | The video has no English auto-captions. Clips still render, just without captions. |
| `No such filter: 'ass'` | Your ffmpeg was built without libass. Install your distro's full `ffmpeg` package. |
| Machine freezes or runs out of memory | Ask for fewer parallel jobs (`--jobs 1`). |
| Wrong font shows | The `font` value must match the font's family name. Check it with `fc-scan --format "%{family}\n" assets/fonts/*.ttf`. |

---

## Notes

- Only clip videos you have the rights to use, or that fall under fair use where you live. You are responsible for what you post.
- Captions come from YouTube's automatic transcript, so a word is occasionally wrong. Spot-check before posting.
- Fonts are from [Google Fonts](https://fonts.google.com) (OFL / Apache licensed). The face detector is [YuNet](https://github.com/opencv/opencv_zoo) from OpenCV Zoo.
