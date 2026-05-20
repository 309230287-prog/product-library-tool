# 实施计划：二期新品增量查重

## 概述

新品入库时自动比对12440条基准库，四维匹配判断能否复用已有编码。产出建议复用/需新增/待确认。

**成功标准：** 10条验收案例全部通过，输出Excel行数=输入行数。

## 架构参考

参见 [specs/README.md](./specs/README.md)，核心模块：
- translator.py（改造）→ matcher.py（新建）→ build_index.py（新建）→ check_new.py（新建）

## 任务清单

### 阶段 1：翻译器改造

- [ ] **T001：NameMeaning 加 name_spec 字段** `[已完成]`
  - 范围：在 NameMeaning dataclass 加 `name_spec: Optional[str] = None`
  - 依赖：无
  - 产出：NameMeaning 有新字段
  - 验收：`hasattr(NameMeaning, 'name_spec')` 为 True

- [ ] **T002：translate_name 加规格提取** `[已完成]`
  - 范围：在品牌提取前扫描名称，提取规格模式（复杂规格→数量单位→重量容量），标准化后剥离
  - 依赖：T001
  - 产出：名称中的规格被正确提取
  - 验收：`translate_name("乌江榨菜1*100*70g").name_spec == "100*70g"`

- [ ] **T003：加 has_processing_intent 函数** `[已完成]`
  - 范围：在 translator.py 加 PROC_PREFIXES 和 has_processing_intent(remark)→bool
  - 依赖：无
  - 产出：加工意图检测函数
  - 验收：`has_processing_intent("切丝") == True`, `has_processing_intent("送二楼") == False`

- [ ] **T004：加 resolve_spec 函数** `[已完成]`
  - 范围：新增 SpecResult dataclass 和 resolve_spec(name_meaning, desc_meaning, has_processing)→SpecResult
  - 依赖：T002
  - 产出：三源规格汇总函数
  - 验收：name_spec="500g", desc_spec="500g" → spec_core="500g", conflict=False

- [ ] **T005：加 TranslatedItem 容器类型** `[已完成]`
  - 范围：新增 TranslatedItem dataclass（core, brand, has_status, unit, category）
  - 依赖：无
  - 产出：新品翻译结果的统一容器
  - 验收：dataclass 可正确实例化

### 阶段 2：基准库索引

- [ ] **T006：build_index.py 主逻辑** `[已完成]`
  - 范围：读取结果表→用新翻译器翻译12440条→resolve_spec→构建core索引→写index.json
  - 依赖：T004, T005
  - 产出：index.json（约10MB）
  - 验收：12440条全量翻译无报错，JSON可正常解析

- [ ] **T007：验证 index.json 覆盖率** `[已完成]`
  - 范围：检查索引的core数量、每个core下的条目数
  - 依赖：T006
  - 产出：验证报告
  - 验收：索引包含所有12440条记录，core去重后数量合理

### 阶段 3：四维匹配引擎

- [ ] **T008：matcher.py 数据结构** `[已完成]`
  - 范围：定义 IndexedRow, CandidateMatch, MatchResult dataclass
  - 依赖：无
  - 产出：matcher.py 骨架 + 数据结构
  - 验收：类型导入无报错

- [ ] **T009：check_spec 规格比对** `[已完成]`
  - 范围：实现 check_spec(new_spec, candidate)→(bool, str)，含5种情况分支
  - 依赖：T008
  - 产出：规格维度比对函数
  - 验收：双方无规格→True，规格不同→False，单方有→spec_mismatch_unilateral

- [ ] **T010：check_dimensions 四维比对** `[已完成]`
  - 范围：实现四维比对（品名含exact/synonym/substring/status/paren，品牌，规格，单位）
  - 依赖：T008, T009
  - 产出：四维比对函数
  - 验收：四维全过返回dim全部True，维度失败正确标记

- [ ] **T011：classify 结果分类** `[已完成]`
  - 范围：实现结果分类逻辑（建议复用/需新增/待确认）
  - 依赖：T010
  - 产出：结果分类函数
  - 验收：四维全过→建议复用，子串→待确认，未匹配→需新增

- [ ] **T012：check_one 主匹配流程** `[已完成]`
  - 范围：翻译→索引查找→异名查找→子串过滤→四维比对→分类
  - 依赖：T011
  - 产出：完整匹配函数
  - 验收：输入新品数据返回 MatchResult

### 阶段 4：主入口 + 验收

- [ ] **T013：check_new.py 主入口** `[已完成]`
  - 范围：读`新品新增接龙表.xlsx`→筛选无编码行(当前62条)→逐行调check_one→反写系统名称(col10)+系统编码(col11)
  - 输入列：*品牌(col2), *名称(col3), *规格(col4), *类别(col5), *单位(col6)
  - 依赖：T012, T006
  - 产出：可独立运行的新品查重脚本
  - 验收：62条待匹配行正确处理，已有编码的598行不变

- [ ] **T014：10条验收案例测试** `[已完成]`
  - 范围：创建测试模板包含10条验收案例，运行check_new.py，逐条验证结果
  - 依赖：T013
  - 产出：验收报告
  - 验收：10条全部通过

## 依赖关系

```
阶段1: T001→T002→T004 ↘
         T003 ─────────→ T004 → T005 → T006 → T007
阶段2:                                        ↘
阶段3: T008→T009→T010→T011→T012 ───────────────→ T013 → T014
```

## 待确认

- 新品待查模板.xlsx 是否已有现成文件？
- 10条验收案例的具体数据（SPUID、名称等）需确认
- index.json 是否需要做压缩（10MB对单次加载可接受）

---
*基于 PRD.md + specs/ 生成，日期：2026-05-20*
