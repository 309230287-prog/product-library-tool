# 实施计划：六期 — 销售订单匹配

## 概述

模块A 清洗完成后，可选上传销售订单 Excel，按 SPUID 匹配，统计命中次数+客户名，判定保留/下架，结果 13 列，导出 3 Sheet。6 个任务，1 个阶段。

## 架构参考

[specs_六期/README.md](./specs_六期/README.md) | [specs_六期/order-matching.md](./specs_六期/order-matching.md)

## 任务清单

### 阶段 1：订单匹配功能（6个任务）

- [ ] **T601：task_state 加 order_data + find_order_columns 辅助函数** `[未开始]`
  - 范围：`web/app.py`，task_state dict 末尾 + 模块级
  - task_state 新增：
    ```python
        "order_data": None,
    ```
  - 模块级新增函数（放在 clean_process 之前或 build_process 附近）：
    ```python
    def find_order_columns(ws):
        """扫描第一行，返回 (spuid_col, customer_col) 1-based，未找到返回 None"""
        spuid_kw = ['spuid', 'spu编码', '商品编码', '编码', 'code', '商品代码']
        customer_kw = ['客户', '商户名', '食堂名称', '客户名称', 'customer', '购货单位']
        spuid_col = customer_col = None
        for c in range(1, ws.max_column + 1):
            val = str(ws.cell(1, c).value or '').strip().lower()
            if spuid_col is None:
                for kw in spuid_kw:
                    if kw in val:
                        spuid_col = c
                        break
            if customer_col is None:
                for kw in customer_kw:
                    if kw in val:
                        customer_col = c
                        break
            if spuid_col and customer_col:
                break
        return spuid_col, customer_col
    ```
  - 依赖：无
  - 验收：`python -c "import py_compile; py_compile.compile('web/app.py', doraise=True); print('Syntax OK')"` → Syntax OK

- [ ] **T602：POST /api/upload-orders 路由** `[未开始]`
  - 范围：`web/app.py`，在 clean-export 路由附近新增
  - 代码：
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
            return jsonify({'error': '未找到SPUID列，支持的列名：SPUID/商品编码/编码/code/商品代码/spu编码'}), 400
        order_data = {}
        for r in range(2, ws.max_row + 1):
            spuid = str(ws.cell(r, spuid_col).value or '').strip()
            if not spuid:
                continue
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
  - 依赖：T601
  - 验收：`python -c "from web.app import app; print('/api/upload-orders' in [r.rule for r in app.url_map.iter_rules()])"` → True

- [ ] **T603：apply_keep_remove + 修改 clean-results 返回** `[未开始]`
  - 范围：`web/app.py`，upload_orders 之前新增 apply_keep_remove 函数；修改 clean_results 路由函数
  - apply_keep_remove（模块级，放在 upload_orders 之前）：
    ```python
    def apply_keep_remove(clean_results, order_data):
        """只负责 keep_or_remove + replace_spuid，不碰 order_count/customers"""
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
                continue
            best = max(items, key=lambda x: order_data.get(x['spuid'], {}).get('count', 0))
            best_count = order_data.get(best['spuid'], {}).get('count', 0)
            if best_count == 0:
                continue
            tied = [r for r in items if order_data.get(r['spuid'], {}).get('count', 0) == best_count]
            if len(tied) > 1:
                continue
            for r in items:
                if r == best:
                    r['keep_or_remove'] = '保留'
                    other = [x for x in items if x != best][0]
                    r['replace_spuid'] = other['spuid']
                else:
                    r['keep_or_remove'] = '下架'
                    r['replace_spuid'] = best['spuid']
    ```
  - clean_results 路由修改（在 `return jsonify(...)` 之前插入）：
    ```python
        od = task_state.get('order_data')
        if od:
            for r in task_state['clean_results']:
                data = od.get(r['spuid'], {})
                r['order_count'] = data.get('count', '') if data.get('count', 0) > 0 else ''
                r['order_customers'] = '\n'.join(data.get('customers', []))
    ```
    并将 return 改为：
    ```python
        return jsonify({'results': task_state['clean_results'],
                        'total': len(task_state['clean_results']),
                        'has_order_data': task_state.get('order_data') is not None})
    ```
  - 依赖：T602
  - 验收：`python -c "from web.app import app; print('apply_keep_remove' in dir()); import py_compile; py_compile.compile('web/app.py', doraise=True); print('OK')"` → OK

- [ ] **T604：clean-export 改为 13 列 × 3 Sheet** `[未开始]`
  - 范围：`web/app.py` clean_export 函数，替换原有导出部分
  - 代码（完整替换 `if not task_state['clean_results']:` 之后到函数末尾）：
    ```python
    @app.route('/api/clean-export')
    def clean_export():
        print("[API] /api/clean-export")
        if not task_state['clean_results']:
            return jsonify({'error': '无清洗结果可导出'}), 400

        results = task_state['clean_results']
        # 同步派生订单数据（和 clean-results 一致）
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
                ws = wb.active
                ws.title = sheet_name
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
        wb.save(output)
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name='清洗结果.xlsx')
    ```

    注意：删除旧的 `clean_export` 函数定义，用新版本替换。
  - 依赖：T603
  - 验收：导出下载后 Excel 含 3 个 Sheet、13 列

- [ ] **T605：前端 — 上传区 + 表格加 4 列** `[未开始]`
  - 范围：`web/templates/index.html`，模块A 区域
  - HTML（在 `#pgA` 内部 `#twA` 的 `</div>` 之后、`</div><!-- /pgA -->` 之前）：
    ```html
      <div class="up" id="upOrders" style="display:none">
        <div class="ic">+</div>
        <div class="tt">上传销售订单（可选）</div>
        <div class="hi">用于统计编码引用次数、客户名称，辅助保留/下架决策</div>
        <input type="file" hidden accept=".xlsx">
      </div>
    ```
  - JS finA() 末尾加（在 `renderTableA(results);` 那行之后）：
    ```javascript
      $('upOrders').style.display = 'block';
    ```
  - JS 订单上传处理（放在模块A JS 区域，resetA 附近）：
    ```javascript
    $('upOrders').onclick = function(){ $('upOrders').querySelector('input').click(); };
    $('upOrders').querySelector('input').onchange = function(){
      var fd = new FormData(); fd.append('file', this.files[0]);
      fetch('/api/upload-orders', {method:'POST', body:fd}).then(function(r){return r.json()}).then(function(d){
        if(d.ok){
          _log('订单: '+d.total_rows+'行, '+d.unique_spuids+'编码, 匹配'+d.matched_existing+'条', '#0f0');
          fetch('/api/clean-results').then(function(r){return r.json()}).then(function(d){ renderTableA(d.results); });
        } else { _log('订单错误: '+d.error, '#f44'); }
      });
    };
    ```
  - renderTableA 完整替换：
    ```javascript
    function renderTableA(data){
      var hasOrders = false;
      for(var i = 0; i < data.length; i++){
        var oc = data[i].order_count;
        if(oc !== undefined && oc !== '' && oc !== 0){ hasOrders = true; break; }
      }
      var h = '<tr><th>SPUID</th><th>名称</th><th>单位</th><th>描述</th>'
        + '<th>异常分类</th><th>组号</th><th>建议</th>';
      if(hasOrders){
        h += '<th>是否下架/保留</th><th>替代编码</th><th>订单命中次数</th><th>订单命中客户</th>';
      }
      h += '</tr>';
      for(var i = 0; i < data.length; i++){
        var r = data[i], ac = r.anomaly_class || '正常';
        var c = ac === '完全重复' ? 'r' : ac === '抄码名重复' ? 'y' : ac === '缺省值' ? 'y' : 'g';
        h += '<tr><td>'+r.spuid+'</td><td>'+r.name+'</td><td>'+r.unit+'</td><td>'+r.desc+'</td>';
        h += '<td><span class="tag '+c+'">'+ac+'</span></td>';
        h += '<td>'+(r.group_id||'')+'</td><td>'+(r.suggestion||'')+'</td>';
        if(hasOrders){
          var kr = r.keep_or_remove || '', rs = r.replace_spuid || '';
          var oc = r.order_count !== undefined && r.order_count !== '' ? r.order_count : '-';
          var ocu = r.order_customers || '';
          ocu = ocu.replace(/\n/g, '<br>');
          h += '<td>'+kr+'</td><td>'+rs+'</td><td>'+oc+'</td><td style="font-size:11px">'+ocu+'</td>';
        }
        h += '</tr>';
      }
      $('tbA').innerHTML = h; $('twA').style.display = 'block';
    }
    ```
  - resetA 中追加一行：
    ```javascript
      $('upOrders').style.display = 'none';
    ```
  - 依赖：T604
  - 验收：`grep "upOrders" web/templates/index.html | wc -l` ≥ 3

- [ ] **T606：端到端验证 + PyInstaller 重新打包** `[未开始]`
  - 验证命令：
    ```bash
    # 1. 启动服务
    cd d:/Users/weis/Desktop/编码整理
    WEB_PORT=5003 python web/app.py &
    sleep 4

    # 2. 设置 Key + 上传清洗
    python -c "
    import requests, time
    r = requests.post('http://127.0.0.1:5003/api/settings', json={'api_key':'sk-f84f0301a4ac4a54afd270a518608f68'})
    print('Key:', r.json())
    with open('商品库整理.xlsx', 'rb') as f:
        r = requests.post('http://127.0.0.1:5003/api/clean', files={'file':('t.xlsx',f)})
    print('Clean:', r.status_code)
    for _ in range(120):
        p = requests.get('http://127.0.0.1:5003/api/clean-progress').json()
        if not p['running']: break
        time.sleep(3)
    print('Done:', p['done'], p['total'])
    "
    ```
  - 期待：清洗完成 12440/12440
  - 打包：
    ```bash
    cd d:/Users/weis/Desktop/编码整理
    pyinstaller 商品库工具.spec
    "C:/Users/weis/AppData/Local/Programs/Inno Setup 6/ISCC.exe" setup.iss
    ```
  - 验收：`ls -lh dist/商品库工具.exe dist/商品库工具_v2.0_安装包.exe` → 两个文件都存在
  - 依赖：T605
  - 产出：新版 exe + 安装包

## 依赖关系

```
T601 → T602 → T603 → T604 → T605 → T606
```

---
*基于 PRD_六期.md + specs_六期/ 生成，日期：2026-05-28*
