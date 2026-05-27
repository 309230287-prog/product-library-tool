"""
四维匹配引擎 — 新品翻译后比对基准库索引
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass, field
from typing import Optional
from translator import (
    SemanticTranslator, TranslatedItem, SpecResult,
    resolve_spec, has_processing_intent,
    SYNONYM_MAP, COMPATIBLE_CATEGORIES, is_status_redundant,
    units_equivalent, weights_equivalent,
)
from judge import judge


@dataclass
class IndexedRow:
    spuid: str; core: str; brand: Optional[str]
    spec_core: Optional[str]; has_processing: bool
    unit: str; raw_name: str; category: str
    has_chaoma: bool; has_status: Optional[str]
    spec_conflict: bool = False  # 名称和描述规格冲突
    hit_count: int = 0


@dataclass
class CandidateMatch:
    spuid: str; raw_name: str
    dim_name: bool; dim_brand: bool; dim_spec: bool; dim_unit: bool
    name_detail: str; spec_detail: str
    has_chaoma: bool = False; hit_count: int = 0; spec_core: Optional[str] = None


@dataclass
class MatchResult:
    result: str
    suggested_spuid: Optional[str] = None
    candidates: list = field(default_factory=list)
    detail: str = ''


def load_index(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    result = {}
    for core, rows in raw.items():
        fixed = []
        for r in rows:
            r.setdefault('hit_count', 0)
            r.setdefault('has_processing', False)
            r.setdefault('has_status', None)
            r.setdefault('brand', None)
            r.setdefault('spec_core', None)
            fixed.append(IndexedRow(**r))
        result[core] = fixed
    return result


def _is_synonym(a, b):
    return (a in SYNONYM_MAP and b in SYNONYM_MAP[a]) or (b in SYNONYM_MAP and a in SYNONYM_MAP[b])


def check_spec(new_spec: SpecResult, candidate: IndexedRow) -> tuple:
    nc = new_spec
    if nc.conflict:
        return False, f"规格冲突({nc.conflict_detail})"
    if not nc.spec_core and not candidate.spec_core and not nc.has_processing and not candidate.has_processing:
        return True, "均无规格"
    if nc.spec_core and candidate.spec_core:
        if nc.spec_core == candidate.spec_core or weights_equivalent(nc.spec_core, candidate.spec_core):
            if nc.has_processing == candidate.has_processing:
                return True, "规格一致"
            return False, "spec_processing_mismatch"
        return False, f"规格不同({nc.spec_core}!={candidate.spec_core})"
    # 一方有一方无
    return False, "spec_mismatch_unilateral"


def check_dimensions(new: TranslatedItem, new_spec: SpecResult,
                     new_remark: str, candidate: IndexedRow) -> CandidateMatch:
    # 维度1: 品名
    core_match = new.core == candidate.core
    name_detail = "exact" if core_match else "mismatch"
    if not core_match:
        if _is_synonym(new.core, candidate.core):
            core_match = True; name_detail = "synonym"
    if not core_match:
        shorter, longer = sorted([new.core, candidate.core], key=len)
        if shorter and shorter in longer and len(shorter) >= 2:
            if longer.startswith(shorter):
                diff = longer[len(shorter):]
            elif longer.endswith(shorter):
                diff = longer[:len(longer)-len(shorter)]
            else:
                diff = None
            if diff and diff in (new_remark or ''):
                core_match = True; name_detail = "substring"
    name_ok = core_match

    # 维度2: 品牌
    if new.brand == '__SKIP__':
        brand_ok = True  # 用户标注"无要求"
    elif new.brand:
        brand_ok = new.brand in candidate.raw_name  # 接龙表品牌→名称包含判断
    elif candidate.brand:
        brand_ok = candidate.brand in new.raw_name if hasattr(new, 'raw_name') else False
    else:
        brand_ok = True  # 双方都无品牌

    # 维度3: 规格
    spec_ok, spec_detail = check_spec(new_spec, candidate)

    # 维度4: 单位（含异名）
    unit_ok = units_equivalent(new.unit, candidate.unit)

    # 状态兼容：一方有状态一方无→检查是否冗余
    if name_ok and new.has_status != candidate.has_status:
        if new.has_status and candidate.has_status:
            name_ok = False  # 双方都有但不同→不兼容
        elif new.has_status and not candidate.has_status:
            if not is_status_redundant(new.has_status, new.category):
                name_ok = False
        elif candidate.has_status and not new.has_status:
            if not is_status_redundant(candidate.has_status, candidate.category):
                name_ok = False

    # 分类兼容：双方都是标准分类→查表；任一方非标→跳过
    all_cats = set(COMPATIBLE_CATEGORIES.keys()) | {v for vs in COMPATIBLE_CATEGORIES.values() for v in vs}
    if new.category and candidate.category \
       and new.category in all_cats and candidate.category in all_cats:
        cat_ok = new.category == candidate.category or \
                 candidate.category in COMPATIBLE_CATEGORIES.get(new.category, []) or \
                 new.category in COMPATIBLE_CATEGORIES.get(candidate.category, [])
        if not cat_ok:
            unit_ok = False

    return CandidateMatch(
        spuid=candidate.spuid, raw_name=candidate.raw_name,
        dim_name=name_ok, dim_brand=brand_ok, dim_spec=spec_ok, dim_unit=unit_ok,
        name_detail=name_detail, spec_detail=spec_detail,
        has_chaoma=candidate.has_chaoma, hit_count=candidate.hit_count,
        spec_core=candidate.spec_core)


def _pick_best(candidates):
    return max(candidates, key=lambda c: (not c.has_chaoma, c.hit_count, 1 if c.spec_core else 0))


def classify(new_item: TranslatedItem, candidates: list) -> MatchResult:
    if not candidates:
        return MatchResult("需新增", detail=f'品名"{new_item.core}"未在库中找到匹配')

    full = [c for c in candidates if c.dim_name and c.dim_brand and c.dim_spec and c.dim_unit]
    if full:
        best = _pick_best(full)
        return MatchResult("建议复用", best.spuid, candidates,
                          detail=f"四维全过；推荐{best.raw_name}({best.spuid},命中{best.hit_count}次)")

    sub = [c for c in candidates if c.name_detail == "substring" and c.dim_brand and c.dim_spec and c.dim_unit]
    if sub:
        best = _pick_best(sub)
        return MatchResult("待确认", best.spuid, candidates, detail=f"子串匹配，待人工确认")

    uni = [c for c in candidates if c.dim_name and c.dim_brand and c.dim_unit
           and c.spec_detail in ("spec_mismatch_unilateral", "spec_processing_mismatch")]
    if uni:
        has_proc_diff = any(c.spec_detail == "spec_processing_mismatch" for c in uni)
        has_unilateral = any(c.spec_detail == "spec_mismatch_unilateral" for c in uni)
        if has_proc_diff:
            detail = "加工意图不一致（基准库无加工信息），待人工确认"
        else:
            detail = "规格信息不对等（基准库无加工信息对比），待人工确认"
        return MatchResult("待确认", None, candidates, detail=detail)

    name_ok = [c for c in candidates if c.dim_name]
    if name_ok:
        reasons = set()
        for c in name_ok[:3]:
            if not c.dim_brand: reasons.add("品牌不同")
            if not c.dim_spec and c.spec_detail != "spec_mismatch_unilateral": reasons.add("规格不同")
            if not c.dim_unit: reasons.add("单位不同")
        return MatchResult("需新增", None, candidates, detail="; ".join(reasons))

    return MatchResult("需新增", detail=f'品名"{new_item.core}"未在库中找到匹配')


def check_one(translator: SemanticTranslator, name: str, brand: Optional[str],
              spec_desc: str, unit: str, category: str, remark: str,
              index: dict) -> MatchResult:
    # 翻译新品
    nm = translator.translate_name(name, category)
    dm = translator.translate_desc(spec_desc, unit)

    # 查候选
    candidates = list(index.get(nm.core, []))
    if nm.core in SYNONYM_MAP:
        for syn in SYNONYM_MAP[nm.core]:
            candidates.extend(index.get(syn, []))
    for core, rows in index.items():
        shorter, longer = sorted([nm.core, core], key=len)
        if shorter and len(shorter) >= 2 and shorter in longer:
            candidates.extend(rows)

    # 去重，保留最多10个候选
    seen = set()
    unique = []
    for c in candidates:
        if c.spuid not in seen:
            seen.add(c.spuid); unique.append(c)
    unique = unique[:10]

    # 格式化 → DeepSeek 判断
    new_dict = {
        "name": name, "brand": brand if brand != '__SKIP__' else "",
        "unit": unit, "spec": spec_desc, "category": category, "remark": remark,
    }
    cand_dicts = [{"spuid": c.spuid, "name": c.raw_name, "unit": c.unit,
                   "spec": c.spec_core or "", "category": c.category,
                   "brand": c.brand or ""} for c in unique]

    result = judge(new_dict, cand_dicts)
    return MatchResult(
        result=result["result"],
        suggested_spuid=result["suggested_spuid"],
        detail=result["detail"],
    )
