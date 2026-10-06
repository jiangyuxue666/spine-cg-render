# 素材说明

本仓库不包含任何游戏素材（版权原因）。使用前需自备游戏文件，并通过 `scripts/extract_all.py` 进行解包。

## 解包后的目录结构

每个骨架对应一个文件夹：

```
spine_assets/
└── <骨架名>/
    ├── <骨架名>.json     ← Spine 骨骼数据（JSON 文本：骨骼 / 皮肤 / 动画时间轴）
    ├── <骨架名>.atlas    ← 图集描述（各贴图页文件名与部件坐标）
    ├── <页名>.png        ← 图集贴图（一张或多张，按 atlas 页数）
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

- 第一行（不缩进、以 `.png` 结尾）为贴图页文件名，其后的 `size:` 为该页尺寸
- 此后每个块为一个部件：部件名一行 + `bounds:x,y,w,h`（在页中的位置）
- `offsets`、`rotate`、`xy` 等为可选字段

## 注意事项

- 贴图实际分辨率可能与 atlas 标注的页尺寸不一致（Unity 导入时的缩放所致），属于正常情况，无需修改（原理详见 `docs/pipeline.md` 第 4 节）
