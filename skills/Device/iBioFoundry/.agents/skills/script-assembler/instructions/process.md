# Process 编写规范

## 📖 概述

`process` 块定义实验自动化流程的具体执行步骤，是 Momentum DSL 脚本的**核心部分**。

**本 Skill（IB-machine-operation）的核心功能：** 根据用户输入的指令，编写 process 部分的内容。

---

## ⚠️ 重要说明

**本 Skill 只负责编写 process 部分！**

其他部分（runtime, devices, pools, variables）：
- ❌ **不要修改** — 仅复制固定模板，不要自行改写
- ✅ **只关注** process 块的编写

---

## 📝 语法结构

### 基本结构

```javascript
process [ProcessName]
{
    // 流程步骤
    DeviceName [ActionName]
        (参数列表)
        Container 规格 in '设备位置' 容器获取方式;
}
```

其中
process `DeviceName [ActionName]
        (参数列表)
        Container 规格 in '设备位置' 容器获取方式;` 中的动作只能从 `$device-operation-library` 的设备模板和 workflow rule 中选择，容器命名与 `Acquire` / `Status` 写法则遵循 `$container-and-status-rules`。

`process` 中的顶层顺序固定为：先写完整 `Acquire`，紧接着写 `set ... Status`，然后才写任何设备动作。
