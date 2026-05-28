# 技术方案：五期 — 规则引擎 + DeepSeek 复核

## 概述

一期清洗的规则引擎在语义歧义场景下存在误判，在 `clean_process()` 末尾追加 DeepSeek 复核步骤。规则引擎照跑不变，只对标记为"完全重复""抄码名重复""异名同物"的行按组号分批送 DeepSeek 做最终判定。

## 架构

```
clean_process()
  ├─ 规则引擎 (rules.py) → 标记异常分类 + 分组
  └─ DeepSeek 复核 (新增)
       ├─ judge.review_group() — 每组 1 次 API 调用
       └─ 判定结果写回 task_state['clean_results']
```

## 改动范围

| 文件 | 操作 | 内容 |
|------|------|------|
| `web/app.py` | 修改 | clean_process 末尾追加复核逻辑 |
| `scripts/judge.py` | 新增函数 | 新增 review_group() 函数 |

其它文件不动。

## 模块列表

- [DeepSeek 复核模块](./deepseek-review.md) — 分组 → API 调用 → 结果写回

## 数据流

```
规则引擎跑完 → task_state['clean_results'] 已填充
         ↓
筛选 anomaly_class ∈ {"完全重复", "抄码名重复", "异名同物"}
         ↓
按 group_id 分组 → {组号: [items...]}
         ↓
逐组调用 judge.review_group(items)
         ├─ True  → 保持原标记
         ├─ False → 整组改回正常，清空组号
         └─ None  → 整组标"待确认"，保留 detail
         ↓
更新 task_state['clean_results']
         ↓
前端读取 /api/clean-results → 含复核后的结果
```

## 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 复核时机 | 规则引擎之后，同步串行 | 避免并发限流，逐组可控 |
| 判断粒度 | 按组整批判断 | 每组 1 次 API，约 300 次调用 |
| 异常处理 | 标"待确认"不中断 | 单组失败不影响整体流程 |
| 修改原子性 | 整组全改或全不改 | 避免组内结果不一致 |
| sent 名称 | 去老编码后缀再送 | 避免 `-EE152717` 等干扰 DeepSeek |

## 约束

- 依赖 DeepSeek API（复用三期配置：api_key / api_url / model）
- 串行调用，约 300 次 × 2s = 10 分钟
- 不修改前端 UI
- 不修改 rules.py
- 不修改模块B

---
*基于 PRD_五期.md 生成，日期：2026-05-27*
