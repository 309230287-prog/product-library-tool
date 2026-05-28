# 翻译器改造

## 功能

在一期 translator.py 基础上新增：名称规格提取 + 加工意图检测。

一期已有：老编码后缀剥离、抄码标记、品牌提取、状态词检测、paren_content保留、描述翻译、异名表。

## NameMeaning 最终结构

```python
@dataclass
class NameMeaning:
    core: str
    brand: Optional[str] = None
    paren_content: Optional[str] = None
    name_spec: Optional[str] = None        # 新增
    has_chaoma: bool = False
    has_status: Optional[str] = None
    status_from_prefix: bool = False
    status_from_paren: bool = False
    raw: str = ''
```

## 名称规格提取

在品牌提取之前扫描名称，识别规格模式后剥离：

```
1. 复杂规格: \d+\.?\d*[*×xX]\d+\.?\d*[*×xX]?\d*\.?\d*[^\s]*
2. 数量+单位: \d+\.?\d*[^\s]*[瓶包袋盒罐桶箱]
3. 重量/容量: \d+\.?\d*\s*(g|kg|斤|ml|L|l|升|公斤|两)
```

提取后立即标准化（×→*、去1*前缀）。

## 提取优先级

```
1. 老编码后缀 → 2. 抄码标记 → 3. 规格(name) → 4. 品牌 → 5. 状态 → 6. core
```

## 加工意图检测

```python
PROC_PREFIXES = ['切', '去', '单冻', '速冻', '剁', '绞', '斩', '削', '剥', '刮']

def has_processing_intent(remark: str) -> bool:
    for prefix in PROC_PREFIXES:
        if prefix in remark:
            return True
    return False
```

不硬编码结果词（丝/块/丁…），只检测动词前缀。

## 三源规格汇总

```python
def resolve_spec(name_meaning, desc_meaning, has_processing: bool) -> SpecResult:
    # 1. 标准化 name_spec 和 desc_spec
    # 2. 都有且不同 → conflict=True, 取 desc_spec
    # 3. 只有一方有 → 使用该值
    # 4. 都没有 → None
```

## 输入/输出

- 输入：raw_name, raw_brand (新品取*品牌列), raw_spec (新品取*规格列), unit, category, remark
- 输出：TranslatedItem + SpecResult

## 单位异名表

```python
UNIT_SYNONYMS = {'箱': ['件'], '件': ['箱'], '包': ['袋'], '袋': ['包']}
```

比对时：单位相同或互为异名 → 通过。

## 度量衡转换

提取规格中的重量数值，统一转为克后比对。仅双方都是重量时才用数值比对，否则退化为字符串比对。

## 规格去尾标准化

在现有去头`1*`基础上新增：`*1`结尾剥离、`/单位`结尾剥离。`10kg*1`→`10kg`，`20斤/箱`→`20斤`。

## 品牌来源区分

- 新品：品牌直接从 `*品牌` 列取（`"无要求"` = None），不从名称提取
- 基准库：品牌由 translator 从名称提取（已有逻辑，build_index时调用 translate_name 获取）

## 三源规格来源

- 新品：`*规格`列 → desc_spec，`*名称`列 → name_spec，备注列 → 加工意图
- 基准库：描述字段 → desc_spec，名称字段 → name_spec，无备注 → 加工意图始终 False
