from pathlib import Path

import pytest
from docx import Document

from app.service.vocabulary.location import normalize_location_payload
from app.service.vocabulary.parser import (
    ParsedVocabularyRow,
    parse_bracket_document_text,
    parse_vocabulary_file,
)


def test_parse_reference_xlsx_maps_written_to_standard_word() -> None:
    result = parse_vocabulary_file(Path("tests/息烽.xlsx"), parser_mode="table")

    assert result.parser_mode == "table"
    assert result.errors == []
    assert result.rows[0] == ParsedVocabularyRow(
        standard_word="哥",
        local_expression="哥",
        ipa="ko1",
        notes="",
    )
    assert len(result.rows) > 10


def test_parse_table_accepts_chinese_column_aliases(tmp_path: Path) -> None:
    csv_path = tmp_path / "vocabulary.csv"
    csv_path.write_text(
        "释义,当地讲法,音标,备注\n"
        "太阳,日头,ȵit2 tʰəu2,常用\n",
        encoding="utf-8",
    )

    result = parse_vocabulary_file(csv_path, parser_mode="table")

    assert result.errors == []
    assert result.rows == [
        ParsedVocabularyRow(
            standard_word="太阳",
            local_expression="日头",
            ipa="ȵit2 tʰəu2",
            notes="常用",
        )
    ]


@pytest.mark.parametrize(
    "header",
    [
        "标准词,方言词,音标,详细释义",
        "標準詞,方言詞,音標,詳細釋義",
    ],
)
def test_parse_table_accepts_requested_column_aliases(tmp_path: Path, header: str) -> None:
    csv_path = tmp_path / "vocabulary.csv"
    csv_path.write_text(
        f"{header}\n太阳,日头,ȵit2 tʰəu2,常用\n",
        encoding="utf-8",
    )

    result = parse_vocabulary_file(csv_path, parser_mode="table")

    assert result.errors == []
    assert result.rows == [
        ParsedVocabularyRow(
            standard_word="太阳",
            local_expression="日头",
            ipa="ȵit2 tʰəu2",
            notes="常用",
        )
    ]


@pytest.mark.parametrize(
    "row",
    [
        ",,[ȵit2]",  # 只有音标
        ",日头,",  # 只有方言词
    ],
)
def test_parse_table_reports_missing_standard_word_for_non_blank_rows(
    tmp_path: Path, row: str
) -> None:
    csv_path = tmp_path / "vocabulary.csv"
    csv_path.write_text(
        f"标准词,方言词,音标,备注\n{row}\n",
        encoding="utf-8",
    )

    result = parse_vocabulary_file(csv_path, parser_mode="table")

    assert result.rows == []
    assert result.skipped_count == 0
    assert len(result.errors) == 1
    assert "standard_word" in result.errors[0]


def test_parse_table_skips_only_fully_blank_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "vocabulary.csv"
    csv_path.write_text(
        "标准词,方言词,音标,备注\n"
        ",,,\n"
        "  ,  ,  ,  \n",
        encoding="utf-8",
    )

    result = parse_vocabulary_file(csv_path, parser_mode="table")

    assert result.rows == []
    assert result.errors == []
    assert result.skipped_count == 2


def test_parse_bracket_document_text_extracts_fields() -> None:
    rows, errors = parse_bracket_document_text(
        "太阳（日头）[ȵit2 tʰəu2]{常用}\n"
        "月亮（月光）[ŋye2 kuaŋ1]"
    )

    assert errors == []
    assert rows == [
        ParsedVocabularyRow(
            standard_word="太阳",
            local_expression="日头",
            ipa="ȵit2 tʰəu2",
            notes="常用",
        ),
        ParsedVocabularyRow(
            standard_word="月亮",
            local_expression="月光",
            ipa="ŋye2 kuaŋ1",
            notes="",
        ),
    ]


def test_parse_whitespace_document_text() -> None:
    from app.service.vocabulary.parser import parse_whitespace_document_text

    rows, errors = parse_whitespace_document_text(
        "太阳 日头 ȵit2tʰəu2 常用\n"
        "月亮 月光 ŋye2kuaŋ1"
    )

    assert errors == []
    assert rows == [
        ParsedVocabularyRow(
            standard_word="太阳",
            local_expression="日头",
            ipa="ȵit2tʰəu2",
            notes="常用",
        ),
        ParsedVocabularyRow(
            standard_word="月亮",
            local_expression="月光",
            ipa="ŋye2kuaŋ1",
            notes="",
        ),
    ]


def test_parse_doc_plain_text_fallback_for_bracket_mode(tmp_path: Path) -> None:
    doc_path = tmp_path / "vocabulary.doc"
    doc_path.write_text("太阳（日头）[ȵit2 tʰəu2]{常用}\n", encoding="utf-8")

    result = parse_vocabulary_file(doc_path, parser_mode="doc_bracket")

    assert result.errors == []
    assert result.rows == [
        ParsedVocabularyRow(
            standard_word="太阳",
            local_expression="日头",
            ipa="ȵit2 tʰəu2",
            notes="常用",
        )
    ]


def test_parse_docx_whitespace_treats_paragraphs_as_records(tmp_path: Path) -> None:
    docx_path = tmp_path / "vocabulary.docx"
    document = Document()
    document.add_paragraph("太阳 日头 ȵit2")
    document.add_paragraph("月亮 月光 ŋye2")
    document.save(docx_path)

    result = parse_vocabulary_file(docx_path, parser_mode="doc_whitespace")

    assert result.errors == []
    assert result.rows == [
        ParsedVocabularyRow(
            standard_word="太阳",
            local_expression="日头",
            ipa="ȵit2",
            notes="",
        ),
        ParsedVocabularyRow(
            standard_word="月亮",
            local_expression="月光",
            ipa="ŋye2",
            notes="",
        ),
    ]


def test_parse_docx_bracket_extracts_real_document_paragraphs(tmp_path: Path) -> None:
    docx_path = tmp_path / "vocabulary-bracket.docx"
    document = Document()
    document.add_paragraph("太阳（日头）[ȵit2 tʰəu2]{常用}")
    document.add_paragraph("月亮(月光)[ŋye2 kuaŋ1]")
    document.save(docx_path)

    result = parse_vocabulary_file(docx_path, parser_mode="doc_bracket")

    assert result.parser_mode == "doc_bracket"
    assert result.errors == []
    assert result.rows == [
        ParsedVocabularyRow(
            standard_word="太阳",
            local_expression="日头",
            ipa="ȵit2 tʰəu2",
            notes="常用",
        ),
        ParsedVocabularyRow(
            standard_word="月亮",
            local_expression="月光",
            ipa="ŋye2 kuaŋ1",
            notes="",
        ),
    ]


def test_parse_docx_auto_uses_bracket_mode_for_real_bracket_document(tmp_path: Path) -> None:
    docx_path = tmp_path / "vocabulary-auto-bracket.docx"
    document = Document()
    document.add_paragraph("风（风）[fuŋ1]{天气}")
    document.save(docx_path)

    result = parse_vocabulary_file(docx_path, parser_mode="auto")

    assert result.parser_mode == "doc_bracket"
    assert result.errors == []
    assert result.rows == [
        ParsedVocabularyRow(
            standard_word="风",
            local_expression="风",
            ipa="fuŋ1",
            notes="天气",
        )
    ]


def test_normalize_location_payload_accepts_chinese_aliases() -> None:
    normalized = normalize_location_payload(
        {
            "簡稱": "息烽",
            "經緯度": "106.73,27.10",
            "省": "贵州",
            "市": "贵阳",
            "縣": "息烽",
            "音典分區": "西南",
            "地圖集二分區": "黔中",
        }
    )

    assert normalized.location_name == "息烽"
    assert normalized.coordinates == "106.73,27.10"
    assert normalized.province == "贵州"
    assert normalized.city == "贵阳"
    assert normalized.county == "息烽"
    assert normalized.yindian_region == "西南"
    assert normalized.atlas_region == "黔中"


def test_normalize_location_payload_accepts_tone_values() -> None:
    normalized = normalize_location_payload(
        {
            "location_name": "息烽",
            "coordinates": "106.73,27.10",
            "t1": "55",
            "T2": "21",
            "t10": "3",
        }
    )

    assert normalized.t1 == "55"
    assert normalized.t2 == "21"
    assert normalized.t10 == "3"
    assert normalized.t3 == ""


def test_normalize_location_payload_accepts_source_description_and_other_aliases() -> None:
    normalized = normalize_location_payload(
        {
            "location_name": "息烽",
            "coordinates": "106.73,27.10",
            "词表来源": "田野调查",
            "说明": "老派材料",
            "其他": "待复核",
        }
    )

    assert normalized.vocabulary_source == "田野调查"
    assert normalized.description == "老派材料"
    assert normalized.other == "待复核"


def test_normalize_location_payload_requires_location_name_and_coordinates() -> None:
    with pytest.raises(ValueError, match="location_name"):
        normalize_location_payload({"coordinates": "106.73,27.10"})

    with pytest.raises(ValueError, match="coordinates"):
        normalize_location_payload({"location_name": "息烽"})


def test_staged_upload_streams_and_closes_rows():
    import io
    from app.service.vocabulary import parser

    class BoundedRead(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024
            return super().read(size)

    content = BoundedRead(('standard_word,local_expression,ipa\n' + ''.join(
        f'word{i},local{i},ipa\n' for i in range(1500)
    ) + ',local,\n,,\n').encode())
    with parser.staged_uploaded_vocabulary_file(filename='large.csv', content=content) as result:
        assert len(result.rows) == 1500
        assert list(result.rows)[-1].standard_word == 'word1499'
        assert len(result.errors) == 1
        assert '1502' in result.errors[0]
        assert result.skipped_count == 1
        assert list(result.rows)[0].standard_word == 'word0'
        staged_rows = result.rows
    assert staged_rows.closed
    assert not content.closed


def test_uploaded_parser_accepts_file_object():
    import io
    from app.service.vocabulary.parser import parse_uploaded_vocabulary_file
    result = parse_uploaded_vocabulary_file(filename='a.tsv', content=io.BytesIO(
        '标准词\t方言词\t音标\n太阳\t日头\tNA\n'.encode()))
    assert result.rows == [ParsedVocabularyRow('太阳', '日头', 'NA')]


def test_xlsx_stream_preserves_numeric_blank_and_duplicate_headers(tmp_path, monkeypatch):
    import pandas as pd
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['standard_word', 'local_expression', 'ipa', 'notes', 'notes'])
    sheet.append([123, True, 1.0, 'first', 'second'])
    sheet.append([None, None, None, None, None])
    sheet.append(['word', 'local', 'NA', None, None])
    sheet.cell(10, 1).number_format = '0'
    path = tmp_path / 'values.xlsx'
    workbook.save(path)
    monkeypatch.setattr(pd, 'read_excel', lambda *a, **k: pytest.fail('full Excel frame'))
    result = parse_vocabulary_file(path)
    assert result.rows == [ParsedVocabularyRow('123', 'True', '1', 'first'),
                           ParsedVocabularyRow('word', 'local', 'NA')]
    assert result.skipped_count == 1


@pytest.mark.parametrize('content', [b'wrong,header\na,b\n', b'standard_word,local_expression\na,b,c\nd,e,f,g\n'])
def test_staged_parser_closes_resources_on_parse_error(tmp_path, monkeypatch, content):
    from app.service.vocabulary import parser
    handles = []
    paths = []
    original_temp = parser.TemporaryFile
    original_mkstemp = parser.mkstemp
    def temporary(*args, **kwargs):
        handle = original_temp(*args, **kwargs)
        handles.append(handle)
        return handle
    def named(*args, **kwargs):
        fd, name = original_mkstemp(*args, dir=tmp_path, **kwargs)
        paths.append(Path(name))
        return fd, name
    monkeypatch.setattr(parser, 'TemporaryFile', temporary)
    monkeypatch.setattr(parser, 'mkstemp', named)
    with pytest.raises(ValueError):
        with parser.staged_uploaded_vocabulary_file(filename='broken.csv', content=content):
            pytest.fail('invalid input accepted')
    assert all(handle.closed for handle in handles)
    assert paths and not any(path.exists() for path in paths)


def test_xlsx_error_only_terminal_row_is_counted_as_skipped(tmp_path):
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['standard_word', 'local_expression', 'ipa'])
    sheet.append(['word', 'local', 'ipa'])
    sheet.append(['#DIV/0!', None, None])
    sheet.cell(8, 1).number_format = '0'
    path = tmp_path / 'error-row.xlsx'
    workbook.save(path)
    result = parse_vocabulary_file(path)
    assert result.rows == [ParsedVocabularyRow('word', 'local', 'ipa')]
    assert result.skipped_count == 1
    assert result.errors == []
