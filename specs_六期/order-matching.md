# 订单匹配模块 — 详细设计

## 1. 功能

清洗完成后，上传销售订单 Excel，自动识别 SPUID+客户列，统计命中次数和客户名称，按命中次数判定重复组保留/下架，导出 13 列 × 3 Sheet。

## 2. 涉及文件

`web/app.py`（新增路由 + 修改现有路由），`web/templates/index.html`（前端新增上传区 + 表格加列）。

## 3. 新增路由

### POST /api/upload-orders

**请求：** FormData, `file`, .xlsx

**处理流程：**
```
1. 校验 .xlsx → openpyxl 读入
2. 扫描第一行 → 识别 SPUID 列 + 客户列
3. 遍历数据行 → 统计 order_data[spuid] = {count, customers[]}
4. 对 clean_results 执行保留/下架判定
5. 返回统计信息
```

**伪代码：**
```python
@app.route('/api/upload-orders', methods=['POST'])
def upload_orders():
    print("[API] /api/upload-orders")
    file = request.files.get('file')
    if not file or not file.filename.endswith('.xlsx'):
        return jsonify({'error': '请上传 .xlsx 文件'}), 400
    try:
        wb = openpyxl.load_workbook(file)
        ws = wb.active
    except Exception:
        return jsonify({'error': '无法读取文件'}), 400

    spuid_col, customer_col = find_order_columns(ws)
    if not spuid_col:
        return jsonify({'error': '未找到SPUID列，支持的列名：SPUID/商品编码/编码/code'}), 400

    order_data = {}
    for r in range(2, ws.max_row + 1):
        spuid = str(ws.cell(r, spuid_col).value or '').strip()
        if not spuid: continue
        if spuid not in order_data:
            order_data[spuid] = {'count': 0, 'customers': []}
        order_data[spuid]['count'] += 1
        if customer_col:
            cust = str(ws.cell(r, customer_col).value or '').strip()
            if cust and cust not in order_data[spuid]['customers']:
                order_data[spuid]['customers'].append(cust)

    task_state['order_data'] = order_data
    apply_keep_remove(task_state['clean_results'], order_data)

    total_rows = ws.max_row - 1
    unique = len(order_data)
    matched = sum(1 for r in task_state['clean_results'] if r.get('order_count', 0) > 0)

    return jsonify({'ok': True, 'total_rows': total_rows,
                    'unique_spuids': unique, 'matched_existing': matched})
```

**响应示例：**
```json
{"ok": true, "total_rows": 15000, "unique_spuids": 8432, "matched_existing": 643}
```

### 列识别函数

> **前提假设**：订单文件第一行为表头行。如第一行不是表头（直接是数据），列识别会失败。
> 由用户在准备订单文件时确保这一点。

```python
def find_order_columns(ws) -> tuple[int | None, int | None]:
    """返回 (spuid_col, customer_col)，1-based"""
    spuid_kw = ['spuid', 'spu编码', '商品编码', 'code', '商品代码']  # 不含 'spu'，避免误匹配 SPU名称/SPU描述 列
    customer_kw = ['客户', '商户名', '食堂名称', '客户名称', 'customer', '购货单位']
    spuid_col = customer_col = None
    for c in range(1, ws.max_column + 1):
        val = str(ws.cell(1, c).value or '').strip().lower()
        if spuid_col is None:
            for kw in spuid_kw:
                if kw in val:
                    spuid_col = c; break
        if customer_col is None:
            for kw in customer_kw:
                if kw in val:
                    customer_col = c; break
        if spuid_col and customer_col:
            break
    return spuid_col, customer_col
```

### 保留/下架判定

```python
def apply_keep_remove(clean_results, order_data):
    """对同组内按订单命中次数判定保留/下架（只负责 keep_or_remove + replace_spuid）"""
    # 先清理旧数据（支持重新上传）
    for r in clean_results:
        r['keep_or_remove'] = ''
        r['replace_spuid'] = ''

    if not order_data:
        return
    from collections import defaultdict
    groups = defaultdict(list)
    review_classes = {'完全重复', '抄码名重复', '异名同物'}
    for r in clean_results:
        if r['group_id'] and r['anomaly_class'] in review_classes:
            groups[r['group_id']].append(r)
    for gid, items in groups.items():
        if len(items) < 2:
            continue  # 单成员组不判定
        best = max(items, key=lambda x: order_data.get(x['spuid'], {}).get('count', 0))
        best_count = order_data.get(best['spuid'], {}).get('count', 0)
        if best_count == 0:
            continue
        tied = [r for r in items if order_data.get(r['spuid'], {}).get('count', 0) == best_count]
        if len(tied) > 1:
            continue  # 并列最高，不判定
        for r in items:
            if r == best:
                r['keep_or_remove'] = '保留'
                other = [x for x in items if x != best][0]
                r['replace_spuid'] = other['spuid']
            else:
                r['keep_or_remove'] = '下架'
                r['replace_spuid'] = best['spuid']
```

**判定规则：**
```
同组内:
  订单次数最高且唯一 → "保留"（替代编码=对方）
  非最高 → "下架"（替代编码=最高者）
  次数相同(并列最高) → 都不填
  都没数据 → 都不填
```

## 4. 修改现有路由

### GET /api/clean-results 修改

```python
@app.route('/api/clean-results')
def clean_results():
    print("[API] /api/clean-results")
    od = task_state.get('order_data')
    results = task_state['clean_results']
    if od:
        for r in results:
            data = od.get(r['spuid'], {})
            r['order_count'] = data.get('count', '') if data.get('count', 0) > 0 else ''
            r['order_customers'] = '\n'.join(data.get('customers', []))
    return jsonify({'results': results, 'total': len(results),
                    'has_order_data': od is not None})
```

### GET /api/clean-export 修改

当前 8 列单 Sheet → 修改为 13 列 × 3 Sheet：

```python
@app.route('/api/clean-export')
def clean_export():
    print("[API] /api/clean-export")
    if not task_state['clean_results']:
        return jsonify({'error': '无清洗结果可导出'}), 400

    results = task_state['clean_results']
    # 先从 order_data 同步派生 order_count/customers（和 clean-results 一致）
    od = task_state.get('order_data')
    if od:
        for r in results:
            data = od.get(r['spuid'], {})
            r['order_count'] = data.get('count', '') if data.get('count', 0) > 0 else ''
            r['order_customers'] = '\n'.join(data.get('customers', []))
    sheet1 = [r for r in results if r['anomaly_class'] in ('完全重复', '异名同物')]
    sheet2 = [r for r in results if r['anomaly_class'] == '正常' and r.get('order_count', '') != '']
    sheet3 = [r for r in results if r['anomaly_class'] == '抄码名重复']

    wb = openpyxl.Workbook()
    headers = ['SPUID', 'SPU名称（可修改）', 'SPU基本单位', 'SPU描述（可修改）',
               '一级分类名称', '组号', '组说明', '建议', '异常分类',
               '是否下架/保留', '替代编码', '订单命中次数', '订单命中客户']

    for sheet_name, rows in [('Sheet1', sheet1), ('Sheet2', sheet2), ('Sheet3', sheet3)]:
        if sheet_name == 'Sheet1':
            ws = wb.active; ws.title = sheet_name
        else:
            ws = wb.create_sheet(sheet_name)
        ws.append(headers)
        for r in rows:
            ws.append([
                r['spuid'], r['name'], r['unit'], r['desc'], r['category'],
                r['group_id'], r['group_desc'], r['suggestion'], r['anomaly_class'],
                r.get('keep_or_remove', ''), r.get('replace_spuid', ''),
                r.get('order_count', ''), r.get('order_customers', ''),
            ])

    output = io.BytesIO()
    wb.save(output); output.seek(0)
    return send_file(output, mimetype='...spreadsheetml.sheet',
                     as_attachment=True, download_name='清洗结果.xlsx')
```

## 5. task_state 新增字段

```python
task_state = {
    ...
    "order_data": None,  # {spuid: {count: int, customers: [str]}}
}
```

clean_results 每行新增字段（dict key）：

| key | 含义 | 示例 |
|-----|------|------|
| keep_or_remove | 是否下架/保留 | "保留" / "下架" / "" |
| replace_spuid | 替代编码 | "C33869997" / "" |
| order_count | 订单命中次数 | 42 / "" |
| order_customers | 订单命中客户 | "客户A\n客户B" / "" |

## 6. 前端改动

### 上传区

```html
<div class="up" id="upOrders" style="display:none">
  <div class="ic">+</div>
  <div class="tt">上传销售订单（可选）</div>
  <div class="hi">用于统计编码引用次数、客户名称，辅助保留/下架决策</div>
  <input type="file" hidden accept=".xlsx">
</div>
```

### JS

```javascript
// finA() 中显示
$('upOrders').style.display = 'block';

$('upOrders').onclick = function(){ $('upOrders').querySelector('input').click(); };
$('upOrders').querySelector('input').onchange = function(){
  var fd = new FormData(); fd.append('file', this.files[0]);
  fetch('/api/upload-orders', {method:'POST', body:fd})
    .then(function(r){return r.json()}).then(function(d){
      if(d.ok){
        _log('订单: '+d.total_rows+'行, '+d.unique_spuids+'编码, 匹配'+d.matched_existing+'条', '#0f0');
        fetch('/api/clean-results').then(function(r){return r.json()})
          .then(function(d){ renderTableA(d.results); });
      } else { _log('订单错误: '+d.error, '#f44'); }
    });
};
```

### 表格加列

renderTableA 检测 data 中是否有 order_count，有则表头加 4 列：

```javascript
var hasOrders = false;
for(var i=0;i<data.length;i++){
  if(data[i].order_count !== undefined && data[i].order_count !== ''){
    hasOrders = true; break;
  }
}
if(hasOrders){
  h += '<th>是否下架/保留</th><th>替代编码</th><th>订单命中次数</th><th>订单命中客户</th>';
}
```

每行数据：

```javascript
var kr = r.keep_or_remove || '';
var rs = r.replace_spuid || '';
var oc = r.order_count !== undefined && r.order_count !== '' ? r.order_count : '-';
var ocu = r.order_customers || '';
// 客户名中的 \n 转为 <br>
ocu = ocu.replace(/\n/g, '<br>');
h += '<td>'+kr+'</td><td>'+rs+'</td><td>'+oc+'</td><td style="font-size:11px">'+ocu+'</td>';
```

## 7. 错误处理

| 场景 | 处理 |
|------|------|
| 非 .xlsx | 400 "请上传 .xlsx 文件" |
| Excel 损坏 | 400 "无法读取文件" |
| 无 SPUID 列 | 400 + 列出支持的关键词 |
| 无数据行 | 400 "订单文件无数据" |
| 不上传 | order_data=None，后 4 列空 |

## 8. 边界情况

| 场景 | 处理 |
|------|------|
| 同组次数相同 | 两个都不填保留/下架 |
| 都没订单数据 | 全都不填 |
| 正常行匹配到订单 | 有订单数据但不填保留/下架（无组号） |
| 重新上传 | 覆盖 order_data，重新判定 |
| 客户重复出现 | customers 去重 |

---
*基于 PRD_六期.md 生成，日期：2026-05-28*
