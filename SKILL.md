---
name: spine-cg-render
description: Use when rendering Spine CG animations from games to video.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [game-assets, unity, spine, animation, video-render, cg-extraction]
    related_skills: [game-cg-extract-unity, game-cg-extract]
---

# Spine 2D animation CGs → mp4 video (Unity games)

Turn Spine skeletal animation assets from Unity games (JSON/atlas TextAssets + page textures, as used by many spine-unity H-games) into rendered mp4 videos using the official **spine-webgl** runtime in a browser + ffmpeg.
Proven end-to-end on a real Unity + Spine game: 15 skeletons / 96 animations / ~15k frames / 68 MB output.
Any game whose bundle contains `*.atlas` TextAssets + spine-unity SkeletonDataAssets is a candidate — check the bundle list first (e.g. an `*_assets_all.bundle` group), then confirm TextAssets starting with `{"skeleton":{"spine":"4.2.x"...`.

## When to Use

- User asks to turn a game's Spine skeletal animations (not videos, not static images) into playable videos / "动态CG".
- A Unity game's asset bundle contains `.atlas` TextAssets plus spine-unity SkeletonDataAsset MonoBehaviours (common in many spine-unity H-games).
- Re-rendering / re-framing scenes from a previous extraction (assets still under `CG_提取\spine_assets\`).
- NOT for: static image CG extraction, or video files shipped in StreamingAssets (copy those directly).

## Pipeline

1. **Extract with UnityPy** (use a Python environment with UnityPy installed): for each skeleton `X`:
   - TextAsset `X` = Spine JSON; TextAsset `X.atlas` = atlas text; Texture2D pages matched by stem (page filename = first line of each atlas page block, e.g. `X_2.png` → Texture2D `X_2`).
   - Save `spine_assets/<X>/X.json`, `X.atlas`, `<page>.png` (use `d.image` — already display-oriented, do NOT flip).
   - Verify pairing via MonoBehaviours `<X>_Atlas` (read_typetree: `atlasFile` PPtr + `materials`) — material `_MainTex` = the page texture.
2. **Serve + render** (scripts/serve.py + scripts/render.html + scripts/driver.py):
   - server: GET static files; POST `/save?p=rel` writes frame bytes to disk (tmp+os.replace); **HTTP/1.1 keep-alive is mandatory** (see pitfalls).
   - render.html: loads spine-webgl IIFE build (`https://cdn.jsdelivr.net/npm/@esotericsoftware/spine-webgl@4.2.120/dist/iife/spine-webgl.js`, global `spine`), per atlas page creates `new spine.GLTexture(gl, img)` and attaches via `page.setTexture(tex)`; `new spine.TextureAtlas(text)` takes ONLY the text (no texture-loader arg in 4.2).
   - driver: background chunk tasks in the page + polling from the driver session (~5s JS-eval cap).
3. **Encode** (scripts/encode_mp4.py): `ffmpeg -framerate 30 -start_number 0 -i f%04d.png -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart out.mp4`.

## Critical settings & pitfalls

- **Camera**: do NOT flip — spine-webgl's default camera (`up.y=+1`) renders spine data upright. Setting `up.y=-1` mirrors everything. Verify orientation with any standing character (e.g. a menu stand illustration) before batch rendering.
- **spine-ts 4.2 API**: `skeleton.updateWorldTransform(spine.Physics.update)` — the physics argument is REQUIRED (throws `physics is undefined` otherwise).
- **Frame stepping**: per frame `state.update(1/fps); state.apply(skeleton); skeleton.updateWorldTransform(...); draw`. Deterministic; chunked+resumed renders are byte-identical to continuous (verified 180/180 frames).
- **Atlas page size ≠ bundled texture size** — harmless. Spine computes normalized UVs from atlas page dims, so content maps correctly onto whatever (rescaled/re-POT'd) texture Unity shipped. Never 'fix' this.
- **CDP `Runtime.evaluate` has a ~5s response cap**: never await long work in a single evaluate call. Kick a page-side async task (updates `R.__chunk = {running, done, err}`) and poll every ~1s; persist progress as frame FILES on disk and resume from the file count (fast-forward by replaying updates without capture; yield every ~250 frames).
- **HTTP/1.0 connection churn breaks Chrome under load**: with a connection-per-request server, `fetch` POSTs start failing ('Failed to fetch') after ~20-25s of ~0.5MB uploads. Fix: `protocol_version = 'HTTP/1.1'` + Content-Length on every response + ThreadingHTTPServer(daemon_threads=True, request_queue_size=128). After the fix, 150×512KB posts complete in 0.5s. Also keep a per-frame POST retry (250ms backoff ×6) as belt-and-braces.
- **Chrome crashes every ~1-2 min** under sustained software-WebGL + PNG encode: make everything resumable (per-animation frame dirs; skip completed frames by file count; reload the page between skeletons; re-kick after disconnects). Losing a browser call is normal — just resume; frame files are the source of truth.
- **Framing / off-stage scratch art**: default framing = union of content bounds across sampled animation times (+7% pad). Rigs often contain *scratch copies* (spare characters/parts parked outside the intended view) → union framing exposes them. The JSON `skeleton.{x,y,width,height}` is the authored viewport/composition window: add a `frame:'viewport'` mode and use it for affected scenes. But NOT everywhere — some scenes legitimately extend beyond the viewport (e.g. effects that extend above frame); spot-check one frame per skeleton (render it and inspect visually) and reframe only confirmed cases. Also spot-check for inverted characters and garbled regions.
- **Animation filtering**: rigs reused from gameplay contain non-CG animations. Skip gameplay sets by name/prefix (e.g. `Mix/`, `Attack/`, `Jump/`, `Skill/` and their variants; `walk|walk2|idle|mix`; `hurt_*`); keep numbered stages and author-named CG segments (`start` / `full` / `cum` / `end`, transitions, previews, etc.).
- **Filename sanitization**: replace `/:*?"<>|` with `_`; CJK filenames are fine on NTFS and in ffmpeg.
- **Browser driver daemon wedged**: after disconnects the daemon may fail to restart because of a stale port/lock file in its runtime directory (Windows: `PermissionError`). Fix: end the driver's own python/chrome processes (match their command lines), clear the runtime directory, retry. Never kill every browser process — filter by the driver's command-line markers.
- Open a fresh page per skeleton to free renderer memory and reduce crash frequency.

## Reuse checklist (adjust before running on a new game)

- Paths are hardcoded per task: update `BASE` (bundle dir) + `BUNDLE` (bundle filename) + `SKELS` (skeleton names) in `extract_all.py`; `FRAMES` (frames root) + `OUT` (video output dir) in `encode_mp4.py`; `FRAMES_ROOT` in `driver.py`. `serve.py` takes its paths via argv (root, save-dir, port).
- Review the animation filter lists in `driver.py` (`SKIP_EXACT` / `SKIP_PREFIXES` / `HURT_RE`) — tuned for rigs that mix CG content with gameplay animations; adjust per game.
- Server layout expected by `render.html`/`driver.py`: the served root must contain `web/render.html` (+ spine-webgl.js) and `spine_assets/<Skel>/`; rendered frames are POSTed to `/save?p=<relative path>` and land under the save-root.
- Order of operations: extract (`extract_all.py`) → start `serve.py` (background) → open `web/render.html` in the browser (CDP session) → per skeleton `run_skeleton()` (from `driver.py`) → `encode_mp4.py` → `make_readme.py`.
- Keep the game folder read-only; all outputs go to `CG_提取\` inside the game folder, frames may live in scratch and be deleted after encoding.
- Always sanity-render ONE small skeleton end-to-end first (init → a few frames → ffprobe + visual spot-check) before batch rendering everything.
- The browser driver's own daemon/processes are tool infrastructure — when the daemon wedges, end only processes matching its command-line markers.

## Verification checklist

- Frame count per animation == round(duration × fps); spot-check with ffprobe (`duration`, `nb_frames`, `avg_frame_rate=30/1`).
- Extract 2-3 mid frames from the FINAL mp4s (`ffmpeg -ss <t> -i out.mp4 -frames:v 1 x.png`) and visually check: coherent scene, correct orientation, no scratch duplicates, no garbled regions.

## Output layout

- `<game>\CG_提取\动态CG\<Skeleton>\<anim>.mp4` — final videos (30 fps, h264, black background, one video per animation).
- `<game>\CG_提取\spine_assets\<Skeleton>\` — extracted json/atlas/png (kept for re-renders).
- `<game>\CG_提取\web\` — render.html + spine-webgl.js (kept; re-runnable by restarting scripts/serve.py).

## Support files

- `scripts/extract_all.py` — UnityPy extraction of all skeletons from a bundle.
- `scripts/serve.py` — static + frame-sink HTTP server (keep-alive).
- `scripts/render.html` — spine-webgl renderer page (chunked background render, viewport/auto framing).
- `scripts/driver.py` — browser-driver script (run in a CDP session): init/run skeleton with polling + resume.
- `scripts/encode_mp4.py` — frames → mp4 batch encoder (skips already-encoded, mtime-based).
- `scripts/make_readme.py` — generates the per-scene video guide (`视频说明.txt`) in the output folder.
