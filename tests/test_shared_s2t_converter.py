from concurrent.futures import ThreadPoolExecutor

import pytest

from app.common.s2t import opencc_s2t
from app.service.vocabulary import script_variants


def test_vocabulary_reuses_common_s2t_converter():
    # An extra native converter retains a second copy of the same dictionaries.
    assert script_variants._S2T is opencc_s2t


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('头发', ('头发', '頭髮')),
        ('儿童', ('儿童', '兒童')),
        ('  廣東话  ', ('廣東话', '广东话', '廣東話')),
        ('IPA 55', ('IPA 55',)),
        ('  ', ()),
    ],
)
def test_shared_converter_preserves_script_variants(text, expected):
    assert script_variants.build_script_variants(text) == expected


def test_common_and_vocabulary_conversion_can_run_concurrently():
    texts = ['头发', '儿童', '广东话', '臺灣', '繁簡转换', 'IPA55', '']
    expected = {text: opencc_s2t.convert(text) for text in texts}
    variants = {text: script_variants.build_script_variants(text) for text in texts}
    script_variants.build_script_variants.cache_clear()

    def convert(index):
        text = texts[index % len(texts)]
        assert opencc_s2t.convert(text) == expected[text]
        assert script_variants._S2T.convert(text) == expected[text]
        assert script_variants.build_script_variants(text) == variants[text]

    # Bounded stress test only; production gets no additional threads or tasks.
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(convert, range(1000)))
