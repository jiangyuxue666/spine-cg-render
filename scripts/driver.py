# -*- coding: utf-8 -*-
"""Driver executed inside browser_exec calls (exec this file, then call functions).
Provides run_skeleton(dirname, name, ...) which renders all CG animations frame-by-frame
into the frames root via POST /save, with resumable chunks."""
import json, time, os, re

FRAMES_ROOT = r"<FRAMES_ROOT>"  # ← CHANGE: dir where frame PNGs are saved (a scratch/temp dir is fine)
# Animation filter tuned for gameplay-reused CG rigs — review/adjust per game.
SKIP_EXACT = {'walk', 'walk2', 'idle', 'mix'}
SKIP_PREFIXES = ('Mix/', 'Attack/', 'Jump/', 'Skill/')  # add per-game variants (weapons, forms, ...) as needed
HURT_RE = re.compile(r'^(hurt_\d|heavily_hurt_)')

def sanitize(name):
    return ''.join('_' if ch in '/\\:*?"<>|' else ch for ch in name).strip() or 'animation'

def is_cg(n):
    if n in SKIP_EXACT:
        return False
    if n.startswith(SKIP_PREFIXES):
        return False
    if HURT_RE.match(n):
        return False
    return True

def js_retry(expr, tries=4, delay=3.0):
    """js() with retry on transient harness/ws errors."""
    last = None
    for k in range(tries):
        try:
            return js(expr)
        except Exception as e:
            last = e
            try:
                time.sleep(delay)
            except Exception:
                pass
    raise last

def init_skel(dirname, name, max_side=1440, fliptex=False, timeout_ticks=400, frame=None):
    opts = {"dir": f"/spine_assets/{dirname}", "name": name, "maxSide": max_side, "flipCam": False, "flipTex": fliptex}
    if frame:
        opts['frame'] = frame
    js_retry("(() => { window.__initState='running'; R.init(%s).then(()=>{window.__initState='done';}).catch(e=>{window.__initState='ERR: '+(e&&e.message||e);}); return 'kicked'; })()" % json.dumps(opts))
    for i in range(timeout_ticks):
        st = js_retry("JSON.stringify({s:window.__initState, e:R.error})")
        d = json.loads(st)
        if d.get('s') != 'running':
            if str(d.get('s', '')).startswith('ERR'):
                print('INIT ERR', d)
                return None
            break
        time.sleep(0.5)
    info = json.loads(js_retry("JSON.stringify(R.info)"))
    return info

def render_range(anim, fps, rel, start, end, poll_s=1.0, max_s=900):
    """Kick a background chunk render and poll until finished. Returns dict."""
    r = js_retry("R.renderChunkBg(%s, %d, %s, %d, %d)" % (json.dumps(anim), fps, json.dumps(rel), start, end))
    if not (isinstance(r, str) and r == 'started'):
        return {'err': f"kick failed: {r}"}
    t0 = time.time()
    last_print = 0
    while True:
        st = js_retry("JSON.stringify({r:R.__chunk.running, d:R.__chunk.done, e:R.__chunk.err})")
        try:
            d = json.loads(st)
        except Exception:
            d = {}
        if d.get('e'):
            return {'err': d['e']}
        if d.get('r') is False:
            return {'done': d.get('d')}
        if time.time() - t0 > max_s:
            return {'timeout': True, 'done': d.get('d')}
        if time.time() - last_print > 12:
            print(f"    ..{rel} {d.get('d')}/{end-start}", flush=True)
            last_print = time.time()
        time.sleep(poll_s)

def run_skeleton(dirname, name, max_side=1440, fps=30, chunk=300, frame=None):
    info = init_skel(dirname, name, max_side=max_side, frame=frame)
    if not info:
        return None
    anims = [a for a in info['anims'] if is_cg(a['name'])]
    print(f"[{name}] canvas={info['canvas']} total_anims={len(info['anims'])} -> cg_anims={len(anims)}")
    results = []
    for a in anims:
        an = a['name']
        dur = float(a['duration'] or 0)
        total = max(2, min(int(round(dur * fps)) if dur > 0 else 2, 5400))
        rel = f"{dirname}/{sanitize(an)}"
        pdir = os.path.join(FRAMES_ROOT, dirname, sanitize(an))
        existing = len(os.listdir(pdir)) if os.path.isdir(pdir) else 0
        print(f"  [{name}] >> {an} ({dur:.2f}s, {total}f, have {existing})", flush=True)
        if existing >= total:
            results.append({'anim': an, 'frames': total, 'status': 'exists'})
            continue
        start = existing
        ok = True
        zero_progress = 0
        while start < total:
            end = min(total, start + chunk)
            rr = render_range(an, fps, rel, start, end)
            cnt = len(os.listdir(pdir)) if os.path.isdir(pdir) else 0
            if cnt <= start:
                zero_progress += 1
                if zero_progress >= 3:
                    ok = False
                    results.append({'anim': an, 'frames': total, 'status': f"ERR stuck at {start}: {rr}"})
                    break
            else:
                zero_progress = 0
            start = cnt
        if ok:
            results.append({'anim': an, 'frames': total, 'status': 'rendered'})
    print("RESULT: " + json.dumps({'skel': name, 'canvas': info['canvas'], 'anims': results}, ensure_ascii=False))
    return results
