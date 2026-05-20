# 技术方案：二期新品增量查重

## 概述

新品入库时，通过语义翻译 + 四维匹配引擎，自动判断能否复用基准库已有编码。

核心思路：**不是字符串匹配，是翻译后四维比对**。

## 架构

```
新品输入(*品牌/*名称/*规格/*类别/*单位/备注)
    ↓ translator.py（语义翻译） 注:品牌取自*品牌列,不从名称提取
TranslatedItem(core, brand, spec, unit, has_processing)
    ↓ matcher.py（四维匹配引擎）
    ├── 查 index.json（base库12440条）
    ├── 四维比对（品名×品牌×规格×单位）
    └── 结果分类（建议复用/需新增/待确认）
    ↓
输出Excel（追加3列）
```

## 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| 语言 | Python 3 | 一期延续 |
| Excel读写 | openpyxl | 一期延续 |
| 索引格式 | JSON | 可读可调试，12440条约10MB |
| 测试 | pytest | Python标准 |

## 模块列表

- [translator-upgrade](./translator-upgrade.md) — 翻译器改造（名称规格提取+加工检测）
- [matcher](./matcher.md) — 四维匹配引擎（核心新增）
- [build-index](./build-index.md) — 基准库索引构建
- [check-flow](./check-flow.md) — 主流程（读模板→匹配→写结果）

## 数据流

```
[商品库整理_结果.xlsx]  (列1-5翻译, 列11命中次数)
    ↓ build_index.py
[index.json]  {core_name: [IndexedRow, ...]}
    ↓
[新品待查模板.xlsx] → check_new.py → [新品待查模板.xlsx + 结果]
                        ↑              ↑
                  translator.py    matcher.py
```

## 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 索引格式 | JSON单文件 | 可读可调试，无序列化兼容问题 |
| 加工检测 | 动作前缀检测 | 不硬编码结果词（切丝/块/丁写不完） |
| 规格提取 | 名称全扫描 | 不预设规格位置（可能在品牌前后） |
| 子串匹配 | 始终执行 | 确保"土豆"也能发现"土豆丝" |
| 异名查找 | 始终同时查 | 确保"苦瓜"也能发现"凉瓜" |

## 约束

- Python 3，openpyxl，无外部API
- 12440条基准库全量翻译不报错
- 输出行数 = 输入行数
- 复用一期 translator.py 基础，不动 rules.py

---
*基于 PRD.md 生成，日期：2026-05-20*
