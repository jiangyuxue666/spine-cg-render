# 技术细节与实战踩坑记录

本文记录 spine-cg-render 的工作原理、关键实现与实战踩过的坑，供二次开发和排错使用。

---

## 1. 资产形态：Spine 游戏里究竟是什么

Unity + spine-unity 的游戏，把 Spine 资产打包进 bundle 后的形态：

| 部件 | Unity 类型 | 说明 |
|------|-----------|------|
| 骨骼数据 | `TextAsset`（名为骨架名，内容是 JSON） | 骨头 / 皮肤 / 槽位 / 全部动画时间轴 |
| 图集描述 | `TextAsset`（名为 `<骨架>.atlas`） | 每个贴图页的文件名 + 每个部件的矩形坐标 |
| 图集贴图 | `Texture2D`（每页一张） | 按页名与 atlas 一一对应 |

**交叉验证方法**：找 `<骨架>_Atlas` 这个 MonoBehaviour，`read_typetree()` 读它的 `atlasFile`（指向 atlas TextAsset）和 `materials`（每个材质 `_MainTex` 指向对应页的 Texture2D）——材质映射能 100% 确认"页 ↔ 贴图"配对。

判断一个 bundle 是不是 Spine 资产：看 TextAssets 是否以 `{"skeleton":{"spine":"4.2.x"...` 开头。

## 2. 为什么必须逐帧渲染，而不是解包/录屏

- **解包**只能得到静止的"零件"，动画在骨骼时间轴里，静态导出无法播放；
- **录屏**受窗口分辨率、性能、遮挡影响，有掉帧与压缩损失，且难以批量；
- **逐帧渲染**：由引擎按固定时间步长（1/30s）计算姿势 → 绘制 → 抓帧。完全确定、无损、可控取景，可无人值守批量执行。

## 3. 渲染核心（spine-webgl 4.2 官方运行时）

在页面中加载官方 IIFE 构建：

```html
<script src="/web/spine-webgl.js"></script>
<!-- https://cdn.jsdelivr.net/npm/@esotericsoftware/spine-webgl@4.2.120/dist/iife/spine-webgl.js -->
```

四个关键点（都踩过）：

1. **TextureAtlas 构造函数只吃文本**：`new spine.TextureAtlas(atlasText)`（4.2 没有 textureLoader 参数）。贴图要手动逐页挂：
   ```js
   const atlas = new spine.TextureAtlas(atlasText);
   for (const page of atlas.pages) {
     page.setTexture(new spine.GLTexture(gl, img));   // img 需预先加载完成
   }
   ```
   没有 `setTexture` 之前一切"正常"但画面全黑，且不报错。
2. **`updateWorldTransform(spine.Physics.update)`**：4.2 起物理参数必传，否则直接抛 `physics is undefined`。
3. **相机不要翻转**：默认 `camera.up = (0,1,0)` 就是正确的（渲染 spine 数据直立）。设 `up.y=-1` 会把整个画面上下镜像。方向校准用任何"站立角色"（如主菜单立绘）目测最稳。
4. **PMA 纹理**：atlas 标了 `pma:true`，绘制用 `drawSkeleton(skeleton, true)`（预乘 alpha 混合）。

**确定性步进**（每帧）：

```js
state.update(1/fps);            // 推进虚拟时钟
state.apply(skeleton);          // 摆好姿势
skeleton.updateWorldTransform(spine.Physics.update);
draw();                         // 绘制
// 抓帧：canvas.toBlob('image/png') → POST 到本地服务落盘
```

同一动画从 0 连续渲染  与  "分两段渲染再拼"  产出的帧**逐字节一致**（曾用 180 帧做过回归验证），所以断点续传是安全的。

## 4. 纹理尺寸之谜（atlas 页尺寸 ≠ 贴图实际尺寸）

常见现象：atlas 里写 `size:2735,866`，bundle 里的贴图却是 2048×512。原因：Unity 导入时按"最大尺寸缩放 + 非2幂取整"，改了贴图实际分辨率。

**为什么无害**：spine 运行时按 atlas 标注的页尺寸计算**归一化 UV**，只要贴图内容是原图的均匀缩放，采样位置就是对的。**不要试图"修"这个差异**（比如重新缩放贴图），只会弄坏。

## 5. 工程化要点（为什么这么写）

### 5.1 HTTP 服务器必须 keep-alive

渲染时每秒要 POST 上传几帧、每帧 0.5MB 左右。若服务器用 HTTP/1.0 一连接一请求：

- 每 20–25 秒必然出现一次 `fetch: Failed to fetch`（实测第 36 次上传、21.7 秒时挂掉）；
- 吞吐极低（~0.85 MB/s）。

换成 `HTTP/1.1` + 每响应带 `Content-Length` + 线程化服务器后，150 × 512KB 上传总共 **0.5 秒**、零失败。

```python
protocol_version = 'HTTP/1.1'
ThreadingHTTPServer.daemon_threads = True
ThreadingHTTPServer.request_queue_size = 128
```

另配上传重试（250ms 退避 ×6）兜底。

### 5.2 浏览器接口有 5 秒调用上限

驱动层（CDP `Runtime.evaluate`）单次调用约 5 秒就必须返回。所以**任何长时间工作都不能在一次调用里干等**：

- 页面里开一个**后台任务**渲染分块，持续更新 `R.__chunk = {running, done, err}`；
- 驱动侧每 1 秒轮询一次进度；
- 分块默认 300 帧（约 20–40 秒/块）。

### 5.3 断点续传 = 以磁盘帧文件为准

要求浏览器"精确续跑"不可靠，所以：

- 每帧落盘文件名 `f0000.png, f0001.png, ...`；
- 续传时数一下现有帧数 `existing`，快进（只 update/apply 不抓帧）到 `existing`，再从那里继续；
- 快进循环每 250 帧让出一次事件循环（避免长时间阻塞页面）；
- 单动画重试连续 3 次零进度才放弃并记录。

### 5.4 崩溃是常态，恢复是设计

软件 WebGL 持续高负载下，Chrome 约每 1–2 分钟崩一次（整只浏览器进程退出）。所以整条链路设计成"崩了无损失"：

- 帧文件是唯一事实来源；
- 每骨架开新页面重来（顺手释放渲染内存）；
- 自动化侧捕获断连，重新拉起后从文件数续跑——崩溃只浪费几十秒。

### 5.5 浏览器 daemon 卡死时的清理

自动化工具的后台 daemon 有时会因残留端口文件（`~/.config/browser-harness/runtime/bu-default.port`）拒绝重启（Windows 下报 `PermissionError`）。清理方法：结束命令行里含 harness 标记的 python / chrome 进程（**别误杀用户自己的浏览器**），删除 runtime 目录内容，重试。

## 6. 取景（最重要的一步，决定成片观感）

- **自动取景**：采样全部动画各时间点的内容包围盒，取并集 + 7% 边距。稳妥，但会把**场外草稿**框进来——很多骨骼里会"停着"没用的备用素材（多余的整只角色、散落的小部件），在游戏里它们位于镜头之外。
- **视口取景**：`JSON.skeleton.{x,y,width,height}` 是作者在 Spine 编辑器里设定的取景窗，通常就是构成窗口。用 `frame:'viewport'` 模式即可裁掉场外草稿。
- **判断方法**：每个骨架先渲染一帧（可叠加红色视口框）+ 视觉检查（人眼或视觉模型）：
  - 出现"重复的整只角色/漂浮零件" → 即场外草稿 → 改视口取景重渲；
  - 内容只是自然溢出视口（如特效超出画面顶部）→ 保持自动取景，裁了反而丢内容。
- 实战结论：不是所有场景都该用视口取景，**逐场景抽查**最稳妥。

## 7. 动画过滤（哪些是 CG、哪些不是）

游戏复用的骨骼里混着大量非 CG 动画。按命名规则过滤（可按游戏微调）：

- **跳过前缀**：`Mix/`（运行时混合补帧）、`Attack/`、`Jump/`、`Skill/` 及其武器/形态变体（按实际游戏补充）
- **跳过名称**：`walk`、`walk2`、`idle`、`mix`、`hurt_*`、`heavily_hurt_*`
- **保留**：编号段（`1`、`2(loop)`）、过渡段（`1-2`）、`start`、`cum`、`end`、`full`（整段连播）、作者命名的预览/细节段等

命名规律就是"剧本"：数字=阶段序，`X-Y`=阶段间过渡，`(loop)`=循环段。

## 8. 性能参考

| 环节 | 数值（软件 WebGL，本机参考） |
|------|------|
| 单帧渲染+抓帧+上传 | 约 70–150 ms |
| 15,500 帧纯渲染 | 约 40–60 分钟 |
| 96 段编码（libx264, CRF18） | 约 4 分钟 |
| 采样滑落 | 约 4–6 GB 中间帧图（编码后可删） |

## 9. 验收方法

1. **帧数核对**：帧数 = `round(动画时长 × 30)`；`ffprobe` 抽查 `duration / nb_frames / avg_frame_rate=30/1`
2. **成品抽帧检查**：从 mp4 里 `-ss <t>` 抽 2–3 帧做视觉检查——构图、朝向、有无场外草稿/破损区域
3. **确定性回归**：任选一段短动画，连续渲染 vs 分块+续传渲染，逐字节比对（应 100% 一致）

## 10. 其他小坑

- 动画名做文件名时要清洗 `/:*?"<>|` → `_`；中日文名字在 NTFS / ffmpeg 下没问题
- 某些动画名为空或叫 `animation`（作者没命名），照常处理
- 骨骼 JSON 里动画大多**不带 duration 字段**，时长要由运行时加载后读出（`R.animInfo`），不能用 JSON 直接算
- 骨骼数据版本 4.2.20–4.2.38 混存，用任意 4.2.x 运行时即可全部加载
