# PyInstaller 打包详细设计

## 1. 目标

将 `web/app.py` + `scripts/` + `web/templates/` + `index.json` 打包为单个 `商品库工具.exe`。

## 2. 安装 PyInstaller

```bash
pip install pyinstaller
```

## 3. 打包命令

```bash
cd d:\Users\weis\Desktop\编码整理
pyinstaller --onefile --name 商品库工具 --add-data "index.json;." --add-data "scripts;scripts" --add-data "web/templates;web/templates" --hidden-import flask --hidden-import openpyxl --hidden-import requests --hidden-import judge web/app.py
```

## 4. 参数说明

| 参数 | 作用 |
|------|------|
| `--onefile` | 打包为单个 exe |
| `--name 商品库工具` | exe 文件名 |
| `--add-data "index.json;."` | 把基准库打包进 exe |
| `--add-data "scripts;scripts"` | 二期引擎 |
| `--add-data "web/templates;web/templates"` | HTML 模板 |
| `--hidden-import flask` | 确保 Flask 被打包 |
| `--hidden-import openpyxl` | Excel 读写 |
| `--hidden-import requests` | HTTP 客户端 |
| `--hidden-import judge` | 判断模块 |

## 5. 需要处理的路径问题

PyInstaller 打包后 `__file__` 不可靠，需要用 `sys._MEIPASS`：

```python
# app.py 启动时
import sys
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INDEX_PATH = os.path.join(BASE_DIR, 'index.json')
SCRIPTS_PATH = os.path.join(BASE_DIR, 'scripts')
sys.path.insert(0, SCRIPTS_PATH)
```

## 6. app.py 需要的适配

```python
import sys, os

if getattr(sys, 'frozen', False):
    # 打包后运行
    BASE_DIR = sys._MEIPASS
    sys.path.insert(0, os.path.join(BASE_DIR, 'scripts'))
    template_folder = os.path.join(BASE_DIR, 'web', 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    # 开发环境
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
    app = Flask(__name__)
```

## 7. 预计体积

| 组件 | 大小 |
|------|------|
| Python 运行时 | ~60 MB |
| Flask + 依赖 | ~10 MB |
| openpyxl | ~5 MB |
| scripts/ | ~100 KB |
| index.json | ~3.5 MB |
| web/ | ~10 KB |
| **总计** | **~80 MB** |

## 8. .spec 文件（可选）

如果命令行参数不够，可手写 `商品库工具.spec`：

```python
# -*- mode: python -*-
a = Analysis(
    ['web/app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('index.json', '.'),
        ('scripts', 'scripts'),
        ('web/templates', 'web/templates'),
    ],
    hiddenimports=['flask', 'openpyxl', 'requests', 'judge'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='商品库工具', debug=False, strip=False, upx=True, console=False)
```

`console=False` 让 exe 不显示命令行黑窗口。

## 9. 启动序列

```
1. 用户双击 商品库工具.exe
2. exe 自解压到 %TEMP%\_MEIxxxx
3. Python 运行时启动
4. app.py main() 执行：
   a. 加载 index.json → SemanticTranslator
   b. 启动 Flask (127.0.0.1:5000)
   c. 打开浏览器
5. 用户关闭浏览器 → 手动退出 exe（或加自动退出逻辑）
```

## 10. 测试步骤

1. 开发机上 `python web/app.py` 先验证功能
2. `pyinstaller` 打包
3. 在 `dist/商品库工具.exe` 双击测试
4. 上传接龙表跑完完整流程
5. 在无 Python 的虚拟机或同事电脑上测试

## 11. 常见问题

| 问题 | 解决 |
|------|------|
| `ModuleNotFoundError: judge` | `--hidden-import judge` |
| `index.json not found` | 检查 `--add-data` 路径分隔符（Windows 用 `;`） |
| 端口被占用 | 改 `WEB_PORT` 环境变量 |
| exe 双击闪退 | 加 `input()` 或查看事件查看器 |
