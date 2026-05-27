# 技术方案：四期 — 完整 Web 工具

## 1. 概述

一期规则引擎（清洗去重）+ 二期+三期引擎（新品查重）整合为一个 Flask Web 应用。用户打开浏览器即可使用，两个模块并列。

## 2. 架构

```
浏览器 (HTML+JS, 单页双标签)
    ↕ HTTP POST/GET
Flask (web/app.py)
    ├─ 模块A: POST /api/clean → from scripts.rules import RuleEngine → run_all()
    ├─ 模块B: POST /api/build-index → build_index逻辑 → 内存dict
    │         POST /api/start → from scripts.matcher import check_one → 内存index
    │         check_one内部: 规则找候选 → judge() → DeepSeek API
    ├─ 共享: POST /api/settings → 更新 judge.API_KEY (热生效)
    └─ 共享: 后台线程 + 轮询进度模式
```

## 3. 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| 后端 | Python Flask | 三期已有，二期 scripts/ 直接 import |
| 模块A引擎 | 一期 rules.py (RuleEngine) | N×N 规则匹配，不调DeepSeek |
| 模块B候选 | 二期 matcher.py (check_one) | 规则找候选 |
| 模块B判断 | judge.py → DeepSeek API | 语义理解 |
| 前端 | HTML + 内嵌 JS | 三期已有，打包友好 |
| 打包 | PyInstaller | 三期已验证 |

## 4. 模块列表

- [module-a](./module-a.md) — 清洗去重：/api/clean 路由 + rules.py 集成 + 进度轮询
- [module-b](./module-b.md) — 新品查重：/api/build-index 路由 + 内存索引 + 查重流程
- [frontend](./frontend.md) — 前端：双标签布局 + 状态机 + 日志面板

## 5. 数据流

```
模块A:
  POST /api/clean (FormData: 商品库.xlsx)
    → openpyxl 逐行读 → translator.translate → ProductRow列表
    → RuleEngine(rows).run_all()
    → 返回 {total, dupes, normal, results: [{spuid, name, ...}]}
    → 前端渲染统计卡片 + 结果表格

模块B:
  Step1: POST /api/build-index (FormData: 商品库.xlsx)
    → 逐行 translate + resolve_spec → IndexedRow列表
    → 按 core 建 dict: task_state['index'] = {core: [IndexedRow,...]}
    → 返回 {total, categories}

  Step2: POST /api/start (复用三期，但传入内存 index)
    → 逐行: check_one(translator, name, brand, spec, unit, cat, remark, task_state['index'])
      → 规则找候选 → 候选≥1: judge() → DeepSeek → 复用/新增/待确认
      → 候选=0: 直接"需新增"
    → Web 逐条返回结果
```

## 6. 改动范围

| 文件 | 操作 | 内容 |
|------|------|------|
| `web/app.py` | 重写 | 新增 /api/clean、/api/build-index、/api/build-progress、/api/clean-progress。task_state 加 index、clean_results 字段 |
| `web/templates/index.html` | 重写 | 双标签页 + 设置弹窗 + 日志面板，替换三期单页面 |
| `scripts/rules.py` | 不动 | — |
| `scripts/matcher.py` | 不动 | — |
| `scripts/judge.py` | 不动 | — |

## 7. 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 模块A引擎 | 规则引擎不改 | N×N 比对不可用 DeepSeek（1.5亿次调用） |
| 模块B索引 | 内存 dict，不写文件 | 每次上传现场建，关闭释放 |
| 模块A/B 并存 | 同一 Flask 进程，不同路由 | 共享 translator 实例，隔离各自 task_state |
| 前端架构 | 单页双标签，状态隔离 | 切换不丢失状态，各自重置 |

## 8. 约束

- 单用户，本地运行（127.0.0.1）
- 模块A ~30秒/12440条
- 模块B ~2秒/条（DeepSeek延迟）
- 不持久化（重启/关闭 = 状态全清）

---
*基于 PRD_四期.md，日期：2026-05-27*
