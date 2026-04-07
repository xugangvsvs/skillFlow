---
name: analyze-pronto
description: 分析 Pronto 缺陷单：上下文归纳、可能根因、验证步骤与需要澄清的信息。
inputs:
  - name: pronto_id
    type: text
    label: Pronto ID
    placeholder: 例如 PR12345678
  - name: pronto_attachment
    type: file
    label: 导出/截图（可选）
    accept: .md,.txt,.pdf,.log,.zip,.png,.jpg,.jpeg
---

# 分析 Pronto

## 目标

基于用户粘贴的 Pronto 描述、日志片段或附件说明，输出可执行的 **分析结论与下一步**。

## 规则

- 先归纳：现象、影响范围、环境/版本、已尝试操作（若文本中有）。
- 区分：事实 vs 推测；推测需写「待验证」及建议验证方法。
- 给出 **排查顺序**（从低成本到高成本）：检查项、命令或界面路径、期望结果。
- 若信息不足，列出 **最少追问清单**（每条对应可 unblock 的分析）。
- 不捏造未在输入中出现的版本号、堆栈或内部工单链接。

## 输出格式

Markdown：**摘要**、**时间线与事实**、**可能根因（分级）**、**建议验证步骤**、**需补充信息**。
