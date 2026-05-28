# Web 后端 — Flask API 详细设计

## 1. 文件位置

`web/app.py` — 单文件，约150行。

## 2. 依赖和导入

```python
import sys, os, io, json, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from flask import Flask, render_template, request, jsonify, send_file
from translator import SemanticTranslator
from matcher import load_index, check_one
from judge import API_URL as JUDGE_URL
import openpyxl
```

## 3. 全局状态

```python
task_state = {
    "running": False,       # 后台线程是否运行中
    "paused": False,        # 用户是否暂停
    "done": 0,              # 已完成行数
    "total": 0,             # 总行数
    "results": [],          # [{row, name, unit, result, spuid, detail}, ...]
    "wb": None,             # openpyxl Workbook 对象（上传时加载，导出时写入）
    "api_key": "",          # DeepSeek API Key
    "model": "deepseek-chat",  # 模型名
    "api_url": "https://api.deepseek.com/v1",  # API 地址
    "error": None,          # 错误信息
}
```

## 4. Flask App 初始化

```python
app = Flask(__name__)
INDEX_PATH = os.path.join(os.path.dirname(__file__), '..', 'index.json')
translator = SemanticTranslator()
index = load_index(INDEX_PATH)
```

index.json 不存在时打印明确错误并退出。

## 5. 接龙表列映射

```python
COLS = {
    'brand': 2,      # *品牌
    'name': 3,       # *名称
    'spec': 4,       # *规格
    'category': 5,   # *类别
    'unit': 6,       # *单位
    'remark': 7,     # 备注
}
```

## 6. API 路由详细设计

### 6.1 GET `/` — 首页

返回 `render_template('index.html')`。

### 6.2 POST `/api/settings` — 保存设置

**请求：**
```json
{"api_key": "sk-xxx", "model": "deepseek-chat", "api_url": "https://api.deepseek.com/v1"}
```

**处理：**
1. 更新 `task_state['api_key']`、`task_state['model']`、`task_state['api_url']`
2. 更新 `judge.API_KEY` 和 `judge.API_URL`（热生效）
3. 返回 `{"ok": true}`

**错误：** 无。

### 6.3 POST `/api/upload` — 上传接龙表

**请求：** FormData，字段名 `file`，文件类型 .xlsx

**处理：**
1. 校验文件扩展名 .xlsx
2. `openpyxl.load_workbook(file)` 读入内存
3. 定位 sheet（优先 `工作表1`，否则 `wb.active`）
4. 校验必填列：col 3（*名称）不能全空
5. 统计总行数（名称非空的行）
6. 生成预览：取前20行，返回 `[{row, name, brand, spec, unit, category, remark}]`
7. 把 wb 存到 `task_state['wb']`

**响应：**
```json
{
  "preview": [{"row": 2, "name": "冬枣", ...}, ...],
  "total": 646
}
```

**错误处理：**
- 非 .xlsx 文件 → 400 `{"error": "请上传 .xlsx 文件"}`
- 无名称列 → 400 `{"error": "表格缺少*名称列（第3列）"}`
- openpyxl 解析失败 → 400 `{"error": "无法读取文件，请确认格式正确"}`

### 6.4 POST `/api/start` — 开始处理

**请求：** 无参数（文件已在 upload 阶段加载）

**处理：**
1. 检查 `task_state['running']` — 已有任务 → 400
2. 检查 `task_state['api_key']` — 未配置 → 400 `{"error": "请先在设置中填写 API Key"}`
3. 检查 `task_state['wb']` — 未上传 → 400 `{"error": "请先上传接龙表"}`
4. 清空 `task_state['results']`，设置 `total` 和 `done=0`
5. 设置 `running=True`
6. 启动后台线程 `process_task()`
7. 返回 `{"ok": true, "total": N}`

**后台线程 `process_task()`：**
```python
def process_task():
    ws = task_state['wb'].active  # 或 工作表1
    for r in range(2, ws.max_row + 1):
        if not task_state['running']:
            break
        while task_state['paused']:
            time.sleep(0.5)
            if not task_state['running']:
                return

        name = str(ws.cell(r, COLS['name']).value or '').strip()
        if not name:
            continue

        # 提取字段
        brand_raw = str(ws.cell(r, COLS['brand']).value or '').strip()
        brand = None if (not brand_raw or brand_raw in ('None', '无要求')) else brand_raw

        try:
            result = check_one(
                translator,
                name,
                brand,
                str(ws.cell(r, COLS['spec']).value or '').strip(),
                str(ws.cell(r, COLS['unit']).value or '').strip(),
                str(ws.cell(r, COLS['category']).value or '').strip(),
                str(ws.cell(r, COLS['remark']).value or '').strip(),
                index
            )
            # col 11=系统名称, col 12=系统编码(接龙表原有), col 13/14=新增
            if result.result == '建议复用' and result.suggested_spuid:
                ws.cell(r, 12, value=result.suggested_spuid)  # 系统编码
            ws.cell(r, 13, value=result.result)         # 匹配结果
            ws.cell(r, 14, value=result.detail)          # 匹配详情
            task_state['results'].append({
                'row': r, 'name': name, 'unit': str(ws.cell(r, COLS['unit']).value or ''),
                'result': result.result, 'spuid': result.suggested_spuid or '',
                'detail': result.detail,
            })
        except Exception as e:
            task_state['results'].append({
                'row': r, 'name': name, 'unit': '',
                'result': '待确认', 'spuid': '', 'detail': f'处理异常: {e}',
            })

        task_state['done'] += 1

    task_state['running'] = False
```

### 6.5 GET `/api/progress` — 查询进度

**响应：**
```json
{"done": 45, "total": 646, "running": true, "paused": false}
```

### 6.6 GET `/api/results` — 获取结果

返回 `task_state['results']` 列表。

### 6.7 POST `/api/stop` — 停止

设置 `running=False`, `paused=False`。

### 6.8 POST `/api/pause` — 暂停/继续

切换 `paused` 状态。返回 `{"paused": true/false}`。

### 6.9 GET `/api/export` — 导出 Excel

```python
output = io.BytesIO()
task_state['wb'].save(output)
output.seek(0)
return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                 as_attachment=True, download_name='查重结果.xlsx')
```

如果 wb 为空 → 400。

## 7. 启动入口

```python
def main():
    import webbrowser
    port = int(os.environ.get('WEB_PORT', 5000))
    url = f'http://127.0.0.1:{port}'
    webbrowser.open(url)
    print(f'服务已启动: {url}')
    app.run(host='127.0.0.1', port=port, debug=False)

if __name__ == '__main__':
    main()
```

## 8. 错误处理总则

- 所有 /api/* 路由 try/except 包裹，意外异常返回 500 `{"error": "服务器内部错误"}`
- 不在 response 中暴露 traceback

## 9. 与二期引擎的接口

直接 import 使用：
- `translator.translate_name(name, category)`
- `matcher.load_index(path) → dict`
- `matcher.check_one(translator, name, brand, spec, unit, category, remark, index) → MatchResult`
- `judge.API_KEY` — 可运行时修改
- `judge.API_URL` — 可运行时修改
