---
name: efs-to-pfs
description: 根据 EFS（特性说明）文档编写或更新 PFS（产品功能说明）；保持术语一致并标明假设与待确认项。
inputs:
  - name: efs_attachment
    type: file
    label: EFS 文档（可选）
    accept: .md,.txt,.pdf,.doc,.docx,.xml,.json
  - name: product_area
    type: text
    label: 产品/模块范围（可选）
    placeholder: 例如 5G L2 / 某网元
---

# EFS → PFS

## 目标

基于用户提供的 EFS 内容与上下文，输出结构化的 **PFS** 草稿，便于评审与迭代。

## 规则

- 明确区分：需求事实（来自 EFS）、设计推断（需标注「推断」）、待产品/架构确认项（单独列表）。
- PFS 建议包含：范围与目标、功能列表、接口/交互概要、非功能约束（性能/可靠性/安全若 EFS 有涉及）、验收要点。
- 若输入不完整，列出 **最小补充信息清单**，仍可先给可评审的 PFS 骨架。
- 使用与用户一致的术语；勿编造 EFS 未支持的具体参数值或外部系统行为。

## 输出格式

使用 Markdown，层级清晰，便于粘贴到文档系统。
