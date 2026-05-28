# 实施计划：四期 — 完整 Web 工具

## 概述

一期清洗 + 二期查重 → Flask Web。双标签页，日志面板全追踪。38个任务，6个阶段。

## 架构参考

[specs_四期/README.md](./specs_四期/README.md)

## 任务清单

### 阶段 1：后端 — task_state + 模块A清洗（7个任务）

- [ ] **T401：task_state 加 clean_progress + clean_results** `[未开始]`
  - 范围：`web/app.py` 第18行附近，task_state dict 加两个 key
  - 代码：`"clean_progress": {"done": 0, "total": 0, "running": False},` 和 `"clean_results": [],`
  - 依赖：无
  - 产出：task_state 新增两个字段
  - 验收：`python -c "from web.app import task_state; print('clean_progress' in task_state and 'clean_results' in task_state)"` → True

- [ ] **T402：task_state 加 build_progress + index** `[未开始]`
  - 范围：同上 task_state，加两个 key
  - 代码：`"build_progress": {"done": 0, "total": 0, "running": False},` 和 `"index": None,`
  - 依赖：无
  - 验收：`python -c "from web.app import task_state; print('build_progress' in task_state and 'index' in task_state)"` → True

- [ ] **T403：所有路由函数第一行加 print** `[未开始]`
  - 范围：`web/app.py`，@app.route 下面的函数体第一行
  - 代码：`print(f"[API] /xxx 被调用")`，xxx 替换为路由路径（如 `/api/clean`、`/api/start` 等）
  - 依赖：无
  - 验收：`curl http://127.0.0.1:5000/` → 控制台输出 `[API] / 被调用`

- [ ] **T404：POST /api/clean 路由** `[未开始]`
  - 范围：`web/app.py`，新增路由函数
  - 代码：
    ```python
    @app.route('/api/clean', methods=['POST'])
    def clean():
        print("[API] /api/clean")
        file = request.files.get('file')
        if not file or not file.filename.endswith('.xlsx'):
            return jsonify({'error': '请上传 .xlsx 文件'}), 400
        try:
            wb = openpyxl.load_workbook(file)
        except Exception:
            return jsonify({'error': '无法读取文件，请确认格式正确'}), 400
        task_state['clean_progress'] = {'done': 0, 'total': 0, 'running': True}
        task_state['clean_results'] = []
        threading.Thread(target=clean_process, args=(wb,), daemon=True).start()
        return jsonify({'ok': True})
    ```
  - 依赖：T401
  - 验收：`curl -X POST http://127.0.0.1:5000/api/clean -F "file=@商品库整理.xlsx"` → `{"ok": true}`

- [ ] **T405：clean_process 线程函数** `[未开始]`
  - 范围：`web/app.py`，在 clean() 之前定义
  - 代码：
    ```python
    def clean_process(wb):
        from scripts.rules import RuleEngine
        ws = wb['工作表1'] if '工作表1' in wb.sheetnames else wb.active
        rows = []
        total = 0
        for r in range(2, ws.max_row + 1):
            name = str(ws.cell(r, 3).value or '').strip()
            if not name: continue
            total += 1
            nm = translator.translate_name(name, str(ws.cell(r, 5).value or ''))
            dm = translator.translate_desc(str(ws.cell(r, 4).value or ''), str(ws.cell(r, 3).value or ''))
            rows.append(ProductRow(spuid=str(ws.cell(r,1).value or ''), name_meaning=nm, unit=str(ws.cell(r,3).value or ''), desc_meaning=dm, category=str(ws.cell(r,5).value or '')))
        task_state['clean_progress']['total'] = total
        engine = RuleEngine(rows, translator)
        engine.run_all()
        for row in rows:
            task_state['clean_results'].append({'spuid': row.spuid, 'name': row.name_meaning.raw, 'unit': row.unit, 'desc': row.desc_meaning.raw, 'category': row.category, 'group_id': row.group_id or '', 'group_desc': row.group_desc or '', 'suggestion': row.suggestion or '', 'anomaly_class': row.anomaly_class or ''})
            task_state['clean_progress']['done'] += 1
            if task_state['clean_progress']['done'] % 200 == 0:
                print(f"[清洗] {task_state['clean_progress']['done']}/{total}")
        task_state['clean_progress']['running'] = False
    ```
  - 依赖：T404
  - 验收：清洗完成后控制台输出 `[清洗] 200/12440` → `[清洗] 12440/12440`

- [ ] **T406：GET /api/clean-progress** `[未开始]`
  - 代码：`return jsonify(task_state['clean_progress'])`
  - 依赖：T405
  - 验收：`curl /api/clean-progress` → `{"done":0,"total":0,"running":false}`

- [ ] **T407：GET /api/clean-results** `[未开始]`
  - 代码：`return jsonify({'results': task_state['clean_results'], 'total': len(task_state['clean_results'])})`
  - 依赖：T405
  - 验收：`curl /api/clean-results` → `{"results":[],"total":0}`

### 阶段 2：后端 — 模块B建索引+查重（6个任务）

- [ ] **T408：POST /api/build-index 路由** `[未开始]`
  - 代码：
    ```python
    @app.route('/api/build-index', methods=['POST'])
    def build_index():
        print("[API] /api/build-index")
        file = request.files.get('file')
        if not file: return jsonify({'error': '请上传文件'}), 400
        try:
            wb = openpyxl.load_workbook(file)
        except Exception:
            return jsonify({'error': '无法读取文件，请确认格式正确'}), 400
        task_state['build_progress'] = {'done': 0, 'total': 0, 'running': True}
        threading.Thread(target=build_process, args=(wb,), daemon=True).start()
        return jsonify({'ok': True})
    ```
  - 依赖：T402
  - 验收：`curl -X POST /api/build-index -F "file=@商品库整理_结果.xlsx"` → `{"ok":true}`

- [ ] **T409：build_process 线程函数** `[未开始]`
  - 代码：
    ```python
    def build_process(wb):
        ws = wb['工作表1'] if '工作表1' in wb.sheetnames else wb.active
        index = {}
        total = 0
        for r in range(2, ws.max_row + 1):
            name = str(ws.cell(r, 3).value or '').strip()
            if not name: continue
            total += 1
            nm = translator.translate_name(name, str(ws.cell(r, 5).value or ''))
            dm = translator.translate_desc(str(ws.cell(r, 4).value or ''), str(ws.cell(r, 3).value or ''))
            from translator import resolve_spec
            spec = resolve_spec(nm, dm, False)
            row = IndexedRow(spuid=str(ws.cell(r,1).value or ''), core=nm.core, brand=nm.brand, spec_core=spec.spec_core, has_processing=False, unit=str(ws.cell(r,3).value or ''), raw_name=str(ws.cell(r,2).value or ''), category=str(ws.cell(r,5).value or ''), has_chaoma=nm.has_chaoma, has_status=nm.has_status, hit_count=0)
            index.setdefault(nm.core, []).append(row)
            task_state['build_progress']['done'] = total
            if total % 200 == 0: print(f"[建索引] {total}")
        task_state['index'] = index
        task_state['build_progress']['total'] = total
        task_state['build_progress']['running'] = False
        print(f"[建索引] 完成 {total} 条, {len(index)} 个core")
    ```
  - 依赖：T408
  - 验收：控制台输出 `[建索引] 200` → `[建索引] 完成 11702 条, 10793 个core`

- [ ] **T410：GET /api/build-progress** `[未开始]`
  - 代码：`return jsonify(task_state['build_progress'])`
  - 依赖：T409
  - 验收：`curl /api/build-progress` → `{"done":0,"total":0,"running":false}`

- [ ] **T411：/api/start 加 index 检查** `[未开始]`
  - 范围：start() 函数第一行（request.get_json 之前）
  - 代码：
    ```python
    if not task_state.get('index'):
        print("[API] /api/start 被拒绝: 索引未建立")
        return jsonify({'error': '请先在Step1上传商品库建立索引'}), 400
    ```
  - 依赖：T409
  - 验收：不建索引直接调 /api/start → 400 `{"error":"请先在Step1上传商品库建立索引"}`

- [ ] **T412：check_one 改用内存 index** `[未开始]`
  - 范围：process() 函数中 check_one 调用
  - 代码：`result = check_one(translator, name, brand, spec, unit, cat, remark, task_state['index'])`
  - 依赖：T411
  - 验收：先建索引→再调 /api/start → 查重正常

- [ ] **T413：查重每行 print 日志** `[未开始]`
  - 范围：process() 函数循环体内
  - 代码：`print(f"[查重] {task_state['done']}/{task_state['total']} {name[:20]} → {result.result}")`
  - 依赖：T412
  - 验收：控制台逐行输出 `[查重] 1/646 六和鸭锁骨 → 建议复用`

### 阶段 3：前端 — 骨架（6个任务）

- [ ] **T414：HTML 顶栏 + 页面容器** `[未开始]`
  - 范围：`web/templates/index.html`，`<body>` 内第一部分
  - 代码：
    ```html
    <div class="bar">
      <h1>商品库工具 v2.0</h1>
      <div class="tabs">
        <button class="on">清洗去重</button>
        <button>新品查重</button>
      </div>
      <span class="spc"></span>
      <button class="gear">设置</button>
    </div>
    <div class="wrap">
      <div class="pg show" id="pgA"></div>
      <div class="pg" id="pgB"></div>
    </div>
    <div id="logPanel"></div>
    ```
  - 验收：浏览器打开看到顶栏和空白区域

- [ ] **T415：HTML 模块A 静态结构** `[未开始]`
  - 范围：`#pgA` 内完整 HTML，参考 demo_四期.html 的 pgA 区域，含步骤条(3个 step div，id 为 sa1/sa2/sa3)、上传区(id=upA)、进度条(id=progA)、提示(id=infoA)、统计卡片(id=statsA，4个卡片)、按钮区(导出+重置)、表格(id=twA，含thead和tbody)
  - 验证：`grep "id=\"sa1\"" web/templates/index.html` 有输出
  - 验收：页面可见模块A所有元素

- [ ] **T416：HTML 模块B 静态结构** `[未开始]`
  - 范围：`#pgB` 内完整 HTML，参考 demo_四期.html 的 pgB 区域，含步骤条(3个step，id=sb1/sb2/sb3)、上传区1(id=upB1)、进度条1(id=progB)、提示(id=infoB)、上传区2(id=upB2，class=lock)、统计卡片(id=statsB)、按钮(开始/暂停/停止/重置/导出，均带id)、进度条2(id=progB2)、筛选按钮(.btn-f ×3)、表格(id=twB)
  - 验证：`grep "id=\"sb1\"" web/templates/index.html` 有输出
  - 验收：Step2 上传区灰色锁定

- [ ] **T417：HTML 设置弹窗** `[未开始]`
  - 代码：
    ```html
    <div class="modal" id="modal">
      <div class="card">
        <h2>设置</h2>
        <label>API 地址</label><input value="https://api.deepseek.com/v1">
        <label>API Key</label><input type="password" id="apiKey" placeholder="sk-xxxx">
        <label>模型名</label><input value="deepseek-chat">
        <div class="mod-btns"><button>保存</button><button>取消</button></div>
      </div>
    </div>
    ```
  - 验收：点 ⚙ → 弹窗出现

- [ ] **T418：CSS 全部样式** `[未开始]`
  - 范围：`<style>` 标签，完整复制 demo_四期.html 的 CSS（约 70 行）
  - 验收：页面视觉与 demo_四期.html 一致

- [ ] **T419：日志面板 JS** `[未开始]**
  - 范围：`<script>` 标签最前面
  - 代码：
    ```javascript
    (function(){
      var p=document.getElementById('logPanel');
      function log(m,c){ var t=new Date().toLocaleTimeString(); p.innerHTML+='<div style="color:'+(c||'#0f0')+'">['+t+'] '+m+'</div>'; p.scrollTop=p.scrollHeight; }
      window.onerror=function(m,u,l,c,e){ log('ERROR: '+m+' (line '+l+')','#f44'); return false; };
      window._log=log; log('日志系统就绪','#ff0');
    })();
    ```
  - 验收：刷新页面 → 日志面板显示黄色 "日志系统就绪"

### 阶段 4：前端 — 模块A JS（6个任务）

- [ ] **T420：模块A 上传触发** `[未开始]`
  - 代码：
    ```javascript
    $('upA').onclick=function(){$('upA').querySelector('input').click()};
    $('upA').querySelector('input').onchange=function(){runA()};
    ```
  - 依赖：T418,T404
  - 验收：点上传区 → 文件选择弹窗 → 选文件 → _log 有记录

- [ ] **T421：模块A 轮询进度** `[未开始]`
  - 代码：
    ```javascript
    function runA(){
      _log('runA 开始清洗','#0ff');
      $('upA').style.display='none';$('progA').style.display='block';
      var file=$('upA').querySelector('input').files[0];
      var fd=new FormData();fd.append('file',file);
      fetch('/api/clean',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
        if(d.error){_log('ERROR:'+d.error,'#f44');return}
        var timer=setInterval(function(){
          fetch('/api/clean-progress').then(function(r){return r.json()}).then(function(p){
            $('pADone').textContent=p.done;$('pAFill').style.width=(p.done/p.total*100)+'%';
            if(!p.running){clearInterval(timer);finA();}
          });
        },500);
      });
    }
    ```
  - 依赖：T406,T420
  - 验收：上传后进度条开始走动

- [ ] **T422：模块A 统计卡片** `[未开始]**
  - 代码：
    ```javascript
    function finA(){
      fetch('/api/clean-results').then(function(r){return r.json()}).then(function(d){
        var results=d.results;
        var dupes=results.filter(function(x){return x.anomaly_class!=='正常'&&x.anomaly_class!=='缺省值'}).length;
        var normal=results.filter(function(x){return x.anomaly_class==='正常'}).length;
        var missing=results.filter(function(x){return x.anomaly_class==='缺省值'}).length;
        $('nTotal').textContent=results.length;$('nDup').textContent=dupes;$('nNormal').textContent=normal;$('nMissing').textContent=missing;
        $('statsA').style.display='flex';
        renderTableA(results);
      });
    }
    ```
  - 依赖：T407,T421
  - 验收：统计卡片数字正确

- [ ] **T423：模块A 表格渲染（颜色标签）** `[未开始]**
  - 代码：
    ```javascript
    function renderTableA(data){
      var h='';
      for(var i=0;i<data.length;i++){ var r=data[i]; h+='<tr>';
        h+='<td>'+r.spuid+'</td><td>'+r.name+'</td><td>'+r.unit+'</td><td>'+r.desc+'</td>';
        var c='',ac=r.anomaly_class||'正常';
        if(ac==='完全重复')c='r';else if(ac==='抄码名重复')c='y';else if(ac==='缺省值')c='y';else c='g';
        h+='<td><span class=\"tag '+c+'\">'+ac+'</span></td>';
        h+='<td>'+(r.group_id||'')+'</td><td>'+(r.suggestion||'')+'</td>';
        h+='</tr>'; }
      $('tbA').innerHTML=h;$('twA').style.display='block';
    }
    ```
  - 依赖：T422
  - 验收：表格有数据，颜色标签正确

- [ ] **T424：模块A 重置** `[未开始]**
  - 代码：
    ```javascript
    function resetA(){
      $('upA').style.display='block';$('progA').style.display='none';$('statsA').style.display='none';$('twA').style.display='none';$('tbA').innerHTML='';
      _log('模块A 重置','#ff0');
    }
    ```
  - 依赖：T423
  - 验收：点重置 → 上传区重现，统计和表格消失

- [ ] **T425：模块A _log 埋点** `[未开始]**
  - 范围：runA/finA/renderTableA/resetA 各函数已含 _log，逐行确认
  - 验证：`grep "_log" web/templates/index.html | grep -c "模块A\|runA\|finA\|resetA"` ≥ 4
  - 验收：日志面板记录模块A完整操作链路

### 阶段 5：前端 — 模块B JS（9个任务）

- [ ] **T426：Step1 上传建索引** `[未开始]**
  - 代码：
    ```javascript
    $('upB1').onclick=function(){$('upB1').querySelector('input').click()};
    $('upB1').querySelector('input').onchange=function(){runIdx()};
    function runIdx(){
      _log('runIdx 开始建索引','#0ff');
      $('upB1').style.display='none';$('progB').style.display='block';
      var file=$('upB1').querySelector('input').files[0];
      var fd=new FormData();fd.append('file',file);
      fetch('/api/build-index',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
        if(d.error){_log('ERROR:'+d.error,'#f44');return}
        var timer=setInterval(function(){
          fetch('/api/build-progress').then(function(r){return r.json()}).then(function(p){
            $('pBDone').textContent=p.done;$('pBFill').style.width=(p.done/p.total*100)+'%';
            if(!p.running){clearInterval(timer);finIdx(p.done);}
          });
        },500);
      });
    }
    ```
  - 依赖：T418,T408,T410
  - 验收：上传商品库 → 建索引进度条走动 → _log 有记录

- [ ] **T427：Step2 激活** `[未开始]**
  - 代码：
    ```javascript
    function finIdx(done){
      $('progB').style.display='none';
      $('infoB').textContent='索引就绪: '+done+' 条';$('infoB').classList.add('ok');
      var u=$('upB2');u.classList.remove('lock');
      u.innerHTML='<div class="ic">+</div><div class="tt" id="b2t">上传新品接龙表</div><div class="hi">点击或拖拽 .xlsx</div>';
      u.onclick=function(){selectFileB2()};
      u.ondragover=function(e){e.preventDefault();u.classList.add('drag')};
      u.ondragleave=function(){u.classList.remove('drag')};
      u.ondrop=function(e){e.preventDefault();u.classList.remove('drag');selectFileB2()};
      _log('finIdx Step2已激活','#0f0');
    }
    ```
  - 依赖：T426
  - 验收：建索引完成 → Step2 从灰色变为可点击 → _log 有记录

- [ ] **T428：selectFileB2 + 启用开始** `[未开始]**
  - 代码：
    ```javascript
    function selectFileB2(){
      $('b2t').textContent='已选择: 接龙表.xlsx';
      $('upB2').querySelector('.ic').textContent='V';
      $('bStart').disabled=false;
      _log('selectFileB2 开始按钮已启用','#0f0');
    }
    ```
  - 依赖：T427
  - 验收：点 Step2 → 显示已选择 → 开始按钮可点击

- [ ] **T429：按钮状态机** `[未开始]`
  - 代码：
    ```javascript
    $('bStart').onclick=function(){runB()};
    $('bPause').onclick=function(){toggleP()};
    $('bStop').onclick=function(){stopB()};
    $('bReset').onclick=function(){resetB()};
    function toggleP(){ B_paused=!B_paused; $('bPause').textContent=B_paused?'继续':'暂停'; _log('toggleP '+$('bPause').textContent,'#ff0'); }
    function stopB(){ if(B_timer){clearTimeout(B_timer);B_timer=null;}finB(); _log('stopB 已停止','#f80'); }
    function finB(){ $('bStart').disabled=false;$('bPause').disabled=true;$('bStop').disabled=true;_log('finB 完成','#0f0'); }
    ```
  - 依赖：T428
  - 验收：开始→暂停→继续→停止，按钮状态全程正确

- [ ] **T430：逐行查重 step()** `[未开始]`
  - 代码：
    ```javascript
    function runB(){
      $('bStart').disabled=true;$('bPause').disabled=false;$('bStop').disabled=false;
      $('statsB').style.display='flex';$('progB2').style.display='block';$('twB').style.display='block';$('tbB').innerHTML='';
      B_paused=false;B_timer=1;
      (function step(){
        if(B_timer===null){finB();return}
        if(B_paused){B_timer=setTimeout(step,500);return}
        fetch('/api/progress').then(function(r){return r.json()}).then(function(p){
          if(!p.running){finB();return}
          fetch('/api/results').then(function(r){return r.json()}).then(function(d){
            var all=d.results, lastN=all.slice(state.lastSeen||0);
            state.lastSeen=all.length;
            for(var j=0;j<lastN.length;j++){
              var r=lastN[j],c=r.result==='建议复用'?'g':r.result==='需新增'?'r':'y',l=r.result;
              var cc='';if(r.spuid)cc='<span class="tt-wrap">'+r.spuid+'<span class="tp">编码:'+r.spuid+'<br>名称:'+r.name+'<br>单位:'+r.unit+'<br>分类:'+r.cat+'<br>品牌:'+r.brand+'<br>规格:'+r.spec+'</span></span>';
              $('tbB').innerHTML+='<tr><td>'+r.row+'</td><td>'+r.name+'</td><td>'+r.unit+'</td><td><span class="tag '+c+'">'+l+'</span></td><td>'+cc+'</td><td>'+r.detail+'</td></tr>';
            }
            $('nbt').textContent=all.length; $('nbr').textContent=all.filter(function(x){return x.result==='建议复用'}).length; $('nbn').textContent=all.filter(function(x){return x.result==='需新增'}).length;
            $('pb2d').textContent=p.done; $('pb2f').style.width=(p.done/p.total*100)+'%';
            B_timer=setTimeout(step,500);
          });
        });
      })();
    }
    ```
  - 依赖：T429,T412
  - 验收：开始后表格逐行增加 → 进度条更新 → 统计数字变化

- [ ] **T431：筛选按钮** `[未开始]**
  - 代码：
    ```javascript
    function filB(type,btn){
      var bs=document.querySelectorAll('#pgB .btn-f');
      for(var i=0;i<bs.length;i++)bs[i].classList.remove('on');
      btn.classList.add('on');
      var d=type==='all'?B_data:B_data.filter(function(x){return x.result===type});
      renderB(d);
    }
    ```
  - 依赖：T430
  - 验收：点"建议复用"→仅显示复用行

- [ ] **T432：编码气泡** `[未开始]`
  - 范围：renderB 和 step 中已有 cc 拼接代码。CSS 加：
    ```css
    .tt-wrap{position:relative;cursor:pointer;color:#1a73e8;text-decoration:underline}
    .tt-wrap .tp{display:none;position:absolute;top:50%;left:calc(100%+8px);transform:translateY(-50%);background:#fff;color:#333;padding:8px 12px;border-radius:6px;font-size:11px;white-space:nowrap;z-index:999;line-height:1.7;box-shadow:0 3px 12px rgba(0,0,0,.15);border:1px solid #e0e0e0}
    .tt-wrap:hover .tp{display:block}
    ```
  - 验证：`grep "tt-wrap" web/templates/index.html | wc -l` ≥ 3（CSS + JS ×2）
  - 验收：悬停编码 → 白色气泡弹出完整信息

- [ ] **T433：模块B 重置** `[未开始]**
  - 代码：
    ```javascript
    function resetB(){
      if(B_timer){clearTimeout(B_timer);B_timer=null;}
      $('upB1').style.display='block';$('progB').style.display='none';$('infoB').classList.remove('ok');
      $('statsB').style.display='none';$('progB2').style.display='none';$('twB').style.display='none';
      var u=$('upB2');u.classList.add('lock');
      u.innerHTML='<div class="ic">X</div><div class="tt">请先上传商品库建立索引</div><div class="hi">完成 Step1 后激活</div>';u.onclick=null;
      $('bStart').disabled=true;$('bPause').disabled=true;$('bStop').disabled=true;$('tbB').innerHTML='';
      _log('模块B 已重置','#ff0');
    }
    ```
  - 依赖：T430
  - 验收：点重置 → Step2回到锁定，一切清空

- [ ] **T434：模块B _log 埋点** `[未开始]**
  - 验证：`grep "_log" web/templates/index.html` 覆盖 runIdx/finIdx/selectFileB2/runB/toggleP/stopB/finB/filB/resetB
  - 验收：日志面板完整记录模块B操作链路

### 阶段 6：杂项+打包（4个任务）

- [ ] **T435：标签切换 JS** `[未开始]**
  - 代码：
    ```javascript
    var tabs=document.querySelectorAll('.bar .tabs button');
    tabs[0].onclick=function(){tabs[0].classList.add('on');tabs[1].classList.remove('on');$('pgA').classList.add('show');$('pgB').classList.remove('show')};
    tabs[1].onclick=function(){tabs[1].classList.add('on');tabs[0].classList.remove('on');$('pgB').classList.add('show');$('pgA').classList.remove('show')};
    ```
  - 验收：切换标签 → 各自状态保持不丢

- [ ] **T436：设置保存对接** `[未开始]`
  - 代码：
    ```javascript
    document.querySelector('.gear').onclick=function(){$('modal').classList.add('show')};
    $('modal').querySelectorAll('button')[0].onclick=function(){
      var key=document.getElementById('apiKey').value;
      fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_key:key})});
      $('modal').classList.remove('show');_log('设置已保存','#0f0');
    };
    $('modal').querySelectorAll('button')[1].onclick=function(){$('modal').classList.remove('show')};
    ```
  - 验收：填Key → 保存 → 后端生效

- [ ] **T437：端到端验收** `[未开始]**
  - 范围：
    1. 模块A：上传商品库整理.xlsx → 清洗进度 → 统计 → 表格(颜色标签) → 重置
    2. 切换模块B：上传商品库整理_结果.xlsx → 建索引 → Step2激活
    3. 上传接龙表 → 开始 → 表格逐行 → 暂停/继续/停止 → 筛选 → 悬停气泡
    4. 切换回模块A → 之前清洗结果还在
    5. 设置 → 填Key → 保存
    6. 检查日志面板：全程无红色ERROR
  - 依赖：T425,T434,T435,T436
  - 验收：全部通过

- [ ] **T438：PyInstaller 打包** `[未开始]`
  - 命令：
    ```bash
    pip install pyinstaller
    pyinstaller --onefile --name 商品库工具 --add-data "scripts;scripts" --add-data "web/templates;web/templates" --hidden-import flask --hidden-import openpyxl --hidden-import requests --hidden-import judge web/app.py
    ```
  - 依赖：T437
  - 验收：双击 `dist/商品库工具.exe` → 浏览器打开 → 全流程可用

## 依赖关系

```
T401→T404→T405→T406→T407→T420→T421→T422→T423→T424→T425↘
T402→T408→T409→T410→T426→T427→T428→T429→T430→T431→T432→T433→T434↘
T403→T411→T412→T413                                          →T435→T436→T437→T438
T414→T415→T416→T417→T418→T419
```

---
*基于 PRD_四期.md + specs_四期/，日期：2026-05-27*
