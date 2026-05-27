# 前端设计 — 详细设计

## 1. 文件

`web/templates/index.html`，单文件内嵌 CSS + JS。参考 `demo_四期.html`（已跑通）。

## 2. 页面结构

```
┌─ .bar (顶栏) ──────────────────────────────┐
│  h1 标题  [清洗去重] [新品查重]    ⚙设置    │
├─ .wrap (主区域) ───────────────────────────┤
│  #pgA.show / #pgB (页面切换)                │
│    ├─ .steps (步骤条)                       │
│    ├─ .up (上传区)                          │
│    ├─ .prg (进度条)                         │
│    ├─ .inf (信息提示)                       │
│    ├─ .st (统计卡片)                        │
│    ├─ .acts (按钮栏)                        │
│    ├─ .tb-scroll > .tb-wrap > table (表格)  │
│#logPanel (日志面板, position:fixed bottom)   │
│#modal (设置弹窗)                             │
└─────────────────────────────────────────────┘
```

## 3. CSS 关键规则

- `.pg{display:none}.pg.show{display:block}` — 页面切换
- `.up.lock{opacity:.35;pointer-events:none}` — 锁定态
- `.steps .s.go .n{background:#1a73e8}` — 当前步骤
- `.steps .s.ok .n{background:#1e8e3e}` — 完成步骤
- `.tb-scroll{max-height:380px;overflow-y:auto}` — 表格滚动容器
- 日志面板：`position:fixed;bottom:0;z-index:9999;background:#1a1a2e;color:#0f0`

## 4. JS 架构

### 全局工具

```javascript
function $(id){return document.getElementById(id)}
function setStep(e, s){e.classList.remove('go','ok'); if(s) e.classList.add(s)}
function _log(msg, color) // 写入 logPanel
```

### 模块A 函数链

```
click upA → runA() → (进度条动画) → finA() → 渲染表格
                                            → resetA() 清空
```

### 模块B 函数链

```
click upB1 → runIdx() → (建索引进度) → finIdx() → 激活 upB2
click upB2 → selectFileB2() → 启用 btnStart
click btnStart → runB() → (逐条step) → finB()
                      → toggleP() 暂停/继续
                      → stopB() 停止
                      → resetB() 清空
```

### 模块B 查重定时器

```javascript
var Btm = null; // 定时器句柄
function step() {
  if (Btm === null || i >= Bdata.length) { finB(); return; }
  // 渲染一行 → i++ → Btm = setTimeout(step, 350);
}
```

### 筛选

```javascript
function filB(type, btn) {
  // 更新按钮高亮 → 筛选 dataB → renderB()
}
```

### 标签切换

```javascript
tabs[0].onclick = function(){ /* show pgA, hide pgB */ }
tabs[1].onclick = function(){ /* show pgB, hide pgA */ }
```

## 5. 日志面板实现

```javascript
(function(){
  var panel = document.getElementById('logPanel');
  function log(msg, color){
    panel.innerHTML += '<div style="color:'+(color||'#0f0')+'">['+new Date().toLocaleTimeString()+'] '+msg+'</div>';
  }
  window.onerror = function(msg, url, line, col, err){
    log('ERROR: '+msg+' (line '+line+')', '#f44');
    return false;
  };
  window._log = log;
})();
```

## 6. 编码悬停气泡

HTML 结构由 JS 动态拼接，不写死任何值：

```javascript
// 每行渲染时动态生成
if (r.cd) {
  cc = '<span class="tt-wrap">' + r.cd +
       '<span class="tp">编码:' + r.cd +
       '<br>名称:' + r.na +
       '<br>单位:' + r.un +
       '<br>分类:' + r.ca +
       '<br>品牌:' + r.br +
       '<br>规格:' + r.sp + '</span></span>';
}
```

CSS 定位规则：
```css
.tt-wrap{position:relative;cursor:pointer}
.tt-wrap .tp{display:none;position:absolute;top:50%;left:calc(100%+8px);transform:translateY(-50%);background:#fff;...}
.tt-wrap:hover .tp{display:block}
```

## 7. 技术要求（兼容性）

- 不用 `classList.replace` → 用 `add` + `remove`
- 不用箭头函数 `=>` → 用 `function`
- 不用模板字符串 `` `${}` `` → 用 `+` 拼接
- 不用 `let/const` → 用 `var`

## 8. 状态隔离

模块A 和模块B 各自独立的 DOM 元素和 JavaScript 变量。切换标签页不触发任何重置。各自的重置按钮只清自己的数据和 UI。
