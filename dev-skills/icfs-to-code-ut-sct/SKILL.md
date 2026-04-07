---
name: icfs-to-code-ut-sct
description: 根据 ICFS 生成实现代码草稿、单元测试（UT）与系统/场景测试（SCT）要点；遵守项目约定与可测试性。
inputs:
  - name: icfs_attachment
    type: file
    label: ICFS 文档（可选）
    accept: .md,.txt,.pdf,.doc,.docx,.xml,.json
  - name: language_stack
    type: text
    label: 语言/框架（可选）
    placeholder: 例如 Python 3.11 / C++17 / Java 17
---

# ICFS → Code / UT / SCT

## 目标

在 ICFS 与用户需求基础上，分别给出：

1. **实现代码** 草稿（可拆分多文件说明）。
2. **UT**：用例表（Given/When/Then 或等价）、关键断言、mock/stub 边界。
3. **SCT**：端到端或系统级场景、前置数据、期望观测点（日志/指标/外部系统行为）。

## 规则

- 代码需与 ICFS 接口一致；缺失细节处用 `TODO` 注释并说明依赖。
- UT 应覆盖：正常路径、主要错误路径、边界值；避免不可测的模糊断言。
- SCT 应可追溯到 ICFS 条目或需求 ID（若用户提供了编号）。
- 不假设未给出的内部类名、路径或构建系统；必要时询问或给出占位包名。

## 输出格式

分四段 Markdown：**代码说明与片段**、**UT 设计**、**SCT 设计**、**假设与风险**。
