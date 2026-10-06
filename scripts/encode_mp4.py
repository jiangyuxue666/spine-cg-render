# -*- coding: utf-8 -*-
"""Encode rendered frame sequences to mp4. Run with any Python 3 (ffmpeg on PATH)."""
import os, subprocess, shutil

FRAMES = r"<FRAMES_ROOT>"  # ← CHANGE: frame dir from the render step
OUT = r"<GAME_DIR>\CG_提取\动态CG"  # ← CHANGE: video output dir
SKIP_DIRS = set()  # optional: extra non-scene subdirectories to skip

ffmpeg = shutil.which('ffmpeg')
if not ffmpeg:
    cand = r"<OPTIONAL_DIR_TO_SEARCH_FOR_FFMPEG>"  # ← CHANGE or delete this fallback
    for root, dirs, files in os.walk(cand):
        if 'ffmpeg.exe' in files:
            ffmpeg = os.path.join(root, 'ffmpeg.exe')
            break
print("ffmpeg:", ffmpeg)

encoded = []
skipped = []
for skel in sorted(os.listdir(FRAMES)):
    sdir = os.path.join(FRAMES, skel)
    if not os.path.isdir(sdir) or skel in SKIP_DIRS:
        continue
    for anim in sorted(os.listdir(sdir)):
        adir = os.path.join(sdir, anim)
        if not os.path.isdir(adir):
            continue
        frames = sorted(f for f in os.listdir(adir) if f.startswith('f') and f.endswith('.png'))
        if not frames:
            continue
        n = len(frames)
        outdir = os.path.join(OUT, skel)
        os.makedirs(outdir, exist_ok=True)
        outpath = os.path.join(outdir, anim + '.mp4')
        if os.path.exists(outpath) and os.path.getmtime(outpath) > os.path.getmtime(adir):
            skipped.append(anim)
            continue
        cmd = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
               '-framerate', '30', '-start_number', '0',
               '-i', os.path.join(adir, 'f%04d.png'),
               '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', outpath]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"FFMPEG FAIL {skel}/{anim}: {r.stderr[-400:]}")
        else:
            sz = os.path.getsize(outpath)
            encoded.append(f"{skel}/{anim}: {n} frames, {sz/1048576:.1f} MB")
print("encoded:")
for e in encoded:
    print("  ", e)
print(f"total encoded: {len(encoded)}; skipped(existing): {len(skipped)}")
