# 代码审查修复计划

> 10个问题，按严重度和依赖分3个阶段。

## 依赖关系

```
阶段1（独立，可并行）:
  F1(保存路径)  F2(candidates取最佳)  F3(replace→startswith/endswith)
  F4(load_index缺省值)   F5(spec_detail拆分)

阶段2（依赖F2）:
  F6(品牌无要求)  F7(待确认/需新增写入Excel)

阶段3（独立低优）:
  F8(子串搜索限流)  F9(规格正则可选)  F10(规格/品牌顺序暂缓)
```

---

## 阶段1：严重问题（5个，解耦独立）

### F1：check_new.py — 不覆盖原文件

- 范围：`check_new.py:58` `wb.save(SRC)` → 另存为 `_查重结果.xlsx`
- 依赖：无
- 验收：原文件不変

### F2：check_new.py — 系统名称取最佳候选

- 范围：`check_new.py:49` 从 candidates 找 spuid=suggested_spuid 的取 raw_name
- 依赖：无
- 验收：编码和名称来自同一个候选

### F3：matcher.py — 子串匹配用 startswith/endswith

- 范围：`matcher.py:84-89` 只取前缀/后缀多出的部分作 diff
- 依赖：无
- 验收："大白白菜" vs "大白菜" → 不进子串匹配

### F4：matcher.py — load_index 容错缺失字段

- 范围：`matcher.py:42` JSON行补默认值
- 依赖：无
- 验收：老版本JSON可加载

### F5：matcher.py — 拆分 spec_detail

- 范围：`matcher.py:70` 加工不一致用独立 detail，classify 对应处理
- 依赖：无
- 验收：加工不一致不归类为"规格信息不对等"

---

## 阶段2：高级问题（2个，依赖F2）

### F6：品牌"无要求"跳过品牌比对

- 范围：check_new 传标记，matcher 跳过品牌比对
- 依赖：F2
- 验收："无要求"时品牌维度始终通过

### F7：待确认/需新增结果写入Excel

- 范围：check_new 把所有结果写进新增列
- 依赖：F2
- 验收：Excel每行都有匹配结果和详情

---

## 阶段3：中等问题（3个）

### F8：子串搜索加最小长度限制

- 范围：shorter < 2 跳过
- 依赖：无

### F9：规格正则尾缀收窄

- 范围：`[^\s]*` → `[\d\w.]*`
- 依赖：无

### F10：规格/品牌提取顺序（暂缓）

- 风险：影响大需重跑全量验证，建议暂缓
