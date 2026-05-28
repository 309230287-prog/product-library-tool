# 技术方案：三期 — 工具封装与交付

## 概述

Flask + HTML/JS + PyInstaller。复用二期引擎，不做逻辑改动。

## 架构

两步流程：
1. **规则引擎找候选** — translator 翻译 → 查 index.json → 异名表 → 子串匹配 → 候选列表
2. **DeepSeek 做判断** — 新品画像 + 候选列表 → judge() → 复用/新增/待确认

```
浏览器 ↔ Flask ↔ 二期引擎(scripts/)
                    ├── 第一步: translator + index.json → 候选
                    └── 第二步: judge() → DeepSeek API
```

## 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| 后端 | Python Flask | 与二期同语言，直接 import |
| 前端 | HTML + 内嵌 JS | 无构建工具，打包友好 |
| 打包 | PyInstaller | Python → 单文件 exe |

## 模块列表

- [web-backend](./web-backend.md) — Flask API 设计
- [web-frontend](./web-frontend.md) — HTML 前端设计
- [config](./config.md) — 配置 Excel 设计
- [packaging](./packaging.md) — PyInstaller 打包

## 数据流

```
接龙表.xlsx → POST /api/upload → 预览
             → POST /api/start  → 后台逐行: check_one() → judge() → DeepSeek
             → GET /api/progress (轮询0.5s) → 实时进度+结果
             → GET /api/export → 下载结果 Excel
```

## 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 前后端通信 | 轮询 | 简单可靠，2秒延迟不敏感 |
| 后台处理 | threading | 单用户，无需队列 |
| 文件上传 | 内存处理 | 不落盘 |

## 约束

- 单用户，本地运行
- 端口可配置，默认5000
- 不持久化状态

---
*基于 PRD_三期.md，日期：2026-05-26*
