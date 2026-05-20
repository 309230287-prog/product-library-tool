"""
报告生成器 — 汇总报告 + 待确认清单
"""
from translator import ProductRow


def format_summary(summary: dict, total: int) -> str:
    rows = [
        f"\n{'='*60}",
        f" 商品库整理汇总报告",
        f"{'='*60}",
        f" 总行数:                {total}",
        "",
    ]
    wq = summary.get('缺省值', 0)
    if isinstance(wq, tuple):
        wq = wq[0]
    rows.append(f" 缺省值:                {wq}")

    wr = summary.get('完全重复', (0, 0))
    rows.append(f" 完全重复:              {wr[0]} ({wr[1]} 组)" if isinstance(wr, tuple) else f" 完全重复:              {wr}")

    cm = summary.get('抄码名重复', (0, 0))
    rows.append(f" 抄码名重复:            {cm[0]} ({cm[1]} 组)" if isinstance(cm, tuple) else f" 抄码名重复:            {cm}")

    ym = summary.get('异名同物', (0, 0))
    rows.append(f" 异名同物:              {ym[0]} ({ym[1]} 组)" if isinstance(ym, tuple) else f" 异名同物:              {ym}")

    nm = summary.get('正常', 0)
    rows.append(f" 正常:                  {nm}")
    rows.append("")
    rows.append(f" 分类冲突_待确认:       {summary.get('分类冲突', 0)}")
    rows.append(f" 规格待确认:            {summary.get('规格待确认', 0)}")

    total_marked = (
        (summary.get('缺省值', 0) if not isinstance(summary.get('缺省值'), tuple) else summary['缺省值']) +
        (summary.get('完全重复', (0, 0))[0] if isinstance(summary.get('完全重复'), tuple) else summary.get('完全重复', 0)) +
        (summary.get('抄码名重复', (0, 0))[0] if isinstance(summary.get('抄码名重复'), tuple) else summary.get('抄码名重复', 0)) +
        (summary.get('异名同物', (0, 0))[0] if isinstance(summary.get('异名同物'), tuple) else summary.get('异名同物', 0)) +
        (summary.get('正常', 0) if not isinstance(summary.get('正常'), tuple) else summary['正常'])
    )
    status = '✓' if total_marked == total else '✗'
    rows.append(f" 合计:                  {total_marked} / {total}  {status}")
    rows.append(f"{'='*60}\n")
    return '\n'.join(rows)


def format_conflicts_cat(conflicts: list) -> str:
    if not conflicts:
        return "无分类冲突。\n"
    lines = ["\n--- 分类冲突_待确认 ---", f"共 {len(conflicts)} 组："]
    for a, b in conflicts:
        lines.append(f"  {a.spuid}({a.name_meaning.core},{a.category}) ↔ "
                     f"{b.spuid}({b.name_meaning.core},{b.category})")
    return '\n'.join(lines)


def format_conflicts_spec(conflicts: list) -> str:
    if not conflicts:
        return "无规格待确认。\n"
    lines = ["\n--- 规格待确认 ---", f"共 {len(conflicts)} 组："]
    for a, b in conflicts:
        lines.append(f"  {a.spuid} \"{a.name_meaning.core}\" desc=\"{a.desc_meaning.raw}\" ↔ "
                     f"{b.spuid} desc=\"{b.desc_meaning.raw}\"")
    return '\n'.join(lines)


def print_summary(summary: dict, conflicts_cat: list, conflicts_spec: list, total: int):
    print(format_summary(summary, total))
    print(format_conflicts_cat(conflicts_cat))
    print(format_conflicts_spec(conflicts_spec))
