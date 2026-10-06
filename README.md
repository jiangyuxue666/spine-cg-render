<div align="center">

# spine-cg-render

**Spine 2D 骨骼动画 → 动态 CG 视频渲染工具链**

[![License](assets/badges/license-mit.png)](LICENSE)
[![Python](assets/badges/python.png)](https://www.python.org/)
[![ffmpeg](assets/badges/ffmpeg.png)](https://ffmpeg.org/)

</div>

## 简介

spine-cg-render 用于将 Unity 游戏中的 Spine 2D 骨骼动画资源（骨骼 JSON + atlas + 贴图）渲染为视频。工具基于官方 spine-webgl 运行时逐帧离线渲染，并通过 ffmpeg 编码为 mp4；全过程无需运行游戏或录屏，输出结果确定且可复现。

## 功能特性

- **离线逐帧渲染**：不依赖录屏与设备性能，相同输入可复现完全一致的输出
- **批量处理**：支持多场景、数十段动画的自动化批量渲染
- **断点续传与故障恢复**：以磁盘帧文件为进度基准，任务中断后可自动恢复
- **双取景模式**：支持自动取景与作者视口取景两种方式
- **动画过滤**：自动过滤战斗动作、混合补帧等非 CG 动画

## 环境要求

- Python 3，需安装 UnityPy 与 Pillow（用于资产提取）
- Chromium 浏览器（渲染脚本通过 CDP 接口驱动，可适配 Playwright 等常见自动化方案）
- ffmpeg（用于视频编码，需加入 PATH）

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

1. **提取资产**：修改 `scripts/extract_all.py` 中的 `BASE`、`BUNDLE`、`SKELS` 等配置后运行，从游戏 bundle 中提取骨骼 JSON、atlas 与贴图。
2. **启动本地服务**：`python scripts/serve.py <served_root> <frames_dir> 8791`
3. **渲染**：
   - 将 `render.html` 与 spine-webgl.js（[下载](https://cdn.jsdelivr.net/npm/@esotericsoftware/spine-webgl@4.2.120/dist/iife/spine-webgl.js)）放入 `<served_root>/web/`
   - 将提取结果放入 `<served_root>/spine_assets/<骨架名>/`
   - 打开 `web/render.html`，调用 `driver.py` 中的 `run_skeleton()` 逐骨架渲染
4. **编码输出**：修改 `scripts/encode_mp4.py` 中的 `FRAMES` 与 `OUT` 后运行，生成 mp4 文件。

> 脚本中标记 `← CHANGE` 的常量均为占位符，使用前请按实际环境修改。

## 目录结构

```
├── SKILL.md          Agent 使用说明（流程与注意事项）
├── scripts/          核心脚本（提取 / 服务 / 渲染 / 编码）
├── docs/pipeline.md  实现原理与注意事项
├── examples/         素材格式说明
└── assets/           README 徽章图片（PNG）
```

## 说明

- 本仓库不包含任何游戏素材。请确保仅对您合法持有的游戏文件使用本工具，并遵守所在地的法律法规与游戏许可条款。
- 工具已在真实游戏环境中完成验证：15 个场景、96 段动画、约 15,500 帧。
- 实现原理与注意事项详见 [docs/pipeline.md](docs/pipeline.md)。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
