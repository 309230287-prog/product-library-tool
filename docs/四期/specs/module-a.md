# 模块A：清洗去重 — 详细设计

## 1. 功能

用户上传原始商品库 Excel → 系统翻译 + 规则引擎清洗 → 展示统计和结果。

## 2. 涉及文件

`web/app.py`（新增路由），`scripts/rules.py`（不动，直接 import），`scripts/translator.py`（不动）。

## 3. 路由设计

### POST /api/clean

**请求：** FormData，字段 `file`，.xlsx 格式

**处理流程：**
```
1. 校验扩展名 .xlsx
2. openpyxl.load_workbook(file)
3. 校验列：col1(SPUID) + col2(名称) + col3(单位) 存在且非空
4. 后台线程执行 clean_process()
5. 返回 {"ok": true, "total": N}
```

**clean_process() 伪代码：**
```python
def clean_process(wb):
    ws = wb.active
    rows = []
    for r in range(2, ws.max_row + 1):
        nm = translator.translate_name(cell(r,2), cell(r,5))
        dm = translator.translate_desc(cell(r,4), cell(r,3))
        rows.append(ProductRow(spuid=cell(r,1), name_meaning=nm, unit=cell(r,3), desc_meaning=dm, category=cell(r,5)))
    engine = RuleEngine(rows, translator)
    engine.run_all()
    # 收集结果
    for row in rows:
        clean_results.append({spuid, name, unit, desc, category, group_id, group_desc, suggestion, anomaly_class})
    clean_progress['done'] = total
```

**错误处理：**
- 非 .xlsx → 400 "请上传 .xlsx 文件"
- 列缺失 → 400 "缺少第N列（列名）"
- Excel 损坏 → 400 "无法读取文件，请确认格式正确"

### GET /api/clean-progress

**返回：** `{"done": 5000, "total": 12440, "running": true}`

### GET /api/clean-results

**返回：** `{"total": 12440, "dupes": 738, "normal": 11702, "results": [...]}`

## 4. task_state 新增字段

```python
task_state = {
    ...原有字段...,
    "clean_progress": {"done": 0, "total": 0, "running": False},
    "clean_results": [],
    "clean_stats": {"total": 0, "dupes": 0, "normal": 0, "missing": 0},
}
```

## 5. 进度机制

每翻译 200 条更新 `clean_progress['done']`。前端每 0.5 秒轮询 /api/clean-progress。

## 6. 输出格式

结果表格列：SPUID / 名称 / 单位 / 描述 / 异常分类 / 组号 / 建议
异常分类颜色：完全重复(红) / 抄码名重复(黄) / 缺省值(橙) / 正常(绿)

## 7. 一期代码接口

```python
from scripts.rules import RuleEngine
from scripts.translator import SemanticTranslator, ProductRow

translator = SemanticTranslator()  # 复用全局实例
```
