# DeepSeek 复核模块 — 详细设计

## 1. 功能

规则引擎跑完后，对标记为"完全重复""抄码名重复""异名同物"的行，按组号分组，每组调用一次 DeepSeek API 做语义判定。判定"不是同一商品"的整组改回"正常"，判定"是同一商品"的保持原标记。

## 2. 涉及文件

`web/app.py`（修改 clean_process），`scripts/judge.py`（新增 review_group）。

## 3. judge.py 新增函数

### review_group()

```python
def review_group(items: list[dict], model: str = "deepseek-chat") -> tuple[bool | None, str]:
    """
    判断同组商品是否为同一商品。
    
    参数:
        items: [
            {
                "name": "黄骨鱼抄码",       # 已去编码后缀的名称
                "unit": "斤",
                "desc": "抄码",
                "category": "水产类"
            },
            ...
        ]
        model: 模型名，默认 deepseek-chat
    
    返回:
        (True, "")         = 是同一商品（保持原标记）
        (False, "")        = 不是同一商品（改回正常）
        (None, "原因")     = API 异常（标为待确认，原因用于 detail）
    """
```

### API 请求参数

| 参数 | 值 |
|------|-----|
| model | `deepseek-chat`（或 task_state['model']） |
| max_tokens | 50（只需要 yes/no） |
| temperature | 0 |
| timeout | 30s |

### 提示词

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
```

### 响应解析

```python
def parse_yes_no(answer: str) -> bool | None:
    """返回 True=yes, False=no, None=格式异常"""
    answer = answer.strip().lower()
    if answer.startswith("yes") or answer.startswith("y"):
        return True
    if answer.startswith("no"):
        return False
    return None  # 格式异常
```

### 异常处理（含重试逻辑）

```python
def review_group(items: list[dict], model: str = "deepseek-chat") -> tuple[bool | None, str]:
    """
    返回 (result, reason):
        (True, "")      → 是同一商品
        (False, "")     → 不是同一商品
        (None, "原因")  → API 异常
    """
    prompt = build_review_prompt(items)
    
    for attempt in range(2):  # 首次 + 重试1次
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
            # 格式异常，重试
            reason = f"DeepSeek返回格式异常: {answer[:50]}"
            print(f"[复核] 格式异常, 重试 {attempt+1}/2")
        except Exception as e:
            reason = f"API异常: {e}"
            print(f"[复核] API异常 ({attempt+1}/2): {e}")
    
    return None, reason
```

## 4. clean_process 修改

### 修改位置

clean_process 函数末尾，`task_state['clean_progress']['running'] = False` 之前。

### 伪代码

```python
def clean_process(wb):
    # ... 现有逻辑：读Excel → 翻译 → 规则引擎 → 写task_state ...
    
    # === 新增：DeepSeek 复核 ===
    if not task_state.get('api_key'):
        print("[复核] 未设置 API Key，跳过复核")
        task_state['clean_progress']['running'] = False
        return
    
    import judge
    judge.API_KEY = task_state['api_key']
    judge.API_URL = task_state.get('api_url', 'https://api.deepseek.com/v1/chat/completions')
    model = task_state.get('model', 'deepseek-chat')
    
    # 1. 筛选需要复核的行
    review_classes = {'完全重复', '抄码名重复', '异名同物'}
    candidates = [r for r in task_state['clean_results']
                  if r['anomaly_class'] in review_classes]
    if not candidates:
        print("[复核] 无需要复核的行")
        task_state['clean_progress']['running'] = False
        return
    
    # 2. 按组号分组
    from collections import defaultdict
    groups = defaultdict(list)
    for r in candidates:
        gid = r['group_id']
        if gid:
            groups[gid].append(r)
    
    total_groups = len(groups)
    print(f"[复核] 开始, 共 {total_groups} 组")
    
    yes_count = 0
    no_count = 0
    err_count = 0
    
    for idx, (gid, items) in enumerate(groups.items(), 1):
        # 构造送审数据（去编码后缀）
        review_items = []
        for r in items:
            clean_name = re.sub(r'[-][A-Z]{2}\d+[【〔]?.*', '', r['name']).strip()
            review_items.append({
                'name': clean_name,
                'unit': r['unit'],
                'desc': r['desc'],
                'category': r['category'],
            })
        
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
    task_state['clean_progress']['running'] = False
```

### 名称清洗

送 DeepSeek 之前，名称需要去掉老编码后缀，避免 `-EE152717`、`-CC2536839【` 等干扰：

```python
import re
clean_name = re.sub(r'[-][A-Z]{2}\d+[【〔]?.*', '', r['name']).strip()
```

### 边界情况

| 场景 | 处理 |
|------|------|
| 没有 API Key | 跳过复核，输出警告 `[复核] 未设置 API Key，跳过复核` |
| 没有需要复核的行 | 直接跳复核阶段 |
| 某组只有一个商品 | 只有完全重复/抄码名重复/异名同物才会有组号，组内至少 2 个商品 |
| 同一 SPUID 出现在多组 | 每组独立判断，互不影响 |
| task_state['clean_results'] 为空 | 规则引擎没跑或没数据，跳过复核 |

## 5. 异常分类变化

### 复核前 → 复核后

```
复核前                         复核后
─────────────────────────────────────────────
完全重复 (387)      ─→   正常 (DeepSeek 说 no)
                         待确认 (API 异常)
                         完全重复 (DeepSeek 说 yes，保持不变)

抄码名重复 (256)    ─→   同上

异名同物 (12)       ─→   同上

缺省值 (229)        ─→   缺省值（不变）

正常 (11556)        ─→   正常（不变）
```

## 6. 数据一致性

- 修改直接在 `task_state['clean_results']` 的 dict 对象上操作，不需要重建列表
- 原子性：同一组内的所有行要么全改要么全不改
- 复核只改 `anomaly_class`、`group_id`、`suggestion` 三个字段
- `spuid`、`name`、`unit`、`desc`、`category`、`group_desc` 不修改

## 7. 进度输出完整示例

```
[清洗] 200/12440
[清洗] 400/12440
...
[清洗] 12440/12440
[复核] 开始, 共 312 组
[复核] 1/312 重103 → no
[复核] 2/312 重104 → yes
[复核] 3/312 重105 → yes
[复核] 4/312 重111 → no
...
[复核] 312/312 抄56 → yes
[复核] 完成: 312组, yes=298, no=12, 异常=2
```
