"""
SemanticTranslator — 语义翻译器
输入原始行数据，输出标准化语义结构。

不是字符串处理器，是"这个东西是什么、怎么卖、什么规格"的翻译器。
"""
import re
from dataclasses import dataclass
from typing import Optional


# ============================================================
# 老编码后缀
# ============================================================
SUFFIX_PAT = re.compile(r'-[A-Z]{2,3}\d+[】\[]?')
TRAILING_JUNK = re.compile(r'[【】\[\]]+$')


# ============================================================
# 状态词
# ============================================================
STATUS_WORDS = {'杀好', '鲜', '活', '冻', '冻品', '冰鲜', '速冻', '散装', '散称'}


def _normalize_spec(raw: str) -> str:
    """规格标准化：×→*、去1*前缀"""
    s = raw.replace('×', '*').replace('x', '*').replace('X', '*')
    s = re.sub(r'^1\*', '', s).strip()
    return s


# 加工动作前缀——只检测动词，不硬编码结果词
PROC_PREFIXES = ['切', '去', '单冻', '速冻', '剁', '绞', '斩', '削', '剥', '刮']


def has_processing_intent(remark: str) -> bool:
    """不硬编码结果词（丝/块/丁…），只检测动词前缀"""
    if not remark:
        return False
    for prefix in PROC_PREFIXES:
        if prefix in remark:
            return True
    return False

PREFIX_STATUS = ['冰鲜', '速冻', '杀好', '散称', '散装', '冻', '活', '鲜', '干']


# ============================================================
# 品牌词
# ============================================================
BRAND_WORDS = [
    '安井', '三全', '思念', '海霸王', '正大', '双汇', '金锣',
    '湾仔码头', '广州酒家', '陶陶居', '百利', '百家鲜', '百小鲜', '安佳',
    '嘉得利', '海天', '李锦记', '太太乐', '家乐', '美极', '金富华',
    '禾源', '点深师', '艾守香', '酪宴', '凤球唛', '光明', '奔富',
    '澳皇', '圣迪乐山姆', '隆泰', '六和', '康源', '佳多兴', '昊明',
    '锦江山', '森煜', '圣农', '艺霖', '丰达农牧', '爱德生', '高盛',
    '宁鑫', '美洋洋', '伊比利亚', '孔师傅', '蜀厨', '鼎丰', '百钻',
    '顺香园', '榴芒一刻', '翠宏',
]
BRAND_PAT = re.compile('|'.join(re.escape(b) for b in sorted(BRAND_WORDS, key=len, reverse=True)))


# ============================================================
# 异名同物表
# ============================================================
SYNONYM_MAP = {
    '空心菜': ['通心菜', '通菜'],
    '通心菜': ['空心菜', '通菜'],
    '香菜': ['芫荽'],
    '芫荽': ['香菜'],
    '茼蒿': ['皇帝菜'],
    '皇帝菜': ['茼蒿'],
    '芥菜': ['潮州芥菜'],
    '潮州芥菜': ['芥菜'],
    '豆苗': ['豌豆苗'],
    '豌豆苗': ['豆苗'],
    '冰菜': ['冰草'],
    '冰草': ['冰菜'],
    '潺菜': ['木耳菜'],
    '木耳菜': ['潺菜'],
    '折耳根': ['鱼腥草'],
    '鱼腥草': ['折耳根'],
    '金不换': ['九层塔'],
    '九层塔': ['金不换'],
    '九芽生菜': ['黄九牙', '苦菊'],
    '黄九牙': ['九芽生菜', '苦菊'],
    '苦菊': ['九芽生菜', '黄九牙'],
    '番茄': ['西红柿'],
    '西红柿': ['番茄'],
    '土豆': ['薯仔', '马铃薯'],
    '薯仔': ['土豆', '马铃薯'],
    '马铃薯': ['土豆', '薯仔'],
    '包菜': ['平包菜', '椰菜', '球菜'],
    '平包菜': ['包菜', '椰菜', '球菜'],
    '椰菜': ['包菜', '平包菜', '球菜'],
    '球菜': ['包菜', '平包菜', '椰菜'],
    '菜花': ['椰菜花', '花菜'],
    '椰菜花': ['菜花', '花菜'],
    '花菜': ['菜花', '椰菜花'],
    '大白菜': ['黄心白菜', '毛菜'],
    '黄心白菜': ['大白菜', '毛菜'],
    '苦瓜': ['凉瓜'],
    '凉瓜': ['苦瓜'],
    '茄瓜': ['茄子'],
    '茄子': ['茄瓜'],
    '丝瓜': ['胜瓜'],
    '胜瓜': ['丝瓜'],
    '青圆椒': ['青灯笼椒'],
    '青灯笼椒': ['青圆椒'],
    '红圆椒': ['红灯笼椒'],
    '红灯笼椒': ['红圆椒'],
    '胡萝卜': ['红萝卜'],
    '红萝卜': ['胡萝卜'],
    '京葱': ['大葱'],
    '大葱': ['京葱'],
    '蒜苔': ['蒜苗', '蒜芯'],
    '蒜苗': ['蒜苔', '蒜芯'],
    '蒜芯': ['蒜苔', '蒜苗'],
    '独蒜': ['独头蒜'],
    '独头蒜': ['独蒜'],
    '红葱头': ['干葱头'],
    '干葱头': ['红葱头'],
    '草鱼': ['鲩鱼'],
    '鲩鱼': ['草鱼'],
    '大头鱼': ['花鲢鱼'],
    '花鲢鱼': ['大头鱼'],
    '罗非鱼': ['福寿鱼'],
    '福寿鱼': ['罗非鱼'],
    '生鱼': ['黑鱼'],
    '黑鱼': ['生鱼'],
    '翘嘴鱼': ['翘壳鱼'],
    '翘壳鱼': ['翘嘴鱼'],
    '鲟鱼': ['鲟龙鱼'],
    '鲟龙鱼': ['鲟鱼'],
    '黄骨鱼': ['黄辣丁'],
    '黄辣丁': ['黄骨鱼'],
    '加州鲈鱼': ['鲈鱼'],
    '鲮鱼': ['土鲮鱼'],
    '土鲮鱼': ['鲮鱼'],
    '马友鱼': ['午笋鱼'],
    '午笋鱼': ['马友鱼'],
    '鸦片鱼': ['比目鱼'],
    '比目鱼': ['鸦片鱼'],
    '多春鱼': ['毛鳞鱼'],
    '毛鳞鱼': ['多春鱼'],
    '马鲛鱼': ['鲅鱼'],
    '鲅鱼': ['马鲛鱼'],
    '罗氏虾': ['大头虾'],
    '大头虾': ['罗氏虾'],
    '皮皮虾': ['濑尿虾'],
    '濑尿虾': ['皮皮虾'],
    '芭乐': ['番石榴'],
    '番石榴': ['芭乐'],
    '香瓜': ['甜瓜'],
    '甜瓜': ['香瓜'],
    '白果': ['银杏'],
    '银杏': ['白果'],
    '金针菜': ['黄花菜'],
    '黄花菜': ['金针菜'],
    '冬菇': ['香菇'],
    '香菇': ['冬菇'],
    '沙姜': ['山奈'],
    '山奈': ['沙姜'],
    '薏米': ['薏苡仁'],
    '薏苡仁': ['薏米'],
    '腐竹': ['支竹'],
    '支竹': ['腐竹'],
    '萝卜干': ['菜脯'],
    '菜脯': ['萝卜干'],
    '皮蛋': ['松花蛋'],
    '松花蛋': ['皮蛋'],
    '白木耳': ['银耳'],
    '银耳': ['白木耳'],
    '荸荠': ['马蹄'],
    '马蹄': ['荸荠'],
    '乌鸡': ['竹丝鸡'],
    '竹丝鸡': ['乌鸡'],
    '青瓜': ['黄瓜'],
    '黄瓜': ['青瓜'],
    '荷兰豆': ['蜜豆'],
    '蜜豆': ['荷兰豆'],
    '莴笋': ['青笋'],
    '青笋': ['莴笋'],
    '春菜苗': ['春菜仔'],
    '春菜仔': ['春菜苗'],
    '芹菜': ['本地芹菜'],
    '本地芹菜': ['芹菜'],
    '青柠': ['西柠'],
    '西柠': ['青柠'],
    '发菜': ['头发菜'],
    '头发菜': ['发菜'],
    '鲤鱼': ['鲤子'],
    '鲤子': ['鲤鱼'],
}


# ============================================================
# 分类互通表
# ============================================================
COMPATIBLE_CATEGORIES = {
    '蔬菜类': ['蔬菜类（通用）'],
    '干调类': ['干调类（通用）'],
    '冻品类': ['冻品类（通用）'],
    '水产类': ['水产类（通用）', '水产品'],
    '鲜肉类': ['鲜肉类（通用）'],
    '禽蛋类': ['禽蛋类（通用）', '家禽类'],
    '酒水副食类': ['酒水副食类（通用）', '饮料副食类'],
    '粮油类': ['粮油类（通用）'],
    '豆制品类': ['豆制品类（通用）'],
    '水果类': ['水果类（通用）'],
    '烧卤味': ['卤烤熟食'],
}


# ============================================================
# 数据类型
# ============================================================
@dataclass
class NameMeaning:
    core: str
    brand: Optional[str] = None
    paren_content: Optional[str] = None  # 括号内原文，不猜测不丢弃
    name_spec: Optional[str] = None      # 名称中提取的规格（数字+单位）
    has_chaoma: bool = False
    has_status: Optional[str] = None
    status_from_prefix: bool = False
    status_from_paren: bool = False
    raw: str = ''


@dataclass
class DescMeaning:
    has_spec: bool = False
    spec_core: Optional[str] = None
    is_quesheng: bool = False
    is_pure_text: bool = False
    raw: str = ''


@dataclass
class ProductRow:
    spuid: str = ''
    name_meaning: Optional[NameMeaning] = None
    unit: str = ''
    desc_meaning: Optional[DescMeaning] = None
    category: str = ''
    group_id: Optional[str] = None
    group_desc: Optional[str] = None
    suggestion: Optional[str] = None
    anomaly_class: Optional[str] = None


@dataclass
class SpecResult:
    """三源规格汇总结果"""
    spec_core: Optional[str] = None
    has_processing: bool = False
    conflict: bool = False
    conflict_detail: str = ''


def resolve_spec(name_meaning: NameMeaning, desc_meaning: DescMeaning,
                 has_proc: bool = False) -> SpecResult:
    """三源规格汇总：name_spec + desc_spec + 加工意图"""
    ns = _normalize_spec(name_meaning.name_spec) if name_meaning.name_spec else None
    ds = desc_meaning.spec_core  # 已由 translate_desc 标准化
    if ns and ds and ns != ds:
        return SpecResult(spec_core=ds, has_processing=has_proc, conflict=True,
                          conflict_detail=f'名称{ns}≠描述{ds}')
    if ns:
        return SpecResult(spec_core=ns, has_processing=has_proc)
    if ds:
        return SpecResult(spec_core=ds, has_processing=has_proc)
    return SpecResult(spec_core=None, has_processing=has_proc)


@dataclass
class TranslatedItem:
    """新品翻译后的完整商品画像"""
    core: str
    brand: Optional[str] = None
    has_status: Optional[str] = None
    paren_content: Optional[str] = None
    unit: str = ''
    category: str = ''


# ============================================================
# 翻译器
# ============================================================
class SemanticTranslator:
    """语义翻译器 — 把原始字段翻译成有意义的结构"""

    @staticmethod
    def _clean_suffix(name: str) -> str:
        name = SUFFIX_PAT.sub('', name)
        name = TRAILING_JUNK.sub('', name)
        return name.strip()

    @staticmethod
    def _strip_brand(name: str) -> str:
        return BRAND_PAT.sub('', name).strip()

    @staticmethod
    def _extract_prefix_status(name: str) -> tuple[str, Optional[str]]:
        for sp in sorted(PREFIX_STATUS, key=len, reverse=True):
            if name.startswith(sp) and len(name) > len(sp):
                remainder = name[len(sp):].strip()
                if remainder:
                    return remainder, sp
        return name, None

    @staticmethod
    def _extract_name_spec(name: str) -> tuple[Optional[str], Optional[str]]:
        """从名称中提取规格，返回 (原始匹配, 标准化后)"""
        # 模式1: 复杂规格 1*4*2.5kg, 1*100*70g, 尾缀只允许字母(单位)
        m = re.search(r'\d+\.?\d*[*×xX]\d+\.?\d*[*×xX]?\d*\.?\d*[a-zA-Z]*', name)
        if m:
            raw = m.group(0)
            return raw, _normalize_spec(raw)
        # 模式2: 数量+包装单位 6瓶
        m = re.search(r'\d+\.?\d*[.*×xX\d]*[瓶包袋盒罐桶箱]', name)
        if m:
            raw = m.group(0)
            return raw, _normalize_spec(raw)
        # 模式3: 重量/容量 300g, 1.65L
        m = re.search(r'\d+\.?\d*\s*(g|kg|斤|ml|L|l|升|公斤|两)', name)
        if m:
            raw = m.group(0)
            return raw, _normalize_spec(raw)
        return None, None

    @staticmethod
    def _extract_paren(name: str) -> tuple[str, Optional[str]]:
        """提取括号内容原样返回，不判断是否为状态"""
        m = re.search(r'[（(]([^）)]*)[）)]', name)
        if not m:
            return name, None
        content = m.group(1)
        cleaned = name[:m.start()] + name[m.end():]
        return cleaned.strip(), content

    def translate_name(self, raw_name: str, category: str = '') -> NameMeaning:
        """翻译名称 → NameMeaning"""
        name = raw_name.strip()
        if not name:
            return NameMeaning(core='', raw=raw_name)

        has_chaoma = '抄码' in name
        statuses = []

        name = self._clean_suffix(name)

        if has_chaoma:
            name = name.replace('抄码', '').strip()

        name, prefix_status = self._extract_prefix_status(name)
        if prefix_status:
            statuses.append(prefix_status)

        # 提取名称中的规格（品牌提取前）
        name_spec_raw, name_spec = self._extract_name_spec(name)
        if name_spec_raw:
            name = name.replace(name_spec_raw, '', 1).strip()

        # 提取品牌（剥离前先记录）
        brand_match = BRAND_PAT.search(name)
        brand = brand_match.group(0) if brand_match else None
        name = self._strip_brand(name)

        name, paren_content = self._extract_paren(name)
        paren_status = None
        from_paren = False
        if paren_content and paren_content in STATUS_WORDS:
            paren_status = paren_content
            statuses.append(paren_content)
            from_paren = True

        core = re.sub(r'\s+', '', name).strip()
        if not core:
            core = name.strip()

        status = '+'.join(statuses) if statuses else None
        return NameMeaning(
            core=core,
            brand=brand,
            paren_content=paren_content,
            name_spec=name_spec,
            has_chaoma=has_chaoma,
            has_status=status,
            status_from_prefix=bool(prefix_status),
            status_from_paren=from_paren,
            raw=raw_name,
        )

    def translate_desc(self, raw_desc: str, unit: str = '') -> DescMeaning:
        """翻译描述 → DescMeaning"""
        desc = (raw_desc or '').strip()
        if not desc:
            return DescMeaning(raw=raw_desc)

        is_quesheng = '缺省值' in desc
        no_spec_words = {'', '抄码', '无', '散称', '散装'}

        if desc in no_spec_words:
            return DescMeaning(has_spec=False, is_quesheng=is_quesheng, raw=raw_desc)

        if unit and desc == unit:
            return DescMeaning(has_spec=False, is_quesheng=is_quesheng,
                               raw=raw_desc, is_pure_text=True)

        spec = desc
        spec = re.sub(r'[\[\]]', '', spec)
        spec = re.split(r'[，,；;]', spec)[0].strip()
        spec = spec.replace('×', '*').replace('x', '*').replace('X', '*')
        spec = re.sub(r'^1\*', '', spec).strip()
        spec = BRAND_PAT.sub('', spec).strip()

        is_text = not bool(re.search(r'\d', spec)) if spec else False

        return DescMeaning(
            has_spec=True, spec_core=spec,
            is_quesheng=is_quesheng, is_pure_text=is_text,
            raw=raw_desc,
        )

    @staticmethod
    def are_categories_compatible(a: str, b: str) -> bool:
        if a == b:
            return True
        return b in COMPATIBLE_CATEGORIES.get(a, []) or a in COMPATIBLE_CATEGORIES.get(b, [])

def is_status_redundant(status: Optional[str], category: str) -> bool:
    if not status:
        return False
    if status == '鲜' and category in ('鲜肉类', '鲜肉类（通用）'):
        return True
    if status == '干' and category in ('干调类', '干调类（通用）'):
        return True
    if status == '冰鲜' and category in ('水产类', '水产类（通用）', '水产品'):
        return True
    return False

    @staticmethod
    def descs_equivalent(a: DescMeaning, b: DescMeaning) -> bool:
        if not a.has_spec and not b.has_spec:
            return True
        if a.has_spec and b.has_spec and not a.is_pure_text and not b.is_pure_text:
            return a.spec_core == b.spec_core
        return False
