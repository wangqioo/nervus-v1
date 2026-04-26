---
name: Android 构建默认横屏
description: 构建 Android 应用时默认设置横屏方向
type: feedback
originSessionId: d3212692-32c8-4a75-afbc-84221bed570d
---
构建 Android 应用时，AndroidManifest.xml 中的 Activity 默认使用横屏方向。

**Why:** 用户明确要求所有构建的 Android 应用默认横屏。

**How to apply:** 在 AndroidManifest.xml 的 `<activity>` 标签中设置 `android:screenOrientation="landscape"`，而不是 `portrait`。
