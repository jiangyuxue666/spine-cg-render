<div align="center">

# spine-cg-render

**Spine 2D 骨骼动画 → 动态 CG 视频渲染工具链**

Render Spine skeletal animations from Unity games into mp4 — frame-by-frame with the official spine-webgl runtime.

[![License](assets/badges/license-mit.png)](LICENSE)
[![Python](assets/badges/python.png)](https://www.python.org/)
[![ffmpeg](assets/badges/ffmpeg.png)](https://ffmpeg.org/)

</div>

游戏里打包的 Spine 骨骼动画是「图片 + atlas + 动画数据」，不是视频，没法直接提取播放。
本工具把**官方 Spine 运行时**跑在无头浏览器里逐帧离线渲染，再用 ffmpeg 编码成 mp4 —— 不开游戏、不录屏、完全可复现。

## 特性

- 🎬 **离线逐帧渲染**：完全确定，同帧重复渲染逐字节一致
- ⚙️ **全自动批处理**：多场景、数十段动画无人值守
- 🔁 **断点续传 + 崩溃恢复**：进度以磁盘帧为准，浏览器崩了自动续跑
- 🖼️ **双取景模式**：自动取景 / 作者视口取景（剔除场外草稿）
- 🧹 **动画智能过滤**：自动略过战斗动作、混合补帧等非 CG 内容

## 工作流程

```
游戏 bundle ──UnityPy──▶ 骨骼JSON + atlas + 贴图
                              │
              本地服务 + 无头浏览器（spine-webgl 官方运行时）
                              │  逐帧渲染（30fps）
                              ▼
                        PNG 帧序列 ──ffmpeg──▶ mp4（每动画一条）
```

## 快速开始

1. **解包** — 改 `scripts/extract_all.py` 的 `BASE` / `BUNDLE` / `SKELS`，运行
2. **起服务** — `python scripts/serve.py <served_root> <frames_dir> 8791`
3. **渲染** — `render.html` + spine-webgl.js（[CDN 下载](https://cdn.jsdelivr.net/npm/@esotericsoftware/spine-webgl@4.2.120/dist/iife/spine-webgl.js)）放入 `<served_root>/web/`，调用 `driver.py` 的 `run_skeleton()`
4. **编码** — 改 `scripts/encode_mp4.py` 的 `FRAMES` / `OUT`，运行

> 脚本中标 `← CHANGE` 的均为占位符，使用前改成实际路径。

**依赖**：Python 3（UnityPy + Pillow） · Chromium · ffmpeg

## 目录

```
├── SKILL.md          Agent 使用说明（流程 / 坑清单 / 复用清单）
├── scripts/          解包 · 服务器 · 渲染页 · 驱动 · 编码 · 说明生成
├── docs/pipeline.md  技术细节与实战踩坑（必读）
├── examples/         素材格式说明（不含版权资源）
└── assets/           README 徽章图片（PNG）
```

## 说明

- 本仓库**不含任何游戏素材**（版权原因），请仅对合法拥有的游戏文件使用
- 已在真实游戏上完整验证：15 个场景 / 96 段动画 / 约 15,500 帧
- 实现原理与十余条实战坑（相机、纹理、keep-alive、崩溃恢复等）见 **[docs/pipeline.md](docs/pipeline.md)**

## License

MIT · [LICENSE](LICENSE)
