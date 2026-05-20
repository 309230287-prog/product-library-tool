# 四维匹配引擎

## 功能

核心新增模块。接收翻译后的新品，比对基准库索引，输出匹配结果。

## 数据结构

```python
@dataclass
class IndexedRow:
    spuid: str; core: str; brand: Optional[str]
    spec_core: Optional[str]; has_processing: bool
    unit: str; raw_name: str; category: str
    has_chaoma: bool; has_status: Optional[str]
    hit_count: int = 0

@dataclass
class CandidateMatch:
    spuid: str; raw_name: str
    dim_name: bool; dim_brand: bool; dim_spec: bool; dim_unit: bool
    name_detail: str   # exact/synonym/substring/status_conflict/paren_conflict/mismatch
    spec_detail: str
    has_chaoma: bool; hit_count: int; spec_core: Optional[str]

@dataclass
class MatchResult:
    result: str  # 建议复用/需新增/待确认
    suggested_spuid: Optional[str]
    candidates: list
    detail: str
```

## 核心流程

```
check_one(item, index) → MatchResult:
  1. translate_name + translate_desc + has_processing_intent
  2. resolve_spec
  3. 查 index: item.core → 候选
  4. 查异名: SYNONYM_MAP → 合并候选（始终执行）
  5. 子串预过滤: 扫描index找子串关系 → 合并候选（始终执行）
  6. 去重(按spuid)
  7. 对每个候选: check_dimensions
  8. classify → MatchResult
```

## 四维比对逻辑

- **维度1 (品名)**: core相同/异名/子串 + status兼容 + paren兼容
- **维度2 (品牌)**: 都无或相同 → 通过
- **维度3 (规格)**: spec_core相同 + has_processing一致 → 通过；单方有→待确认
- **维度4 (单位)**: 完全相同 → 通过

## 结果分类

- 四维全过 → 建议复用
- 子串+其他三维过 → 待确认
- 品名过+规格不对等 → 待确认
- 品名过+状态/品牌/规格/单位明确冲突 → 需新增
- 品名未匹配 → 需新增

## 最佳匹配

多候选时：无抄码 > hit_count高 > 有规格
