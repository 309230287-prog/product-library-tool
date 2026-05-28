# 实施计划：三期 — 工具封装与交付

## 概述

Flask + HTML + PyInstaller。两步流程：规则引擎找候选 → DeepSeek 做判断。
复用二期 scripts/，不动引擎代码。

**成功标准：** 双击 exe 启动，上传接龙表，出查重结果，导出 Excel。

## 架构参考

[specs_三期/README.md](./specs_三期/README.md)

## 当前状态

| 任务 | 状态 |
|------|------|
| T301 judge.py | ✅ |
| T302 matcher对接 | ✅ |
| T303-T306 | ❌ |

## 任务清单

### 阶段 1：Flask 后端

- [ ] **T304-1：app.py 骨架 + Flask 初始化** `[未开始]`
  - 范围：`web/app.py`，创建 Flask app，`sys.path.insert` 引入 scripts/，加载 index.json 和 SemanticTranslator
  - 依赖：T302（已完成）
  - 产出：app 对象可启动
  - 验收：`python web/app.py` 不报错，`curl http://127.0.0.1:5000/` 返回 HTML

- [ ] **T304-2：POST /api/settings 保存设置** `[未开始]`
  - 范围：接收 `{api_key, model, api_url}`，更新 task_state 和 judge 模块
  - 依赖：T304-1
  - 产出：设置可保存
  - 验收：`curl -X POST /api/settings -d '{"api_key":"test"}'` → `{"ok":true}`

- [ ] **T304-3：POST /api/upload 上传文件** `[未开始]`
  - 范围：接收 .xlsx，校验格式，读入 openpyxl，返回预览前20条 + 总条数
  - 依赖：T304-1
  - 产出：文件上传+预览
  - 验收：上传接龙表 → 返回 `{preview:[...], total:646}`

- [ ] **T304-4：POST /api/start + 后台线程** `[未开始]`
  - 范围：启动后台线程，逐行调 `check_one()`，结果写入 `task_state['results']`，写入 ws 的 col12-14
  - 依赖：T304-3
  - 产出：可开始处理
  - 验收：上传后点开始 → 后台线程运行 → progress 增加

- [ ] **T304-5：GET /api/progress + /api/results** `[未开始]`
  - 范围：progress 返回 `{done, total, running}`，results 返回已完成列表
  - 依赖：T304-4
  - 产出：进度和结果可查询
  - 验收：处理中轮询 progress，值随 done 递增

- [ ] **T304-6：POST /api/stop + /api/pause** `[未开始]`
  - 范围：stop 设置 running=False，pause 切换 paused 状态
  - 依赖：T304-4
  - 产出：可停止/暂停
  - 验收：暂停后 progress.done 不变，停止后 running=False

- [ ] **T304-7：GET /api/export 下载结果** `[未开始]`
  - 范围：`task_state['wb']` 写入结果后 → `send_file(BytesIO)`
  - 依赖：T304-4
  - 产出：可下载 Excel
  - 验收：调用 /api/export → 下载 .xlsx 文件

- [ ] **T304-8：main() 启动入口** `[未开始]`
  - 范围：读 WEB_PORT 环境变量，启动 Flask，`webbrowser.open(url)`
  - 依赖：T304-1
  - 产出：双击 web/app.py 可启动
  - 验收：运行后浏览器自动打开，端口可配

### 阶段 2：HTML 前端

- [ ] **T305-1：页面骨架 + CSS** `[未开始]`
  - 范围：`web/templates/index.html`，顶部栏 + 两个stage（upload/working），CSS 样式
  - 依赖：T304-1
  - 产出：页面可渲染
  - 验收：浏览器打开 → 看到上传区域

- [ ] **T305-1b：首次使用引导** `[未开始]`
  - 范围：页面加载时检查 hasApiKey，未填则自动弹出设置弹窗提示"请先配置 API Key"；上传后检查返回是否报格式错，报错则提示接龙表列结构要求
  - 依赖：T305-1
  - 产出：首次使用不会茫然
  - 验收：清空Key后刷新页面 → 自动弹设置窗；上传错误格式文件 → 提示列结构

- [ ] **T305-2：设置弹窗** `[未开始]`
  - 范围：模态弹窗，三个字段（apiUrl/apiKey/model 预填默认值），保存调 `/api/settings`
  - 依赖：T305-1, T304-2
  - 产出：设置可保存
  - 验收：点⚙→弹窗→填Key→保存→关闭

- [ ] **T305-3：文件上传 + 预览** `[未开始]`
  - 范围：点击/拖拽上传，调 `/api/upload`，展示文件名+总条数+前20条预览
  - 依赖：T305-1, T304-3
  - 产出：上传流程
  - 验收：选文件 → 显示预览

- [ ] **T305-4：控制按钮 + 进度条** `[未开始]`
  - 范围：开始(调start)→轮询progress(0.5s)→更新进度条，暂停(调pause)，停止(调stop)，重置
  - 依赖：T305-3, T304-4/5/6
  - 产出：按钮可用
  - 验收：开始→进度条动，暂停→停，停止→结束

- [ ] **T305-5：结果表格 + 筛选** `[未开始]`
  - 范围：轮询时逐条追加表格行，颜色标签，筛选按钮切换视图，统计卡片更新
  - 依赖：T305-4, T304-5
  - 产出：结果可视化
  - 验收：处理中表格逐行增加，筛选生效

- [ ] **T305-6：导出按钮** `[未开始]`
  - 范围：调 `/api/export` 下载 Excel
  - 依赖：T304-7
  - 产出：可下载
  - 验收：点导出 → 浏览器下载 .xlsx

### 阶段 3：配置（P1）

- [ ] **T303：配置 Excel 模板** `[未开始]`
  - 范围：`配置.xlsx`，Sheet=加工前缀，translator.py 启动时读取，不存在用默认
  - 依赖：无（独立低优）
  - 产出：`配置.xlsx` + translator.py 一行读取代码
  - 验收：修改配置后新增前缀生效

### 阶段 4：打包

- [ ] **T306-1：安装 PyInstaller + 写 .spec** `[未开始]`
  - 范围：`pip install pyinstaller`，写 spec 文件
  - 依赖：T305
  - 产出：可执行打包命令
  - 验收：`pyinstaller 商品库工具.spec` 不报错

- [ ] **T306-2：打包 + 验证** `[未开始]`
  - 范围：打包出 exe，在开发机双击测试完整流程
  - 依赖：T306-1
  - 产出：`dist/商品库工具.exe`
  - 验收：双击 → 浏览器打开 → 上传 → 查重 → 导出

- [ ] **T306-3：无 Python 环境测试** `[未开始]`
  - 范围：复制 exe 到另一台无 Python 电脑，测试完整流程
  - 依赖：T306-2
  - 产出：验证通过
  - 验收：无 Python 电脑上正常运行

## 依赖关系

```
T304-1 → T304-2~8 → T305-1 → T305-2~6 → T306-1 → T306-2 → T306-3
T303 (独立低优)
```

## 待确认

- API Key 用户自己填还是预置？
- 基准库更新频率？

---
*基于 PRD_三期.md + specs_三期/，日期：2026-05-26*
