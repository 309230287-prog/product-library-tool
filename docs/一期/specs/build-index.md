# 基准库索引构建

## 功能

读取一期结果表，用新翻译器重新翻译12440条，构建JSON索引。

## 输入

`商品库整理_结果.xlsx` Sheet(2)，列1-5（spuid/名称/单位/描述/分类），列11（命中次数）

## 输出

`index.json` — `{core_name: [IndexedRow, ...]}`，约10MB

## 流程

1. 读取Excel
2. 逐行翻译：translate_name + translate_desc + resolve_spec(has_processing=False)
3. 组装 IndexedRow
4. 按 core 分组
5. 转 dict → json.dump

## 注意

- 基准库无备注，has_processing 始终为 False
- 每条需 resolve_spec 统一 spec_core
- dataclass 需转 dict 再序列化
