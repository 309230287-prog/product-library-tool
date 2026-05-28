# PRD：六期 — 销售订单匹配

## 问题陈述

清洗去重后重复组的建议只说"保留其一"，没有给出保留/下架的具体决策。一期手动用销售订单数据按 SPUID 匹配，根据订单引用次数决定保留哪个、下架哪个。需要把这个过程自动化到 Web 工具里。

## 目标用户

使用商品库工具 v2.0 进行清洗的用户（内部运营/采购人员）。

## 预期输出格式（对标 `重复编码下架保留清单.xlsx`）

输出 Excel 含 13 列，分 3 个 Sheet：

| Sheet | 内容 | 行数 |
|-------|------|------|
| Sheet1 | 完全重复 + 异名同物 | 按重复组数 |
| Sheet2 | 正常（无异常但有订单数据） | 匹配上的正常行 |
| Sheet3 | 抄码名重复 | 按重复组数 |

13 列：

| # | 列名 | 来源 | 说明 |
|---|------|------|------|
| 1 | SPUID | 商品库 | — |
| 2 | SPU名称（可修改） | 商品库 | — |
| 3 | SPU基本单位 | 商品库 | — |
| 4 | SPU描述（可修改） | 商品库 | — |
| 5 | 一级分类名称 | 商品库 | — |
| 6 | 组号 | 规则引擎 | — |
| 7 | 组说明 | 规则引擎 | — |
| 8 | 建议 | 规则引擎/DeepSeek | — |
| 9 | 异常分类 | 规则引擎/DeepSeek | — |
| 10 | **是否下架/保留** | **新增** | "保留" / "下架" / 空 |
| 11 | **替代编码** | **新增** | 组内对方 SPUID / 空 |
| 12 | **订单命中次数** | **新增** | 数字 / 空 |
| 13 | **订单命中客户** | **新增** | 客户名换行分隔 / 空 |

### "是否下架/保留" 判定规则

```
同组内比较订单命中次数：
  次数多的一方 → "保留"
  次数少的一方 → "下架"
  次数相同 → 都不填（无法区分优先级）
  无订单数据 → 空
```

### "替代编码" 填写规则

```
标记"保留" → 替代编码 = 组内对方的 SPUID
标记"下架" → 替代编码 = 组内对方的 SPUID
标记为空 → 替代编码 = 空
```

### "订单命中客户" 格式

```
去重 + 换行分隔
例：
  单54(光明围台)
  单158（海警21540艇）
  单103(龙岗供销社)
```

## 功能需求

### P0（必须有）

- **FR-601**：模块A 清洗完成后显示选填上传区"上传销售订单（可选）"
- **FR-602**：自动识别订单文件的 SPUID 列（关键词：spuid / spu编码 / 商品编码 / code / 商品代码）+ 客户列（关键词：客户 / 商户名 / 食堂名称 / 客户名称 / customer / 购货单位）。假设第一行为表头行。
- **FR-603**：按 SPUID 统计每条编码的订单命中次数
- **FR-604**：按 SPUID 收集关联的客户名称（去重）
- **FR-605**：结果表格多 4 列——是否下架/保留、替代编码、订单命中次数、订单命中客户
- **FR-606**：重复组内按订单命中次数自动判定保留/下架、填写替代编码
- **FR-607**：导出 Excel 分 3 个 Sheet（完全重复+异名同物 / 正常 / 抄码名重复）

### P1（应该有）

- **FR-608**：SPUID 列或客户列识别失败 → 提示支持的关键词
- **FR-609**：日志面板记录匹配结果
- **FR-610**：重新上传订单 → 覆盖旧数据

## 不涉及

- 不修改模块B
- 不修改 DeepSeek 复核
- 不修改规则引擎
- 不涉及实时同步

## 技术方案

### 改动位置

- `web/app.py` — 新增 `/api/upload-orders` + `/api/clean-export` 修改为多 Sheet 导出 + 保留/下架逻辑
- `web/templates/index.html` — 模块A 新增上传区 + 表格加 4 列

### 数据流

```
清洗 + DeepSeek 复核完成（现有流程）
         │
         ├─ 可选上传订单 Excel
         │     ├─ 识别 SPUID 列 + 客户列
         │     ├─ 统计: order_data[spuid] = {count, customers}
         │     └─ 存入 task_state['order_data']
         │
         ├─ 前端渲染结果（13 列）
         │     ├─ 有订单: 列1-9 + 保留/下架 + 替代编码 + 次数 + 客户
         │     └─ 无订单: 列1-9，后4列为空
         │
         └─ 导出 Excel（3 Sheet）
               ├─ Sheet1: 完全重复 + 异名同物
               ├─ Sheet2: 正常
               └─ Sheet3: 抄码名重复
```

### 列识别

```python
def find_order_columns(ws):
    spuid_kw = ['spuid', 'spu编码', '商品编码', 'code', '商品代码']
    customer_kw = ['客户', '商户名', '食堂名称', '客户名称', 'customer', '购货单位']
    spuid_col = customer_col = None
    for c in range(1, ws.max_column + 1):
        val = str(ws.cell(1, c).value or '').strip().lower()
        for kw in spuid_kw:
            if kw in val and spuid_col is None:
                spuid_col = c
        for kw in customer_kw:
            if kw in val and customer_col is None:
                customer_col = c
    return spuid_col, customer_col
```

### 数据处理

```python
# 输入: 订单 Excel
# 输出:
order_data = {
    "C33869996": {"count": 2, "customers": ["客户A", "客户B"]},
    "C33869997": {"count": 1, "customers": ["客户A"]},
}
```

### 保留/下架判定

```python
def resolve_keep_or_remove(group_rows, order_data):
    for r in group_rows:
        r['keep_or_remove'] = ''
        r['replace_spuid'] = ''
    if not order_data:
        return
    # 按订单命中次数排序
    counts = [(r, order_data.get(r['spuid'], {}).get('count', 0)) for r in group_rows]
    best = max(counts, key=lambda x: x[1])
    best_count = best[1]
    # 次数相同 → 保持空
    if best_count == 0 or len([c for _, c in counts if c == best_count]) > 1:
        return
    for r, cnt in counts:
        r['keep_or_remove'] = '保留' if r == best[0] else '下架'
        r['replace_spuid'] = best[0]['spuid'] if r != best[0] else [x for x in group_rows if x != best[0]][0]['spuid']
```

### task_state 新增字段

```python
task_state = {
    ...
    "order_data": None,  # {spuid: {count, customers}} or None
}
```

### 结果结构

```python
# clean_results 每行新增:
{
    ...原有9字段...,
    "keep_or_remove": "保留",     # 或 "下架" / ""
    "replace_spuid": "C33869997", # 或 ""
    "order_count": 2,             # 或 ""
    "order_customers": "客户A\n客户B"  # 或 ""
}
```

## 范围与边界

### 在范围内

- 选填上传 + 双列识别 + 统计 + 4列新增 + 多 Sheet 导出

### 不在范围内

- 模块B / DeepSeek / 规则引擎 / 多文件 / 实时同步

## 成功标准

- [ ] 清洗完成后出现"上传销售订单（可选）"上传区
- [ ] 上传 → 自动识别 SPUID + 客户列 → 表格 13 列
- [ ] 重复组内自动判定保留/下架
- [ ] 导出 Excel 分 3 Sheet
- [ ] 不上传 → 一切正常，无报错

## 验收方式

1. 清洗 → 上传订单 → 表格出现 4 列新数据
2. 重复组内"是否下架/保留"和"替代编码"正确交叉引用
3. 导出 → 3 Sheet 格式与参考文件一致

---
*基于 PROBLEM_六期.md + 重复编码下架保留清单.xlsx，日期：2026-05-28*
