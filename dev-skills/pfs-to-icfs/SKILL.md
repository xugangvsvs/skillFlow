---
name: pfs-to-icfs
description: 根据 PFS（产品功能说明）编写 ICFS（接口控制功能说明），聚焦接口、消息、状态与错误语义。
inputs:
  - name: pfs_attachment
    type: file
    label: PFS 文档（可选）
    accept: .md,.txt,.pdf,.doc,.docx,.xml,.json
  - name: interface_scope
    type: text
    label: 接口范围（可选）
    placeholder: 例如 北向 API / 模块 X 与 Y 之间
---

# PFS → ICFS

## 目标

从 PFS 中抽取与接口相关的功能，输出 **ICFS** 草稿：可指导实现与联调。

## 规则

- ICFS 应覆盖：接口标识、请求/响应或消息结构、字段说明、默认值、可选性、错误码/异常语义、时序或状态机（若适用）。
- 对 PFS 中未展开的部分，用 **TBD** 列出需 PFS/架构补充的问题，不要虚构协议细节。
- 与现有系统命名风格冲突时，在「命名与兼容」小节中说明选项与推荐。

## 输出格式

Markdown，建议分「接口清单」「逐接口说明」「开放问题」三节。
