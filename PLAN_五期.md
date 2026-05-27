# 实施计划：五期 — 规则引擎 + DeepSeek 复核

## 概述

clean_process 跑完规则引擎后，对标记为"完全重复""抄码名重复""异名同物"的行按组号分批送 DeepSeek 复核。DeepSeek 说"不是同一商品"的整组改回正常。5 个任务，1 个阶段。

## 架构参考

[specs_五期/README.md](./specs_五期/README.md) | [specs_五期/deepseek-review.md](./specs_五期/deepseek-review.md)

## 任务清单

### 阶段 1：DeepSeek 复核功能（5个任务）

- [ ] **T501：judge.py 新增 build_review_prompt 和 parse_yes_no** `[未开始]`
  - 范围：`scripts/judge.py` 末尾，新增两个辅助函数
  - 代码：
    ```python
    def build_review_prompt(items: list[dict]) -> str:
        lines = [
            "你是一名商品数据审核员。请判断以下多个商品信息是否指向同一个实际商品。",
            "",
            "判断规则：",
            "- 名称核心含义相同 + 单位相同 + 分类相同 → 是同一商品",
            "- 名称核心含义不同（如普通腊肉 vs 二刀肉，普通鳝鱼 vs 花鳝）→ 不是同一商品",
            "- 规格/容量/重量不同（1kg vs 5kg）→ 不是同一商品",
            "- 注意：抄码（称重卖）和正常规格描述可以指向同一商品，也可能指向不同商品，",
            "  以实际名称含义为准",
            "",
            "商品列表：",
        ]
        for i, item in enumerate(items, 1):
            lines.append(
                f"{i}. 名称：{item['name']}，单位：{item['unit']}，"
                f"描述：{item['desc']}，分类：{item['category']}"
            )
        lines.extend(["", "请仅回答 yes 或 no。"])
        return "\n".join(lines)

    def parse_yes_no(answer: str) -> bool | None:
        answer = answer.strip().lower()
        if answer.startswith("yes") or answer.startswith("y"):
            return True
        if answer.startswith("no"):
            return False
        return None
    ```
  - 依赖：无
  - 产出：judge.py 末尾新增两个辅助函数
  - 验收：`cd d:/Users/weis/Desktop/编码整理 && python -c "import sys; sys.path.insert(0, 'scripts'); from judge import build_review_prompt, parse_yes_no; print(parse_yes_no('yes')); print(parse_yes_no('no')); print(parse_yes_no('maybe'))"` → `True` `False` `None` 依次三行

- [ ] **T502：judge.py 新增 review_group 函数** `[未开始]`
  - 范围：`scripts/judge.py` 末尾（在 T501 辅助函数之后），新增主函数
  - 代码：
    ```python
    def review_group(items: list[dict], model: str = "deepseek-chat") -> tuple[bool | None, str]:
        prompt = build_review_prompt(items)
        for attempt in range(2):
            try:
                resp = requests.post(API_URL,
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={"model": model,
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 50, "temperature": 0},
                    timeout=30)
                data = resp.json()
                answer = data["choices"][0]["message"]["content"].strip()
                result = parse_yes_no(answer)
                if result is not None:
                    return result, ""
                reason = f"DeepSeek返回格式异常: {answer[:50]}"
                print(f"[复核] 格式异常, 重试 {attempt+1}/2")
            except Exception as e:
                reason = f"API异常: {e}"
                print(f"[复核] API异常 ({attempt+1}/2): {e}")
        return None, reason
    ```
  - 依赖：T501
  - 产出：judge.py 新增 review_group 函数
  - 验收：`cd d:/Users/weis/Desktop/编码整理 && python -c "import sys; sys.path.insert(0, 'scripts'); from judge import review_group; help(review_group)"` → 显示函数签名

- [ ] **T503：clean_process 追加复核代码** `[未开始]`
  - 范围：`web/app.py`，clean_process 函数末尾（当前第 244 行），`task_state['clean_progress']['running'] = False` 之前
  - 代码：在 `task_state['clean_progress']['running'] = False` 之前插入以下代码：
    ```python
        # === DeepSeek 复核 ===
        if not task_state.get('api_key'):
            print("[复核] 未设置 API Key，跳过复核")
            task_state['clean_progress']['running'] = False
            return

        import judge
        judge.API_KEY = task_state['api_key']
        judge.API_URL = task_state.get('api_url', 'https://api.deepseek.com/v1/chat/completions')
        model = task_state.get('model', 'deepseek-chat')

        review_classes = {'完全重复', '抄码名重复', '异名同物'}
        candidates = [r for r in task_state['clean_results'] if r['anomaly_class'] in review_classes]
        if not candidates:
            print("[复核] 无需要复核的行")
            task_state['clean_progress']['running'] = False
            return

        from collections import defaultdict
        groups = defaultdict(list)
        for r in candidates:
            gid = r['group_id']
            if gid:
                groups[gid].append(r)

        total_groups = len(groups)
        print(f"[复核] 开始, 共 {total_groups} 组")
        yes_count = no_count = err_count = 0

        for idx, (gid, items) in enumerate(groups.items(), 1):
            review_items = []
            for r in items:
                import re
                clean_name = re.sub(r'[-][A-Z]{2}\d+[【〔]?.*', '', r['name']).strip()
                review_items.append({'name': clean_name, 'unit': r['unit'],
                                     'desc': r['desc'], 'category': r['category']})
            result, reason = judge.review_group(review_items, model)
            if result is True:
                yes_count += 1
                print(f"[复核] {idx}/{total_groups} {gid} → yes")
            elif result is False:
                no_count += 1
                print(f"[复核] {idx}/{total_groups} {gid} → no")
                for r in items:
                    r['anomaly_class'] = '正常'
                    r['group_id'] = ''
                    r['suggestion'] = ''
            else:
                err_count += 1
                print(f"[复核] {idx}/{total_groups} {gid} → 异常: {reason}")
                for r in items:
                    r['anomaly_class'] = '待确认'
                    r['suggestion'] = reason

        print(f"[复核] 完成: {total_groups}组, yes={yes_count}, no={no_count}, 异常={err_count}")
    ```
  - 依赖：T502
  - 产出：clean_process 末尾追加复核代码
  - 验收：`python -c "import py_compile; py_compile.compile('web/app.py', doraise=True); print('Syntax OK')"` → Syntax OK

- [ ] **T504：端到端验证** `[未开始]`
  - 范围：启动服务 → 上传商品库 → 等待清洗+复核 → 检查结果
  - 命令：
    ```bash
    # 启动服务
    cd d:/Users/weis/Desktop/编码整理
    WEB_PORT=5002 python web/app.py &

    # 上传清洗 + 验证结果
    python -c "
    import requests, time
    with open('商品库整理.xlsx', 'rb') as f:
        r = requests.post('http://127.0.0.1:5002/api/clean', files={'file': ('test.xlsx', f)})
    print('Upload:', r.status_code, r.json())
    for _ in range(120):
        p = requests.get('http://127.0.0.1:5002/api/clean-progress').json()
        print(f'done={p[\"done\"]} total={p[\"total\"]} running={p[\"running\"]}')
        if not p['running']: break
        time.sleep(5)
    r = requests.get('http://127.0.0.1:5002/api/clean-results').json()
    results = r['results']
    # 重103和重111应该不再存在（DeepSeek判定不同商品）
    g103 = [x for x in results if x['group_id'] == '重103']
    g111 = [x for x in results if x['group_id'] == '重111']
    print(f'重103: {len(g103)}条 {"✓" if not g103 else "✗ 仍有"}')
    print(f'重111: {len(g111)}条 {"✓" if not g111 else "✗ 仍有"}')
    # 抄38应该仍保留
    g38 = [x for x in results if x['group_id'] == '抄38']
    print(f'抄38: {len(g38)}条 {"✓ 仍保留" if g38 else "✗ 消失"}')
    # 缺省值不变
    qs = [x for x in results if x['anomaly_class'] == '缺省值']
    print(f'缺省值: {len(qs)}条 {"✓" if len(qs)==229 else "✗ 不等于229"}')
    # 总数不变
    print(f'总条数: {len(results)} {"✓" if len(results)==12440 else "✗ 不等于12440"}')
    "
  - 依赖：T503
  - 验收：控制台输出全部 ✓，无 ✗。关键指标：重103=0条、重111=0条、抄38仍存在、缺省值=229、总条数=12440

- [ ] **T505：PyInstaller 重新打包** `[未开始]`
  - 命令：
    ```bash
    cd d:/Users/weis/Desktop/编码整理
    pyinstaller 商品库工具.spec
    ```
  - 依赖：T504
  - 产出：`dist/商品库工具.exe` 更新版
  - 验收：`ls -lh dist/商品库工具.exe` → 文件存在且大小 > 30MB

## 依赖关系

```
T501 → T502 → T503 → T504 → T505
```

## 待确认

- 无（需求、技术方案、实施计划全部对齐）

---
*基于 PRD_五期.md + specs_五期/ 生成，日期：2026-05-27*
