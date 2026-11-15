---
name: viral-clipper
description: Clip a long YouTube video into as many viral vertical shorts as possible (1080x1920, face-tracked crop, word-by-word highlighted captions, post captions + hashtags). Can copy the style of any reference short the user gives. Use when the user gives a YouTube URL and wants shorts / clips / viral clips / TikToks / Reels, or types /viral-clipper.
argument-hint: <youtube-url> [output-folder] [--ref <reference-short-url>] [--style <preset>] [extra wishes]
---

# viral-clipper

Turn one long YouTube video into many ready-to-post vertical shorts.

`SKILL_DIR` below means the directory this SKILL.md is in (Claude Code shows it as the skill's base directory). Everything runs from there:

| Path | What it does |
|---|---|
| `SKILL_DIR/scripts/download.sh URL WORKDIR` | gets `src.mkv` (≤1440p, original audio), `src.en-orig.vtt` (word timings), `src.info.json` |
| `SKILL_DIR/scripts/reference.sh URL_OR_FILE OUTDIR` | downloads a reference short and makes contact sheets of its frames |
| `SKILL_DIR/scripts/batch.py WORKDIR OUTDIR [--jobs N] [--style FILE]` | renders every clip in `WORKDIR/moments.json`, writes `OUTDIR/README.md` |
| `SKILL_DIR/scripts/make_short.py SRC VTT START END OUT [--style FILE]` | renders one clip (redo a single clip) |
| `SKILL_DIR/styles/*.json` | caption style presets (`default` = bold karaoke captions) |
| `SKILL_DIR/.venv/bin/python` | python to run the scripts with |

If `SKILL_DIR/.venv` or `SKILL_DIR/assets` is missing, run `SKILL_DIR/install.sh` first and tell the user.

## 1. Parse the request

- **URL** (required).
- **Output folder**: the name given; if none, use the channel name from `src.info.json` (lowercase, hyphens). Create it under the current working directory unless the user gives a full path. The work dir is `<outdir>/.work/`.
- **Style**, first match wins:
  1. `--ref <url or file>` or "make it like this short: <url>" → copy that style (step 3)
  2. `--style <name>` → `SKILL_DIR/styles/<name>.json`
  3. nothing → `SKILL_DIR/styles/default.json`
- **Extra wishes**: "under 60s", "10 clips", "no captions", "let me pick" (show the list and wait before rendering), etc.

## 2. Download (in the background)

```
bash SKILL_DIR/scripts/download.sh "<url>" "<workdir>"
```
It handles: the JS challenge runtime (deno/node/bun), picking the **original** audio track instead of AI dubs, falling back across formats on HTTP 403, and fetching captions separately to avoid HTTP 429. Wait for `DOWNLOAD OK`. If it fails, show the user the last lines of output.

## 3. Copy a reference style (only if a reference was given)

```
bash SKILL_DIR/scripts/reference.sh "<ref>" "<workdir>/ref"
```
Look at `sheet_full.jpg`, `sheet_dense.jpg` and `frame_big.jpg` and write `<workdir>/style.json` with only the keys that differ from the defaults:

| key | meaning | default |
|---|---|---|
| `captions` | burn in captions at all | `true` |
| `font` | family name. Bundled: `Anton`, `Bebas Neue`, `Poppins ExtraBold`, `Bangers`, `Luckiest Guy`. For another Google Font, download its .ttf into `SKILL_DIR/assets/fonts/` and use its family name (`fc-scan --format "%{family}\n" file.ttf`) | `Anton` |
| `font_size` | px on a 1080×1920 frame. Caption cap-height ≈ 0.7×size | `132` |
| `uppercase` | | `true` |
| `text_color` | `#RRGGBB` | `#FFFFFF` |
| `highlight_colors` | colour(s) of the word being spoken, cycled per chunk. `[]` = none | green, yellow, red |
| `outline_color`, `outline`, `shadow` | stroke colour, stroke px, shadow px | black, 9, 5 |
| `position_y` | caption centre as a fraction of height (0.5 = middle) | `0.68` |
| `max_words`, `max_chars` | words / characters on screen at once | `3`, `16` |
| `pop_animation` | scale-in when a new chunk appears | `true` |
| `strip_punctuation` | drop trailing `.` `,` | `true` |
| `crop` | `face` (track faces) or `center` | `face` |

Also note the reference's **length and pacing** and use them when picking moments. After the first clip renders, compare it side by side with `frame_big.jpg` and adjust. To keep a style for next time, save it as `SKILL_DIR/styles/<name>.json` when the user asks.

## 4. Read the transcript and pick moments

Build a readable `[mm:ss] text` transcript from the VTT: strip the tags, drop rolling duplicate lines and `>>` markers. Creator captions (`yt-dlp --write-subs --sub-langs en --skip-download`) are cleaner to read when they exist. Read **all** of it.

Pick as many strong moments as the video supports (about 1 clip per 2 minutes of good content, often 15–25 for a 30+ minute video). Good shorts:
- **hook in the first 1–2 seconds**: a shocking line, a question, conflict, a big number, a famous name
- **self-contained**: setup → payoff, ending right after the payoff or reaction
- funny lines, betrayals, twists, emotional confessions, reveals, money moments, the winner or result
- **20–75 s** (≤ 60 s if the user wants TikTok/Reels); no sponsor reads, intros or dead air

Write `<workdir>/moments.json` in story order:
```json
[{"s": 75, "e": 108,
  "title": "He called his MOM mid-fight",
  "caption": "Bro really yelled for his MOM in the middle of the Hunger Games 😭",
  "tags": "#mrbeast #hungergames #funny #shorts"}]
```
`s` = start of the first line, `e` = start of the first line **not** included, both in seconds. batch.py snaps them to word boundaries. Titles become filenames; captions and tags go in the README, written to drive comments.

If the user wants to pick, show a numbered table (title, length, why it works) and wait.

## 5. Render (in the background)

```
cd SKILL_DIR && nohup .venv/bin/python scripts/batch.py "<workdir>" "<outdir>" --jobs 2 > "<workdir>/batch.log" 2>&1 &
```
Use `--jobs 2` on 4 cores or ≤ 8 GB RAM, and `--jobs 3–4` on bigger machines. Each clip takes about 2–4 minutes. Watch `batch.log` for `done`, `FAILED` and `ALL DONE`. Re-running skips finished clips. To stop it, kill by PID; `pkill -f batch.py` would also kill the calling shell.

## 6. Check quality on the first finished clip

```
ffmpeg -v error -ss 8 -i clip.mp4 -frames:v 1 -vf scale=270:-1 a.jpg   # 3–4 timestamps, then hstack
```
Look at the frames. Captions should be readable with no junk tokens, and faces and action should be inside the crop. If a reference was given, the clip should match it. If something is wrong, change the style or script, delete the bad clips and re-run.

## 7. Report

Give a table of the clips (number, title, length), the 4–5 you would post first, the output folder, and caveats: auto-caption mistakes, clips over 60 s, anything skipped.
