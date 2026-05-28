# 模块B：新品查重 — 详细设计

## 1. 功能

Step1 上传清洗后的商品库建索引 → Step2 上传接龙表查重。

## 2. 涉及文件

`web/app.py`（新增 /api/build-index），`scripts/matcher.py`（不动），`scripts/judge.py`（不动）。

## 3. 路由设计

### POST /api/build-index

**请求：** FormData，字段 `file`，.xlsx 格式

**处理流程：**
```
1. 校验 .xlsx → openpyxl 读入
2. 校验列：col1(SPUID) + col2(名称) + col3(单位)
3. 后台线程执行 build_process()
4. 返回 {"ok": true, "total": N}
```

**build_process() 伪代码：**
```python
def build_process(wb):
    ws = wb['工作表1'] if '工作表1' in wb.sheetnames else wb.active
    index = {}
    for r in range(2, ws.max_row + 1):
        nm = translator.translate_name(cell(r,2), cell(r,5))
        dm = translator.translate_desc(cell(r,4), cell(r,3))
        spec = resolve_spec(nm, dm, has_proc=False)
        row = IndexedRow(spuid=cell(r,1), core=nm.core, brand=nm.brand, spec_core=spec.spec_core, unit=cell(r,3), raw_name=cell(r,2), category=cell(r,5), has_chaoma=nm.has_chaoma, has_status=nm.has_status, hit_count=0)
        index.setdefault(nm.core, []).append(row)
        build_progress['done'] += 1
    task_state['index'] = index
    build_progress['running'] = False
```

### GET /api/build-progress

**返回：** `{"done": 5000, "total": 11702, "running": true}`

### POST /api/start（修改三期版本）

**修改点：** check_one 第三个参数由 load_index 改为 task_state['index']：
```python
# 三期原版
result = check_one(translator, name, brand, spec, unit, cat, remark, index)
# 四期改为
if not task_state.get('index'):
    return jsonify({'error': '请先在Step1上传商品库建立索引'}), 400
result = check_one(translator, name, brand, spec, unit, cat, remark, task_state['index'])
```

## 4. 查重两步流程

```
check_one(translator, name, brand, spec, unit, cat, remark, index):
  第一步：规则引擎找候选
  1. translate_name/desc → nm, dm
  2. 查 index[nm.core] → 候选列表
  3. SYNONYM_MAP 异名查 → 合并候选
  4. 子串匹配 → 合并候选
  5. 去重 → 候选列表
  第二步：DeepSeek 判断
  6. 候选 = 0 → 返回 MatchResult("需新增", detail="库中未找到匹配")
  7. 候选 ≥ 1 → judge() → DeepSeek API → 返回判断结果
```

## 5. 错误处理

- DeepSeek API 超时/报错 → 该行标记"待确认"，detail 记录 `API异常: {原因}`
- 索引不存在时调用 /api/start → 400 "请先在 Step1 上传商品库"

## 6. task_state 新增字段

```python
task_state = {
    ...原有字段...,
    "index": None,
    "build_progress": {"done": 0, "total": 0, "running": False},
}
```

## 7. 索引生命周期

- 上传商品库 → 建索引 → 存 task_state['index']
- 查重期间 → 读取 task_state['index']
- 点重置 / 关闭程序 → task_state['index'] = None
- 下次启动 → 必须重新上传
