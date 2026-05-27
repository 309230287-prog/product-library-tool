"""
DeepSeek 语义判断模块 — 规则引擎是手脚，这是脑子
"""
import os, re, requests

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"


def judge(new_item: dict, candidates: list[dict]) -> dict:
    """判断新品能否复用库里编码
    new_item: {name, brand, unit, spec, category, remark}
    candidates: [{spuid, name, unit, spec, category, brand}, ...]
    返回: {result, suggested_spuid, detail}
    """
    if not candidates:
        return {"result": "需新增", "suggested_spuid": None,
                "detail": f'库中未找到与"{new_item["name"]}"相似的商品'}

    lines = [
        "你是生鲜供应链商品库去重专家。判断新品和库里候选是不是同一个商品。",
        "",
        "注意：箱=件，包=袋，20斤=10kg（1斤=500g），1*10kg=10kg。",
        "注意：括号里的杀好/公/母/包装不影响商品身份，大/小/中号影响。",
        "注意：品牌对比时，如果新品品牌出现在候选名称里（如新品品牌=新西兰LAMB，候选名=新西兰LAMB七骨羊排），视为品牌匹配。品牌不同=不同商品。",
        "注意：抄码=称重卖，和正常名称是同一个商品。",
        "",
        f"【新品】名称:{new_item['name']} | 品牌:{new_item.get('brand','')} | 单位:{new_item['unit']} | 规格:{new_item.get('spec','')} | 类别:{new_item.get('category','')}",
    ]
    if new_item.get('remark'):
        lines.append(f"备注:{new_item['remark']}")

    for i, c in enumerate(candidates[:5]):
        lines.append(f"【候选{i+1}】名称:{c['name']} | 品牌:{c.get('brand','')} | 单位:{c['unit']} | 规格:{c.get('spec','')} | 类别:{c.get('category','')} | SPUID:{c['spuid']}")

    lines.extend([
        "",
        "只回答两行：",
        "第一行：复用 或 新增 或 待确认",
        "第二行：如果复用，写SPUID（如C33878333）；如果新增或待确认，写原因",
    ])

    prompt = "\n".join(lines)

    try:
        resp = requests.post(API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 100, "temperature": 0},
            timeout=30)
        data = resp.json()
        answer = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return {"result": "待确认", "suggested_spuid": None, "detail": f"API调用失败:{e}"}

    first_line = answer.split('\n')[0].strip()
    if "复用" in first_line:
        m = re.search(r'C\d+', answer)
        spuid = m.group(0) if m else candidates[0]["spuid"]
        return {"result": "建议复用", "suggested_spuid": spuid, "detail": answer}
    elif "新增" in first_line:
        return {"result": "需新增", "suggested_spuid": None, "detail": answer}
    else:
        return {"result": "待确认", "suggested_spuid": None, "detail": answer}


def build_review_prompt(items: list[dict]) -> str:
    """构造清洗复核提示词"""
    lines = [
        "你是一名商品数据审核员。请判断以下多个商品信息是否指向同一个实际商品。",
        "",
        "判断规则：",
        "- 名称核心含义相同 + 单位相同 + 分类相同 → 是同一商品",
        "- 括号内内容如果是部位/品种（如二刀肉、红心、花鳝等），说明是不同的具体品种 → 不是同一商品",
        "- 括号内内容如果是加工状态（如杀好），一方有一方没有 → 不是同一商品，加工改变了商品形态",
        "- 规格/容量/重量不同（1kg vs 5kg）→ 不是同一商品",
        "- 鲜 vs 冻 vs 干 → 不是同一商品",
        "- 抄码（称重卖）和正常名称可以指向同一商品，也可能指向不同商品，以实际名称含义为准",
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
    """解析 yes/no 回答，返回 True/False/None（格式异常）"""
    answer = answer.strip().lower()
    if answer.startswith("yes") or answer.startswith("y"):
        return True
    if answer.startswith("no"):
        return False
    return None


def review_batch(groups: list[dict], model: str = "deepseek-chat") -> list[tuple[str, bool | None, str]]:
    """
    批量判断多组商品是否为同一商品。

    参数:
        groups: [{"group_id": "重103", "items": [{...}, {...}]}, ...]
        model: 模型名

    返回:
        [(group_id, result, reason), ...]
        result: True=是同一商品, False=不是, None=API异常
    """
    if not groups:
        return []

    # 构造批量提示词
    lines = [
        "你是一名商品数据审核员。请判断以下每组商品是否指向同一个实际商品。",
        "",
        "判断规则（严格按顺序执行）：",
        "1. 规格/容量/重量不同 → 不是同一商品",
        "2. 鲜/冻/干 状态不同 → 不是同一商品",
        "3. 括号内是不同部位/品种 → 不是同一商品",
        "4. 关键规则：加工状态（杀好/切片/去内脏等）不同的商品不是同一商品。"
        "例如：「黄骨鱼抄码」和「黄骨鱼（杀好）抄码」→ 不是同一商品。"
        "例如：「黄骨鱼抄码」和「黄骨鱼（杀好）」→ 是同一商品（抄码名配对）。",
        "5. 以上均不触发时，名称相同+单位相同+分类相同 → 是同一商品",
        "",
        "请输出一个JSON对象（不要其他文字），格式如：{\"重103\": false, \"重111\": true}，true=是同一商品、false=不是",
    ]

    for g in groups:
        gid = g['group_id']
        lines.append(f"\n--- {gid} ---")
        for i, item in enumerate(g['items'], 1):
            lines.append(
                f"  {i}. 名称：{item['name']}，单位：{item['unit']}，"
                f"描述：{item['desc']}，分类：{item['category']}"
            )

    lines.extend(["", "请输出每组判断（格式：组ID: yes/no）："])
    prompt = "\n".join(lines)

    for attempt in range(2):
        try:
            resp = requests.post(API_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 500, "temperature": 0},
                timeout=60)
            data = resp.json()
            answer = data["choices"][0]["message"]["content"].strip()
            return parse_batch_result(answer, groups)
        except Exception as e:
            print(f"[复核] API异常 ({attempt+1}/2): {e}")
            if attempt == 1:
                return [(g['group_id'], None, f"API异常: {e}") for g in groups]
    return [(g['group_id'], None, "未知错误") for g in groups]


def parse_batch_result(answer: str, groups: list[dict]) -> list[tuple[str, bool | None, str]]:
    """解析批量返回结果，优先JSON，回退正则"""
    import re, json
    results = []
    parsed = {}

    # 尝试 JSON 解析
    json_str = answer.strip()
    # 容错：去掉可能的 markdown ``` 包裹
    for prefix, suffix in [('```json\n', '\n```'), ('```\n', '\n```'), ('{', '}')]:
        if prefix in json_str:
            start = json_str.index(prefix) if prefix != '{' else json_str.index('{')
            end = json_str.rindex(suffix) + 1 if suffix != '}' else json_str.rindex('}') + 1
            json_str = json_str[start:end]
            if prefix == '{':
                json_str = json_str
            break
    try:
        for _ in range(3):  # 尝试修复常见 JSON 问题
            try:
                obj = json.loads(json_str)
                for gid, val in obj.items():
                    if isinstance(val, bool):
                        parsed[gid] = val
                    elif isinstance(val, str):
                        parsed[gid] = val.lower().startswith('y')
                break
            except json.JSONDecodeError:
                # 尝试修复：中文引号 → 英文引号
                json_str = json_str.replace('“', '"').replace('”', '"')
                continue
    except Exception:
        pass

    # JSON 解析成功则返回
    if parsed:
        for g in groups:
            gid = g['group_id']
            if gid in parsed:
                results.append((gid, parsed[gid], ""))
            else:
                results.append((gid, None, f"JSON中未找到{gid}"))
        return results

    # JSON 失败 → 回退正则
    for line in answer.strip().split('\n'):
        line = line.strip()
        m = re.search(r'(重\d+|抄\d+|异\d+)\s*[:：]\s*(yes|no|YES|NO|Yes|No|true|false)', line, re.IGNORECASE)
        if m:
            gid = m.group(1)
            val = m.group(2).lower()
            if val in ('true', 'false'):
                parsed[gid] = val == 'true'
            else:
                parsed[gid] = val.startswith('y')

    for g in groups:
        gid = g['group_id']
        if gid in parsed:
            results.append((gid, parsed[gid], ""))
        else:
            results.append((gid, None, f"DeepSeek返回格式异常: 未找到{gid}的结果"))
            print(f"[复核] 解析失败 原始返回({len(answer)}字): {answer[:200]}")
    return results
