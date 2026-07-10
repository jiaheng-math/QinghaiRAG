from __future__ import annotations

import re
import unicodedata

REGION_ALIASES = {
    "青海": "青海省",
    "西宁": "西宁市",
    "海东": "海东市",
    "海北": "海北州",
    "海北藏族自治州": "海北州",
    "黄南": "黄南州",
    "黄南藏族自治州": "黄南州",
    "海南": "海南州",
    "海南藏族自治州": "海南州",
    "果洛": "果洛州",
    "果洛藏族自治州": "果洛州",
    "玉树": "玉树州",
    "玉树藏族自治州": "玉树州",
    "海西": "海西州",
    "海西蒙古族藏族自治州": "海西州",
}

ENTITY_ALIASES = {
    "酥油花": "塔尔寺酥油花",
    "堆绣": "湟中堆绣",
    "盘绣": "土族盘绣",
    "格萨尔": "格萨（斯）尔",
    "格萨（斯）尔": "格萨（斯）尔",
    "青海刺绣": "青绣",
}


def normalize_text_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", "", value)
    value = value.replace("()", "").replace("（）", "")
    return value.strip("，。；：、")


def normalize_region(value: str) -> str:
    key = normalize_text_key(value)
    return REGION_ALIASES.get(key, key)


def normalize_entity_name(value: str) -> str:
    key = normalize_text_key(value)
    return ENTITY_ALIASES.get(key, REGION_ALIASES.get(key, key))
