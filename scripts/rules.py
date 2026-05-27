"""
RuleEngine — 规则引擎
按优先级依次执行5级+待确认，一行一旦被标记就锁定。
"""
from collections import defaultdict
from translator import (
    SemanticTranslator, ProductRow,
    SYNONYM_MAP, is_status_redundant,
    UNIT_SYNONYMS, STATUS_WORDS,
)


CAT_QUESHENG = '缺省值'
CAT_WANQUAN = '完全重复'
CAT_CHAOMA = '抄码名重复'
CAT_YIMING = '异名同物'
CAT_NORMAL = '正常'


def _paren_compatible(a, b):
    """括号内容是否兼容 — 完全相同或差异仅由状态词造成"""
    pa = a.paren_content
    pb = b.paren_content
    if pa == pb:
        return True
    diff_words = set()
    if pa:
        diff_words.add(pa)
    if pb:
        diff_words.add(pb)
    return all(w in STATUS_WORDS for w in diff_words)


class RuleEngine:
    """规则引擎 — 逐级执行"""

    def __init__(self, rows: list[ProductRow], translator: SemanticTranslator):
        self.rows = rows
        self.tr = translator
        self.counts = {k: 0 for k in ['缺省值', '完全重复', '抄码名重复', '异名同物', '正常']}
        self.gid_counters = {k: 0 for k in ['缺省', '重', '抄', '异']}
        self.conflicts_cat = []
        self.conflicts_spec = []

    def _build_index(self):
        """构建索引 — 仅含未标记行，单位异名也建索引"""
        active = [r for r in self.rows if r.anomaly_class is None]
        self.idx_nu = defaultdict(list)        # (core, unit) → rows
        self.idx_by_name = defaultdict(list)   # core → rows (for yiming)
        for r in active:
            self.idx_nu[(r.name_meaning.core, r.unit)].append(r)
            self.idx_by_name[r.name_meaning.core].append(r)
            for syn_unit in UNIT_SYNONYMS.get(r.unit, []):
                self.idx_nu[(r.name_meaning.core, syn_unit)].append(r)

    def _mark(self, row, cat, gid, desc, sug) -> bool:
        """标记一行，返回True=成功标记，False=已被标记过"""
        if row.anomaly_class is not None:
            return False
        row.anomaly_class = cat
        row.group_id = gid
        row.group_desc = desc
        row.suggestion = sug
        return True

    def run_quesheng(self):
        for r in self.rows:
            if r.anomaly_class is not None:
                continue
            if '缺省值' in r.name_meaning.raw:
                self._mark(r, CAT_QUESHENG, '缺省',
                           '商品名称含"缺省值"，数据不完整',
                           '补全商品信息或停用该编码')
                self.counts['缺省值'] += 1
            elif r.desc_meaning.is_quesheng:
                self._mark(r, CAT_QUESHENG, '缺省',
                           '描述字段含"缺省值"，数据不完整',
                           '补全商品信息或停用该编码')
                self.counts['缺省值'] += 1

    def _status_compatible(self, a: ProductRow, b: ProductRow) -> bool:
        s1, s2 = a.name_meaning.has_status, b.name_meaning.has_status
        if s1 == s2:
            return True
        if s1 is None and s2 is not None:
            return is_status_redundant(s2, b.category)
        if s2 is None and s1 is not None:
            return is_status_redundant(s1, a.category)
        return False

    def run_wanquan(self):
        self._build_index()
        used_pairs = set()
        for (core, unit), candidates in self.idx_nu.items():
            if len(candidates) < 2:
                continue
            # 按分类分组
            cat_groups = defaultdict(list)
            for c in candidates:
                if c.anomaly_class is not None:
                    continue
                cat_groups[c.category].append(c)
            for cat, group in cat_groups.items():
                if len(group) < 2:
                    continue
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        a, b = group[i], group[j]
                        pair = tuple(sorted([a.spuid, b.spuid]))
                        if pair in used_pairs:
                            continue
                        if not self._status_compatible(a, b):
                            continue
                        # 品牌不同 → 不同商品
                        if a.name_meaning.brand and b.name_meaning.brand and a.name_meaning.brand != b.name_meaning.brand:
                            continue
                        # 一个有品牌一个没有 → 信息不对等，跳过
                        if bool(a.name_meaning.brand) != bool(b.name_meaning.brand):
                            continue
                        # 括号内容不同且非状态差异 → 不同商品
                        if not _paren_compatible(a.name_meaning, b.name_meaning):
                            continue
                        # 双方都有name_spec且不同 → 不同商品
                        if a.name_meaning.name_spec and b.name_meaning.name_spec \
                           and a.name_meaning.name_spec != b.name_meaning.name_spec:
                            continue
                        # 一方有抄码一方无 → 留给run_chaoma处理
                        if a.name_meaning.has_chaoma != b.name_meaning.has_chaoma:
                            continue
                        if not self.tr.descs_equivalent(a.desc_meaning, b.desc_meaning):
                            if a.desc_meaning.has_spec != b.desc_meaning.has_spec:
                                self.conflicts_spec.append((a, b))
                            continue
                        used_pairs.add(pair)
                        self.gid_counters['重'] += 1
                        gid = f"重{self.gid_counters['重']}"
                        if self._mark(a, CAT_WANQUAN, gid,
                                     f"与{b.spuid} 语义完全一致，重复编码",
                                     f"与{b.spuid} 名称单位分类相同，保留其一"):
                            self.counts['完全重复'] += 1
                        if self._mark(b, CAT_WANQUAN, gid,
                                     f"与{a.spuid} 语义完全一致，重复编码",
                                     f"与{a.spuid} 名称单位分类相同，保留其一"):
                            self.counts['完全重复'] += 1

    def run_chaoma(self):
        self._build_index()
        for r in self.rows:
            if r.anomaly_class is not None:
                continue
            if not r.name_meaning.has_chaoma:
                continue
            core = r.name_meaning.core
            unit = r.unit
            matches = self.idx_nu.get((core, unit), [])
            targets = [m for m in matches if m.spuid != r.spuid
                       and m.anomaly_class is None
                       and not m.name_meaning.has_chaoma
                       and self.tr.are_categories_compatible(r.category, m.category)
                       and self._status_compatible(r, m)]
            # 品牌+paren+name_spec+描述过滤
            targets = [t for t in targets
                       if _paren_compatible(r.name_meaning, t.name_meaning)
                       and (not r.name_meaning.brand and not t.name_meaning.brand
                            or r.name_meaning.brand == t.name_meaning.brand)
                       and not (r.name_meaning.name_spec and t.name_meaning.name_spec
                                and r.name_meaning.name_spec != t.name_meaning.name_spec)
                       and self.tr.descs_equivalent(r.desc_meaning, t.desc_meaning)]
            if not targets:
                continue
            same_cat = [t for t in targets if t.category == r.category]
            target = same_cat[0] if same_cat else targets[0]
            self.gid_counters['抄'] += 1
            gid = f"抄{self.gid_counters['抄']}"
            if self._mark(r, CAT_CHAOMA, gid,
                         f"抄码名版本，对应正常名编码: {target.spuid}",
                         f"停用抄码名编码，使用正常名编码 {target.spuid}"):
                self.counts['抄码名重复'] += 1
            if self._mark(target, CAT_CHAOMA, gid,
                         f"正常名版本，对应抄码名编码: {r.spuid}",
                         f"保留正常名编码，停用抄码名 {r.spuid}"):
                self.counts['抄码名重复'] += 1

    def run_post_chaoma_wanquan(self):
        """补漏：抄码→抄码内部完全重复（run_chaoma后没匹配到正常名的抄码名之间互标）"""
        self._build_index()
        used = set()
        for (core, unit), candidates in self.idx_nu.items():
            if len(candidates) < 2:
                continue
            chaoma_rows = [r for r in candidates if r.name_meaning.has_chaoma and r.anomaly_class is None]
            if len(chaoma_rows) < 2:
                continue
            # 同分类才能互标
            cat_groups = defaultdict(list)
            for r in chaoma_rows:
                cat_groups[r.category].append(r)
            for cat, group in cat_groups.items():
                if len(group) < 2:
                    continue
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        a, b = group[i], group[j]
                        pair = tuple(sorted([a.spuid, b.spuid]))
                        if pair in used:
                            continue
                        used.add(pair)
                        # 品牌不同 → 不同商品
                        if a.name_meaning.brand and b.name_meaning.brand and a.name_meaning.brand != b.name_meaning.brand:
                            continue
                        if bool(a.name_meaning.brand) != bool(b.name_meaning.brand):
                            continue
                        # 括号内容不同且非状态差异 → 不同商品
                        if not _paren_compatible(a.name_meaning, b.name_meaning):
                            continue
                        # 双方都有name_spec且不同 → 不同商品
                        if a.name_meaning.name_spec and b.name_meaning.name_spec \
                           and a.name_meaning.name_spec != b.name_meaning.name_spec:
                            continue
                        # 状态兼容性
                        if not self._status_compatible(a, b):
                            continue
                        # 描述等价
                        if not self.tr.descs_equivalent(a.desc_meaning, b.desc_meaning):
                            continue
                        self.gid_counters['重'] += 1
                        gid = f"重{self.gid_counters['重']}"
                        if self._mark(a, CAT_WANQUAN, gid,
                                     f"与{b.spuid} 语义完全一致(抄码互重)",
                                     f"与{b.spuid} 名称单位相同，抄码互重，保留其一"):
                            self.counts['完全重复'] += 1
                        if self._mark(b, CAT_WANQUAN, gid,
                                     f"与{a.spuid} 语义完全一致(抄码互重)",
                                     f"与{a.spuid} 名称单位相同，抄码互重，保留其一"):
                            self.counts['完全重复'] += 1

    def run_yiming(self):
        self._build_index()
        used = set()
        for std_name, syn_list in SYNONYM_MAP.items():
            rows_std = self.idx_by_name.get(std_name, [])
            rows_std = [r for r in rows_std if r.anomaly_class is None]
            if not rows_std:
                continue
            for syn in syn_list:
                rows_syn = self.idx_by_name.get(syn, [])
                rows_syn = [r for r in rows_syn if r.anomaly_class is None]
                if not rows_syn:
                    continue
                for ra in rows_std:
                    for rb in rows_syn:
                        pair = tuple(sorted([ra.spuid, rb.spuid]))
                        if pair in used:
                            continue
                        if ra.unit != rb.unit:
                            continue
                        if not self.tr.are_categories_compatible(ra.category, rb.category):
                            continue
                        if not self._status_compatible(ra, rb):
                            continue
                        if not _paren_compatible(ra.name_meaning, rb.name_meaning):
                            continue
                        if not self.tr.descs_equivalent(ra.desc_meaning, rb.desc_meaning):
                            continue
                        if ra.name_meaning.name_spec and rb.name_meaning.name_spec \
                           and ra.name_meaning.name_spec != rb.name_meaning.name_spec:
                            continue
                        used.add(pair)
                        self.gid_counters['异'] += 1
                        gid = f"异{self.gid_counters['异']}"
                        if self._mark(ra, CAT_YIMING, gid,
                                     f"同物异名: {ra.name_meaning.core} = {rb.name_meaning.core}",
                                     f"确定标准名称为\"{std_name}\""):
                            self.counts['异名同物'] += 1
                        if self._mark(rb, CAT_YIMING, gid,
                                     f"同物异名: {ra.name_meaning.core} = {rb.name_meaning.core}",
                                     f"确定标准名称为\"{std_name}\""):
                            self.counts['异名同物'] += 1

    def run_normal(self):
        for r in self.rows:
            if r.anomaly_class is None:
                r.anomaly_class = CAT_NORMAL
                self.counts['正常'] += 1

    def get_conflicts(self):
        active = [r for r in self.rows if r.anomaly_class in (None, CAT_NORMAL)]
        groups = defaultdict(list)
        for r in active:
            groups[(r.name_meaning.core, r.unit)].append(r)
        cat_conflicts = []
        for (core, unit), grp in groups.items():
            if len(grp) < 2:
                continue
            for i in range(len(grp)):
                for j in range(i + 1, len(grp)):
                    a, b = grp[i], grp[j]
                    if a.category == b.category:
                        continue
                    if self.tr.are_categories_compatible(a.category, b.category):
                        continue
                    cat_conflicts.append((a, b))
        return cat_conflicts, self.conflicts_spec

    def run_all(self):
        self.run_quesheng()
        # 抄码名重复在完全重复前: 抄码→正常先匹配, 剩下的正常→正常、抄码→抄码走完全重复
        self.run_chaoma()
        self.run_wanquan()
        self.run_post_chaoma_wanquan()  # 剩余抄码→抄码互重
        self.run_yiming()
        self.run_normal()
        self.conflicts_cat, _ = self.get_conflicts()

    def summary(self) -> dict:
        return {
            '总行数': len(self.rows),
            '缺省值': self.counts['缺省值'],
            '完全重复': (self.counts['完全重复'], self.gid_counters['重']),
            '抄码名重复': (self.counts['抄码名重复'], self.gid_counters['抄']),
            '异名同物': (self.counts['异名同物'], self.gid_counters['异']),
            '正常': self.counts['正常'],
            '分类冲突': len(self.conflicts_cat),
            '规格待确认': len(self.conflicts_spec),
        }
