from functools import lru_cache

from opencc import OpenCC

from app.common.s2t import s2t_pro


MAX_SCRIPT_VARIANTS = 16

_S2T = OpenCC("s2t.json")
_T2S = OpenCC("t2s.json")


def _dedupe(values: list[str], *, limit: int = MAX_SCRIPT_VARIANTS) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


@lru_cache(maxsize=None)
def standard_word_key(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return _T2S.convert(text)


def _mapping_phrases(text: str, *, limit: int) -> list[str]:
    try:
        _, mapping = s2t_pro(text, level=2, keep_all_layers=True)
    except Exception:
        return []

    phrases = [""]
    for original_char, char_candidates in mapping:
        ordered_candidates = _dedupe(
            [original_char, *sorted(char_candidates)],
            limit=limit,
        )
        next_phrases = []
        for prefix in phrases:
            for candidate in ordered_candidates:
                next_phrases.append(prefix + candidate)
                if len(next_phrases) >= limit:
                    break
            if len(next_phrases) >= limit:
                break
        phrases = next_phrases
        if len(phrases) >= limit:
            break
    return phrases


@lru_cache(maxsize=4096)
def build_script_variants(value: str) -> tuple[str, ...]:
    text = value.strip()
    if not text:
        return ()

    candidates = [
        text,
        _T2S.convert(text),
        _S2T.convert(text),
        *_mapping_phrases(text, limit=MAX_SCRIPT_VARIANTS),
    ]
    return tuple(_dedupe(candidates))
