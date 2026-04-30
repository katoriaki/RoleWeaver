# Shiro VRM 接入说明

当前模型文件：

```text
C:\Users\kator\Desktop\RoleWeaver\shiro\shiro.vrm
```

已复制到 Unity 工程：

```text
C:\Users\kator\Desktop\RoleWeaver\shiro\unity\ShirosWorld\Assets\RoleWeaver\Models\shiro.vrm
```

## 为什么还需要 UniVRM

`.vrm` 是基于 glTF 的虚拟人格式，Unity 原生不能完整导入表情、humanoid rig、spring bone、材质和 VRM 元数据。需要安装 UniVRM。

官方文档：

- UniVRM 安装说明：https://vrm.dev/en/univrm/
- UniVRM GitHub Releases：https://github.com/vrm-c/UniVRM/releases

当前 Unity 工程已改用 UniVRM `v0.128.3` 的 UPM 路径：

```json
"com.vrmc.gltf": "https://github.com/vrm-c/UniVRM.git?path=/Assets/UniGLTF#v0.128.3",
"com.vrmc.vrm": "https://github.com/vrm-c/UniVRM.git?path=/Assets/VRM10#v0.128.3"
```

原因：`v0.131.0` 开始源码迁移到 `Packages` 目录，但在当前 Unity 6.3 + URP 项目里导入 `shiro.vrm` 时出现过 `ArgumentNullException: Shader`。这是 UniVRM 导入 MToon10 材质时找不到 shader 的问题，不是 `shiro.vrm` 本体损坏。

如果手动安装，建议优先使用 UnityPackage 方式，因为它最直观：

1. 打开 `ShirosWorld` Unity 项目。
2. 从 UniVRM Releases 下载 `UniVRM-*.unitypackage`。
3. 在 Unity 中选择 `Assets -> Import Package -> Custom Package`。
4. 导入 UniVRM 包。
5. 等 Unity 编译完成后，将 `Assets/RoleWeaver/Models/shiro.vrm` 拖入 Project 面板或等待自动导入。
6. UniVRM 成功后应生成 Shiro 的 prefab。
7. 把 prefab 拖到场景中，挂到 `ShiroAvatarDriver.avatarRoot`。

## 如果出现 Shader 为空

错误形态：

```text
ArgumentNullException: Value cannot be null.
Parameter name: Shader
UniGLTF.MaterialFactory.LoadAsync
```

处理顺序：

1. 关闭 Unity。
2. 确认 `Packages/manifest.json` 使用 `v0.128.3`，不是 `v0.131.0`。
3. 如果 Unity 仍显示旧 hash 堆栈，例如 `com.vrmc.gltf@39e860...`，说明当前 Editor 进程还在用旧包；关闭并重新打开 Unity。
4. 当前工程已把 MToon10 shader 镜像到：

   ```text
   Assets/RoleWeaver/Vendor/MToon10/Shaders
   ```

   先让 Unity 导入这个目录，确认 Console 没有 shader 编译错误。
5. 删除失败导入留下的 `Assets/RoleWeaver/Models/shiro.vrm.meta`。
6. 右键 `Assets/RoleWeaver/Models/shiro.vrm`，选择 `Reimport`。

`shiro.vrm` 已确认是 VRM 1.0 / MToon10，因此不需要安装 VRM 0.x 的 `com.vrmc.univrm`，除非后续还要导入旧版 VRM0 模型。

## 当前 M2.1 代码做了什么

新增 `ShiroAvatarDriver`，不依赖 UniVRM 编译符号，因此即使没装 UniVRM 也不会让工程报错。它会读取 `ShiroStateController` 输出的：

- emotion
- expression
- motion
- intensity
- pose

并映射到 Unity avatar：

- 朝向摄像机；
- 根据情绪强度做轻微呼吸/浮动；
- 给 Animator 写入参数；
- 根据 guarded/tired/focused/thinking 等状态改变姿态倾向。

之后安装 UniVRM 后，M2.2 再把这些状态精确接到：

- VRM BlendShape / Expression；
- humanoid Animator；
- spring bone；
- look-at；
- lip sync。

## M2 后续任务

1. 安装 UniVRM。
2. 导入 `shiro.vrm` 生成 prefab。
3. 创建 `ShiroWorld.unity` 主场景。
4. 把 prefab 挂到 `ShiroAvatarDriver`。
5. 建立 expression/motion 映射表。
6. 接入摄像机、桌宠视角和 3D 房间。
