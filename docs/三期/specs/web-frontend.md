# Web 前端 — HTML 单页详细设计

## 1. 文件位置

`web/templates/index.html` — 单文件，内嵌 CSS + JS。

## 2. 技术栈

- 纯 HTML5 + CSS3 + Vanilla JS（ES6）
- 无外部 CDN、无框架、无构建工具
- 通信：`fetch()` API
- 文件导出：Blob + `<a download>`

## 3. 完整页面结构

```html
<div class="topbar">
  商品库新品查重
  <button id="btnSettings">⚙ 设置</button>
</div>

<!-- 设置弹窗 -->
<div class="modal" id="modalSettings">
  <form>
    <label>API 地址 <input id="apiUrl" value="https://api.deepseek.com/v1"></label>
    <label>API Key  <input id="apiKey" type="password" placeholder="sk-xxxx"></label>
    <label>模型名   <input id="model" value="deepseek-chat"></label>
    <button>保存</button> <button type="button">取消</button>
  </form>
</div>

<!-- 主区域 -->
<div id="stageUpload">
  <div class="upload-zone">点击或拖拽上传接龙表 .xlsx</div>
  <input type="file" hidden>
</div>

<div id="stageWorking" style="display:none">
  <div class="actions">
    <button id="btnStart">▶ 开始</button>
    <button id="btnPause" disabled>⏸ 暂停</button>
    <button id="btnStop" disabled>⏹ 停止</button>
    <button id="btnReset">🔄 重置</button>
  </div>
  <div class="progress-bar">
    <div class="fill" id="progressFill"></div>
    <span id="progressText">0 / 0</span>
  </div>
  <div class="stats">
    <span id="statTotal">总计 0</span>
    <span id="statReuse">复用 0</span>
    <span id="statNew">新增 0</span>
  </div>
  <div class="filters">
    <button data-filter="all" class="active">全部</button>
    <button data-filter="建议复用">建议复用</button>
    <button data-filter="需新增">需新增</button>
    <button data-filter="待确认">待确认</button>
    <button id="btnExport" style="margin-left:auto">📥 导出 Excel</button>
  </div>
  <table>
    <thead><tr><th>序号</th><th>商品名称</th><th>单位</th><th>结果</th><th>建议编码</th><th>详情</th></tr></thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>
```

## 4. CSS 关键样式

- 配色：主色 `#1a73e8`（蓝），复用绿 `#1e8e3e`，新增红 `#d93025`，待确认黄 `#e37400`
- 上传区：虚线边框 + hover 高亮
- 表格：斑马纹（`tr:hover`），`table-layout:auto`
- 弹窗：居中遮罩层，白色卡片
- 进度条：圆角，transition 动画
- 响应式：`max-width: 1100px` 居中

## 5. JavaScript 状态管理

```javascript
let state = {
  file: null,           // 上传的 File 对象
  preview: [],          // 前20条预览
  total: 0,             // 总条数
  results: [],          // 已完成结果
  pollTimer: null,      // 轮询定时器ID
  currentFilter: 'all', // 当前筛选
  settings: {
    apiUrl: 'https://api.deepseek.com/v1',
    apiKey: '',
    model: 'deepseek-chat',
  }
};
```

## 6. 事件处理流程

### 6.1 文件选择 / 拖拽

```javascript
function onFileSelected(file) {
  if (!file.name.endsWith('.xlsx')) { showError('请上传 .xlsx 文件'); return; }
  state.file = file;
  uploadFile(file);  // POST /api/upload
}
```

`POST /api/upload` → 成功后：
- 显示文件名 + 总条数
- 展示预览表格（前20条，只读）：
  ```
  ┌─────────────────────────────────────┐
  │ 已上传：接龙表.xlsx  共 646 条       │
  │ 预览（前20条）：                     │
  │  # │ 名称        │ 品牌 │ 单位 │ ... │
  │  2 │ 六和鸭锁骨  │ ...  │ 箱   │     │
  │  ...                                │
  └─────────────────────────────────────┘
  ```
- 切换到 `stageWorking`
- `btnStart` 可用

### 6.2 开始处理

```javascript
async function onStart() {
  await fetch('/api/start', {method:'POST'});
  state.results = [];
  state.pollTimer = setInterval(pollProgress, 500);
  btnStart.disabled = true;
  btnPause.disabled = false;
  btnStop.disabled = false;
}
```

### 6.3 轮询进度

```javascript
async function pollProgress() {
  let r = await fetch('/api/progress'); let p = await r.json();
  updateProgressBar(p.done, p.total);
  if (p.done > state.results.length) {
    // 有新结果，增量拉取
    let r2 = await fetch('/api/results'); let d = await r2.json();
    state.results = d.results;
    renderTable(state.results, state.currentFilter);
    updateStats();
  }
  if (!p.running) {
    clearInterval(state.pollTimer);
    onFinished();
  }
}
```

### 6.4 暂停/停止/重置

- **暂停：** `POST /api/pause` → 切换按钮文字
- **停止：** `POST /api/stop` → 清定时器，恢复按钮
- **重置：** 清所有状态，回到 `stageUpload`

### 6.5 筛选

```javascript
function filter(type) {
  state.currentFilter = type;
  let data = type === 'all' ? state.results : state.results.filter(r => r.result === type);
  renderTable(data);
}
```

### 6.6 导出

```javascript
function exportExcel() {
  window.open('/api/export');
}
```

## 7. 渲染函数

### 7.1 表格渲染

```javascript
function renderTable(data) {
  let html = data.map(r => `
    <tr>
      <td>${r.row}</td>
      <td>${r.name}</td>
      <td>${r.unit}</td>
      <td><span class="tag tag-${r.result === '建议复用' ? 'ok' : r.result === '需新增' ? 'no' : 'maybe'}">${r.result}</span></td>
      <td>${r.spuid}</td>
      <td title="${r.detail}">${r.detail}</td>
    </tr>
  `).join('');
  document.getElementById('tableBody').innerHTML = html;
}
```

### 7.2 统计更新

```javascript
function updateStats() {
  document.getElementById('statTotal').textContent = `总计 ${state.results.length}`;
  document.getElementById('statReuse').textContent = `复用 ${state.results.filter(r => r.result === '建议复用').length}`;
  document.getElementById('statNew').textContent = `新增 ${state.results.filter(r => r.result === '需新增').length}`;
}
```

## 8. 错误处理

- fetch 异常 → 显示红色错误栏
- API 返回 error → alert 弹窗
- 网络断开 → 停止轮询，提示用户

## 9. 首次使用引导

- 页面加载时检查 API Key 是否为空
- 为空 → 自动弹出设置弹窗，提示"请先配置 API Key"
- 上传文件后检查是否有 *名称 列 → 没有则提示"表格格式可能不正确"
