# 素材说明

本仓库**不包含任何游戏素材**（版权原因）。要使用本工具，需要自备游戏文件，并用 `scripts/extract_all.py` 自行解包。

## 解包后的目录结构

每个骨架一个文件夹：

```
spine_assets/
└── <骨架名>/
    ├── <骨架名>.json     ← Spine 骨骼数据（文本 JSON：骨头/皮肤/动画时间轴）
    ├── <骨架名>.atlas    ← 图集描述（每页文件名 + 各部件矩形坐标）
    ├── <页名>.png        ← 图集贴图（1 张或多张，按 atlas 页数）
    └── ...
```

## atlas 文本格式（合成示例，非真实素材）

```
Example.png
size:1024,1024
filter:Linear,Linear
pma:true
head
bounds:2,2,200,200
torso
bounds:204,2,150,300
offsets:0,2,150,304
leg_left
bounds:2,210,120,400
```

- 第一行（不缩进、以 `.png` 结尾）是贴图页文件名，其后 `size:` 是页尺寸
- 之后每个块是一个部件：名字一行 + `bounds:x,y,w,h`（在页中的位置）
- `offsets`、`rotate`、`xy` 等为可选字段

## 注意

- 贴图实际分辨率可能与 atlas 标注的页尺寸不同（Unity 导入时缩放所致），这是正常的，无需修改（原理见 `docs/pipeline.md` 第 4 节）
- 素材文件请勿随本仓库一起提交（`.gitignore` 已默认忽略 `frames/` 等运行时产物）
