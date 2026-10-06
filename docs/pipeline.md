# 技术说明

本文说明 spine-cg-render 的实现原理、关键细节与注意事项，供使用与二次开发参考。

---

## 1. 资产形态：Spine 资产在 Unity 中的打包结构

Unity + spine-unity 项目将 Spine 资产以下列形式打包进 bundle：

| 部件 | Unity 类型 | 说明 |
|------|-----------|------|
| 骨骼数据 | `TextAsset`（名为骨架名，内容为 JSON） | 骨骼、皮肤、槽位与全部动画时间轴 |
| 图集描述 | `TextAsset`（名为 `<骨架>.atlas`） | 各贴图页文件名与部件的矩形坐标 |
| 图集贴图 | `Texture2D`（每页一张） | 按页名与 atlas 一一对应 |

**配对校验方法**：读取 `<骨架>_Atlas` 这一 MonoBehaviour（`read_typetree()`）中的 `atlasFile`（指向 atlas TextAsset）与 `materials`（各材质的 `_MainTex` 指向对应页的 Texture2D），即可准确确认"页 ↔ 贴图"的映射关系。

判断 bundle 是否包含 Spine 资产：检查 TextAsset 内容是否以 `{"skeleton":{"spine":"4.2.x"...` 开头。

## 2. 采用逐帧渲染的原因

- 资产解包只能得到静态素材，动画数据保存在骨骼时间轴中，无法通过静态导出播放；
- 录屏受窗口分辨率、性能与遮挡影响，存在掉帧与压缩损失，且难以批量执行；
- 逐帧渲染按固定时间步长（1/30 秒）计算姿势并输出帧，结果确定、无损、取景可控，适合无人值守的批量处理。

## 3. 渲染实现（spine-webgl 4.2 官方运行时）

在页面中引入官方 IIFE 构建：

```html
<script src="/web/spine-webgl.js"></script>
<!-- https://cdn.jsdelivr.net/npm/@esotericsoftware/spine-webgl@4.2.120/dist/iife/spine-webgl.js -->
```

四个关键实现点（均经实际验证）：

1. **TextureAtlas 构造函数仅接受文本**：`new spine.TextureAtlas(atlasText)`（4.2 版本没有 textureLoader 参数）。贴图需手动逐页挂载：
   ```js
   const atlas = new spine.TextureAtlas(atlasText);
   for (const page of atlas.pages) {
     page.setTexture(new spine.GLTexture(gl, img));   // img 需预先加载完成
   }
   ```
   未调用 `setTexture` 时页面不会报错，但渲染结果为全黑。
2. **`updateWorldTransform(spine.Physics.update)`**：4.2 起物理参数为必传项，遗漏会抛出 `physics is undefined`。
3. **相机方向保持默认**：默认 `camera.up = (0,1,0)` 即为正确方向（渲染 spine 数据直立）；将 `up.y` 设为 `-1` 会导致画面上下镜像。建议在批量渲染前先用一个站立角色进行方向校验。
4. **PMA 纹理**：atlas 标注 `pma:true` 时，绘制应使用 `drawSkeleton(skeleton, true)`（预乘 alpha 混合）。

**确定性步进**（每帧）：

```js
state.update(1/fps);            // 推进虚拟时钟
state.apply(skeleton);          // 应用姿势
skeleton.updateWorldTransform(spine.Physics.update);
draw();                         // 绘制
// 抓帧：canvas.toBlob('image/png') → POST 到本地服务落盘
```

同一动画"连续渲染"与"分块渲染后拼接"的输出逐字节一致（已用 180 帧样本做过回归验证），因此断点续传是安全的。

## 4. 纹理尺寸差异（atlas 页尺寸 ≠ 贴图实际尺寸）

常见现象：atlas 标注的页尺寸与 bundle 内贴图的实际分辨率不一致（例如标注 `size:2735,866`，实际为 2048×512），原因是 Unity 导入时进行了缩放与非 2 次幂取整。

**该差异不影响渲染**：spine 运行时按 atlas 标注的页尺寸计算归一化 UV，只要贴图内容为原图的等比缩放，采样位置即为正确。请勿尝试"修正"这一差异（例如重新缩放贴图），否则会破坏采样。

## 5. 工程实现要点

### 5.1 HTTP 服务需启用 keep-alive

渲染过程持续上传帧数据（每秒数帧、每帧约 0.5MB）。若服务器采用 HTTP/1.0 的一连接一请求模式：

- 浏览器侧 `fetch` 会在约 20–25 秒后开始失败（实测约第 36 次上传、21.7 秒时出现）；
- 吞吐率约 0.85 MB/s。

改用 `HTTP/1.1` 并保证每个响应携带 `Content-Length`，配合线程化服务器后，150 × 512KB 上传可在 0.5 秒内完成，零失败：

```python
protocol_version = 'HTTP/1.1'
ThreadingHTTPServer.daemon_threads = True
ThreadingHTTPServer.request_queue_size = 128
```

另配置上传重试（250ms 退避 ×6）作为兜底。

### 5.2 浏览器接口的 5 秒调用上限

驱动层（CDP `Runtime.evaluate`）单次调用需在约 5 秒内返回，因此长任务不能在单次调用中等待完成：

- 页面内以后台任务方式分块渲染，持续更新 `R.__chunk = {running, done, err}`；
- 驱动侧每秒轮询一次进度；
- 默认分块大小为 300 帧（约 20–40 秒/块）。

### 5.3 断点续传以磁盘帧文件为基准

依赖浏览器状态实现精确续跑不可靠，因此以磁盘帧文件为准：

- 帧文件按 `f0000.png`、`f0001.png`、…… 命名落盘；
- 续传时统计现有帧数（`existing`），快进（仅更新状态、不抓帧）至该位置后继续；
- 快进循环每 250 帧让出一次事件循环，避免长时间阻塞页面；
- 单个动画连续 3 次零进度才判定失败并记录。

### 5.4 中断恢复机制

软件 WebGL 持续高负载下，浏览器进程可能周期性退出（实测约每 1–2 分钟一次）。因此整条链路按"中断无损失"的原则设计：

- 帧文件是唯一事实来源；
- 每个骨架渲染前重新加载页面，同时释放渲染内存；
- 自动化侧捕获断连，重启后按文件数续跑；单次中断仅损失数十秒。

### 5.5 自动化工具环境异常时的清理

自动化后台进程可能因残留端口文件（`~/.config/browser-harness/runtime/bu-default.port`）而无法重启（Windows 下报 `PermissionError`）。处理方式：结束命令行中带 harness 标识的 python / chrome 进程（注意不要终止正在使用的浏览器），清空 runtime 目录内容后重试。

## 6. 取景（影响成片效果的关键步骤）

- **自动取景**：对全部动画的多个时间点采样内容包围盒，取并集并外扩 7% 边距。该方式稳健，但会将"场外草稿"纳入画面——部分骨骼中存放着未使用的备用素材（多余的整只角色、散落元件），在游戏画面中位于镜头之外。
- **视口取景**：`JSON.skeleton.{x,y,width,height}` 是作者在 Spine 编辑器中设定的取景窗，使用 `frame:'viewport'` 模式即可裁去场外草稿。
- **判断方法**：先对每个骨架渲染一帧（可叠加红色视口框）并进行视觉检查：
  - 出现"重复的整只角色 / 漂浮元件" → 属于场外草稿，改用视口取景重新渲染；
  - 内容仅为自然溢出视口（如特效超出画面顶部） → 保留自动取景，避免裁掉有效内容。
- 结论：并非所有场景都适合视口取景，建议逐场景抽查确认。

## 7. 动画过滤规则

复用的骨骼中包含大量非 CG 动画，可按命名规则过滤（需要按游戏调整）：

- **跳过前缀**：`Mix/`（运行时混合补帧）、`Attack/`、`Jump/`、`Skill/` 及其武器 / 形态变体
- **跳过名称**：`walk`、`walk2`、`idle`、`mix`、`hurt_*`、`heavily_hurt_*`
- **保留**：编号段（`1`、`2(loop)`）、过渡段（`1-2`）、`start`、`cum`、`end`、`full`（整段连播）、作者命名的预览 / 细节段等

命名规律即游戏内的推进顺序：数字为阶段编号，`X-Y` 为阶段间过渡，`(loop)` 为循环段。

## 8. 性能参考

| 环节 | 数值（软件 WebGL 环境） |
|------|------|
| 单帧渲染 + 抓帧 + 上传 | 约 70–150 ms |
| 15,500 帧纯渲染 | 约 40–60 分钟 |
| 96 段编码（libx264，CRF 18） | 约 4 分钟 |
| 中间帧图片磁盘占用 | 约 4–6 GB（编码后可清理） |

## 9. 验收方法

1. **帧数核对**：帧数 = `round(动画时长 × 30)`；可用 `ffprobe` 抽查 `duration`、`nb_frames`、`avg_frame_rate=30/1`。
2. **成片抽帧检查**：从 mp4 中抽取 2–3 帧进行视觉检查（构图、朝向、有无场外素材或破损区域）。
3. **确定性回归**：任选一段短动画，"连续渲染"与"分块 + 续传渲染"的结果应逐字节一致。

## 10. 其他注意事项

- 动画名转为文件名时需处理 `/:*?"<>|` → `_`；中文 / 日文文件名在 NTFS 与 ffmpeg 下均可正常使用。
- 个别动画可能未命名（为空或名为 `animation`），按正常流程处理即可。
- 骨骼 JSON 中的动画大多不包含时长字段，时长需由运行时加载后读取（`R.animInfo`）。
- 骨骼数据版本可能混存（如 4.2.2x–4.2.3x），任意 4.2.x 运行时均可加载。
