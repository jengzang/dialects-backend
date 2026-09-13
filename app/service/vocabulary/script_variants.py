from functools import lru_cache

from opencc import OpenCC


_S2T = OpenCC("s2t.json")
_T2S = OpenCC("t2s.json")


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


@lru_cache(maxsize=None)
def standard_word_key(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return _T2S.convert(text)


@lru_cache(maxsize=4096)
def build_script_variants(value: str) -> tuple[str, ...]:
    """原样、全简、全繁三种写法。

    只做整词的简繁转换，不做逐字笛卡尔积：逐字组合会产生「头發」这类
    并不存在的写法，既白跑全表扫描又污染召回。
    """
    text = value.strip()
    if not text:
        return ()
    return tuple(_dedupe([text, _T2S.convert(text), _S2T.convert(text)]))
