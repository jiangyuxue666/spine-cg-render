# -*- coding: utf-8 -*-
"""Generate README (video guide) for the rendered CG folder."""
import os

# Example script — rewrite SECTIONS for your game.
OUT = r"<GAME_DIR>\CG_提取\动态CG"  # ← CHANGE
GAME = "<GAME_NAME>"  # ← CHANGE
README = os.path.join(OUT, "视频说明.txt")

# Example (fictional data) — replace with your game's scene list.
# Each entry: (folder name, description, [animation names in story order])
SECTIONS = [
    ("Scene_01", "示例场景 1（含循环段与过渡段）", [
        "start", "loop1", "Loop1-2", "loop2", "cum", "end", "full"]),
    ("Scene_02", "示例场景 2（多状态分支）", [
        "1-start", "1-start-alt", "2-normal", "2-alt", "3-over", "3-over-alt"]),
    ("Scene_03", "示例场景 3（单段整体动画）", ["animation"]),
]

lines = []
lines.append("=" * 60)
lines.append(f"{GAME} 动态 CG 视频说明")
lines.append("=" * 60)
lines.append("")
lines.append("【来源与生成方式】")
lines.append("这些视频不是录屏，也不是随机拼接：它们是从游戏文件中解包出的 Spine 骨骼动画")
lines.append("数据（骨骼JSON + atlas + 贴图），用官方 Spine 4.2 运行时逐帧渲染（30fps），")
lines.append("再由 ffmpeg 编码成 H.264 mp4。")
lines.append("")
lines.append("每个视频 = 游戏数据中的一个【具名动画段落】，按它自带的时长从头播到尾一次。")
lines.append("文件夹里的文件名就是游戏内部原始命名，未做过任何改名或重组。")
lines.append("")
lines.append("【命名规律 = 游戏内的推进顺序】")
lines.append("  数字（1、2、3…）   阶段编号，按数字顺序推进")
lines.append("  X-Y（如 1-2）      阶段之间的过渡动画")
lines.append("  (loop)             该阶段的循环动作")
lines.append("  start / end        开场 / 结束段")
lines.append("  cum                高潮/完结段")
lines.append("  full               作者做好的整段连播版（一条时间轴演完整场）")
lines.append("  其它命名           作者按其习惯命名的补充段（预览、细节特写等）")
lines.append("")
lines.append("【各场景内容（按游戏流程顺序排列）】")
for sk, desc, order in SECTIONS:
    lines.append("")
    lines.append(f"── {sk}：{desc}")
    d = os.path.join(OUT, sk)
    have = set()
    if os.path.isdir(d):
        have = {f[:-4] for f in os.listdir(d) if f.endswith(".mp4")}
    for i, name in enumerate(order, 1):
        mark = "✓" if name in have else "✗(缺)"
        lines.append(f"    {i:02d}. {name}.mp4  {mark}")
    extra = have - set(order)
    for name in sorted(extra):
        lines.append(f"    --. {name}.mp4  (未在预期顺序里)")
lines.append("")
lines.append("【未包含哪些？为什么？】")
lines.append("骨骼文件里含有大量非 CG 内容（角色的走路/攻击/跳跃/技能/受击等战斗动画，")
lines.append("以及运行时混合补帧（表情、附加部件等），它们不是独立 CG）。")
lines.append("本次只导出了 CG 场景实际用到的段落；如需角色全部战斗动作可以加做。")
lines.append("")
lines.append("【技术参数】")
lines.append("- 分辨率：逐场景不同，最长边 1440 像素（保持原场景构图比例）")
lines.append("- 帧率：30fps  编码：H.264（yuv420p, CRF 18）  背景：黑  无音轨（Spine 无音频）")
lines.append("- 每个视频播放一遍该动画；标注 (loop) 的为其一个完整循环周期")

with open(README, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("README written:", README)
print("total lines:", len(lines))
