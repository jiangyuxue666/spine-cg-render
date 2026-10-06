# -*- coding: utf-8 -*-
"""Extract listed skeletons (json + atlas + page textures) from an Addressables bundle."""
import sys, os, json, re
sys.stdout.reconfigure(encoding='utf-8')
import UnityPy

BASE = r"<GAME_DIR>\<GAME>_Data\StreamingAssets\aa\StandaloneWindows64"  # ← CHANGE: bundle dir
BUNDLE = r"<BUNDLE_NAME>.bundle"  # ← CHANGE: the CG bundle's filename inside BASE
SPINE_OUT = r"<GAME_DIR>\CG_提取\spine_assets"  # ← CHANGE: asset output dir

# Example list — replace with the target game's skeleton names.
SKELS = ['Example_Scene_01', 'Example_Scene_02', 'Example_NPC_01']

env = UnityPy.load(os.path.join(BASE, BUNDLE))
texts = {}
texs = {}
for obj in env.objects:
    if obj.type.name == 'TextAsset':
        d = obj.read()
        s = d.m_Script
        raw = s.encode('utf-8') if isinstance(s, str) else bytes(s)
        if isinstance(s, str) and '\ufffd' in s:
            print("WARN: replacement chars in", d.m_Name)
        texts.setdefault(d.m_Name, []).append(raw)
    elif obj.type.name == 'Texture2D':
        d = obj.read()
        texs.setdefault(d.m_Name, []).append(d)

manifest = {}
for sk in SKELS:
    outdir = os.path.join(SPINE_OUT, sk)
    os.makedirs(outdir, exist_ok=True)
    js_l = texts.get(sk)
    at_l = texts.get(sk + '.atlas')
    if not js_l or not at_l:
        print(f"!! {sk}: missing json or atlas TextAsset")
        continue
    open(os.path.join(outdir, sk + '.json'), 'wb').write(js_l[0])
    atlas_bytes = at_l[0]
    open(os.path.join(outdir, sk + '.atlas'), 'wb').write(atlas_bytes)
    atlas_text = atlas_bytes.decode('utf-8', 'replace')
    pages = re.findall(r'^(\S+\.(?:png|jpg|jpeg|webp))\s*$', atlas_text, re.M)
    missing = []
    for page in pages:
        stem = page.rsplit('.', 1)[0]
        hits = texs.get(stem, [])
        if not hits:
            missing.append(page)
            continue
        d = max(hits, key=lambda x: x.m_Width * x.m_Height)
        img = d.image
        img.save(os.path.join(outdir, page))
    status = "OK" if not missing else f"MISSING {missing}"
    print(f"{sk}: json={len(js_l[0])}B atlas={len(atlas_bytes)}B pages={len(pages)} -> {status}")
    manifest[sk] = {'pages': pages, 'missing': missing}

with open(os.path.join(SPINE_OUT, 'extract_manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
print("\nAll skeletons extracted. Total missing pages:", sum(len(m['missing']) for m in manifest.values()))
