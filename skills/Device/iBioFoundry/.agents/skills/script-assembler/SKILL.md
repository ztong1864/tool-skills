---
name: script-assembler
description: Momentum DSL 完整脚本组装规范，将 process 部分与 runtime/devices/pools/variables 组合成完整脚本，并校验 Acquire、set 和设备动作顺序。
---

# 脚本组装规范

## 📐 完整脚本结构

```javascript
profile [My System]
{
    runtime (...)  ;          // 来自 instructions/runtime.md
    devices { ... }           // 来自 instructions/devices.md
    pools { ... }             // 来自 instructions/pools.md
    variables { ... }         // 来自 instructions/variables.md
    process [Name] { ... }    // 自己编写的部分
}
```

---

## 🔧 组装步骤

### 步骤 1：准备固定部分

从本技能自己的 `instructions/` 目录复制以下内容：

| 部分 | 来源文件 | 说明 |
|------|----------|------|
| `runtime` | `instructions/runtime.md` | 运行时配置（固定） |
| `devices` | `instructions/devices.md` | 设备定义（固定） |
| `pools` | `instructions/pools.md` | 耗材池定义（固定） |
| `variables` | `instructions/variables.md` | 变量定义（固定） |

### 步骤 2：编写 process 部分

根据实验需求编写 `process [Name] { ... }` 部分。

命名要求：

- 输出脚本文件名必须使用 `foundry_<standard_name>_<YYYYMMDD_HHMMSS>.txt`。
- `foundry_` 为固定前缀。
- `<standard_name>` 使用标准实验名，并规范为 ASCII 兼容的小写下划线格式，避免空格、中文和特殊字符。
- `<YYYYMMDD_HHMMSS>` 使用生成脚本时的本地日期时间，精确到秒，用于保证导入时不重名。
- `process[...]` 中的名称必须等于输出脚本文件名去掉 `.txt` 后缀。

示例：

```javascript
// 文件名：foundry_cell_seeding_384well_20260508_153012.txt
process [foundry_cell_seeding_384well_20260508_153012]
{
    // ...
}
```

### 步骤 3：组装完整脚本

按以下顺序组合：

```javascript
profile [My System]
{
    // === 固定部分（直接复制）===
    runtime (
        IterationMode = 'Single',
        MaxIterations = '1',
        // ... 从 instructions/runtime.md 复制
    );
    
    devices
    {
        // ... 从 instructions/devices.md 复制
    }
    
    pools
    {
        // ... 从 instructions/pools.md 复制
    }
    
    variables
    {
        // ... 从 instructions/variables.md 复制
    }
    
    // === 自己编写的部分 ===
    process [foundry_standard_experiment_name_YYYYMMDD_HHMMSS]
    {
        // ... 自己编写的 process 内容
    }
}
```

---

## ⚠️ 核心原则

### 1. 固定部分一字不改
- `runtime`、`devices`、`pools`、`variables` 必须完全复制
- 不允许修改、删除、添加任何内容
- 不允许从 example 中复制这些部分

### 2. 只编写 process
- 唯一需要编写的是 `process` 部分
- process 顶层顺序必须为 `Acquire → set ... Status → 设备动作`
- process 中的设备动作从 reference 复制
- 只修改 reference 标注"可修改"的参数

### 3. 一次性输出
- 整理完整后再一次性写入文件
- 不要分步写入

---

## 📋 组装检查清单

- [ ] profile [My System] 开头格式正确
- [ ] runtime 部分完全复制自 instructions/runtime.md
- [ ] devices 部分完全复制自 instructions/devices.md
- [ ] pools 部分完全复制自 instructions/pools.md
- [ ] variables 部分完全复制自 instructions/variables.md
- [ ] 文件名符合 `foundry_<standard_name>_<YYYYMMDD_HHMMSS>.txt`
- [ ] process 名称等于文件名去掉 `.txt`
- [ ] process 中 `set ... Status` 紧接 `Acquire`，所有设备动作位于其后
- [ ] process 部分设备动作来自 reference
- [ ] 没有使用 reference 外的设备/动作/容器
- [ ] 没有修改禁止修改的参数
- [ ] 脚本一次性完整输出

---

## 🚫 禁止事项

- ❌ 不要自行设计 runtime/devices/pools/variables
- ❌ 不要从 example 中复制固定部分
- ❌ 不要分步写入文件
- ❌ 不要修改固定部分的内容

---
