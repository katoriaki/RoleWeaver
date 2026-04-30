# Live2D 桌宠与 VTube Studio 接入

当前桌宠方案采用 VTube Studio 渲染 Live2D，RoleWeaver 前端只负责连接、授权、读取 Shiro 情绪状态并触发表情。

## 模型位置

默认模型目录：

```text
C:\Users\kator\Desktop\RoleWeaver\shiro\Shiro\March 7th
```

模型元数据：

```text
C:\Users\kator\Desktop\RoleWeaver\shiro\Shiro\March 7th\march 7th.model3.json
```

已经修正过表情引用路径：`exp/1.exp3.json` 到 `exp/8.exp3.json`。

## 使用流程

1. 打开 VTube Studio。
2. 在 VTube Studio 的设置里启用 API。
3. 把 `March 7th` 这个模型目录导入 VTube Studio。
4. 打开 RoleWeaver 前端，进入“桌宠”页面。
5. 点击“连接 VTube Studio”。
6. 第一次使用时点击“请求授权”，然后在 VTube Studio 弹窗里允许 RoleWeaver。
7. 点击“同步白的情绪”，前端会读取 Shiro 当前 `emotion.primary` 并触发对应表情。

## 情绪到表情的当前映射

| Shiro emotion | VTS expression |
| --- | --- |
| `warm` | `exp/4.exp3.json` |
| `playful` | `exp/8.exp3.json` |
| `focused` | `exp/7.exp3.json` |
| `curious` | `exp/8.exp3.json` |
| `guarded` | `exp/5.exp3.json` |
| `hurt` | `exp/6.exp3.json` |
| `tired` | `exp/1.exp3.json` |
| `neutral` | 关闭表情 |

这个映射只是第一版。等正式的白模型和 Live2D 表情命名确定后，可以在前端替换成更精确的表情 adapter。

## API

RoleWeaver 新增：

```http
GET /pet/model
```

返回模型路径、VTube Studio WebSocket 地址、表情列表和 motions 列表。前端不直接加载 `.moc3`，避免浏览器 Live2D SDK 依赖；实际渲染由 VTube Studio 完成。

## 为什么先用 VTube Studio

- VTube Studio 已经处理 Live2D Cubism 运行时、透明窗口、物理、捕捉和渲染；
- RoleWeaver 不需要在网页里引入 Live2D SDK 和 Cubism Core；
- 对单卡常驻环境更稳，前端只是控制台，不抢推理显存；
- 之后如果要做网页内嵌 Live2D，可以把同一套 `emotion/live2d` 信号接给 WebGL renderer。
