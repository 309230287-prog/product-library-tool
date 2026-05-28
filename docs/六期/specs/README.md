# 技术方案：六期 — 销售订单匹配

## 概述

模块A 清洗完成后，可选上传销售订单 Excel，自动识别 SPUID+客户列，按命中次数判定重复组内保留/下架，结果 13 列，导出 3 Sheet。

## 架构

```
模块A 现有流程（不变）:
  POST /api/clean → clean_process → RuleEngine → DeepSeek 复核
                                      ↓
                              结果写入 clean_results

新增:
  POST /api/upload-orders → 识别列 → 统计 → 判定保留/下架
                                      ↓
                              order_data 写入 task_state
                                      ↓
  GET /api/clean-results → 返回含 order_count/keep_or_remove 等字段
                                      ↓
  GET /api/clean-export → 13 列 × 3 Sheet Excel
```

## 改动范围

| 文件 | 操作 | 内容 |
|------|------|------|
| `web/app.py` | 修改 + 新增 | 新增 upload-orders 路由 + 修改 clean-results/clean-export |
| `web/templates/index.html` | 修改 | 新增上传区 + 表格加 4 列 |

其它文件不动。

## 模块列表

- [订单匹配模块](./order-matching.md) — 列识别 → 统计 → 保留/下架 → 导出

## 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 客户列也自动识别 | 是 | 参考文件有客户名列，后续可能列名变化 |
| 判定逻辑在后端 | 是 | 导出 Excel 需要后端生成，前端只负责渲染 |
| Sheet 分离 | 按异常分类分 3 Sheet | 对标参考文件格式 |
| 不上传不影响 | 后 4 列为空 | 选填功能 |

## 约束

- 只操作 `task_state['clean_results']` 的 dict，不增删行
- 订单数据 `order_data` 覆盖式更新
- 不修改现有路由的返回值结构（只新增字段）

---
*基于 PRD_六期.md 生成，日期：2026-05-28*
