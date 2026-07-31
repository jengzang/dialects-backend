import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkstemp
from typing import Iterable, Optional

import pandas as pd


@dataclass(frozen=True)
class ParsedVocabularyRow:
    standard_word: str
    local_expression: str
    ipa: str
    notes: str = ""


@dataclass(frozen=True)
class VocabularyParseResult:
    rows: list[ParsedVocabularyRow]
    errors: list[str]
    skipped_count: int
    parser_mode: str


_COLUMN_ALIASES = {
    "standard_word": {
        "standard_word",
        "written",
        "释义",
        "釋義",
        "书面",
        "書面",
        "书面词条",
        "書面詞條",
        "词条",
        "詞條",
        "meaning",
    },
    "local_expression": {
        "local_expression",
        "vocabulary",
        "当地讲法",
        "當地講法",
        "方言词",
        "方言詞",
        "方言讲法",
        "方言講法",
        "local",
    },
    "ipa": {
        "ipa",
        "IPA",
        "音标",
        "音標",
        "国际音标",
        "國際音標",
    },
    "notes": {
        "notes",
        "note",
        "注释",
        "註釋",
        "备注",
        "備註",
        "说明",
        "說明",
    },
}

_TABLE_SUFFIXES = {".xlsx", ".xls", ".csv", ".tsv"}
_DOC_SUFFIXES = {".docx", ".doc"}


def _normalize_header(value: object) -> str:
    return str(value).strip().replace(" ", "").replace("_", "").lower()


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _build_column_map(columns: Iterable[object]) -> dict[str, str]:
    normalized_to_original = {
        _normalize_header(column): str(column)
        for column in columns
    }

    column_map: dict[str, str] = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            original = normalized_to_original.get(_normalize_header(alias))
            if original is not None:
                column_map[field] = original
                break
    return column_map


def _validate_row(
    *,
    standard_word: str,
    local_expression: str,
    ipa: str,
    notes: str,
    row_number: int,
    fill_standard_from_local: bool = False,
) -> tuple[Optional[ParsedVocabularyRow], Optional[str], bool]:
    if fill_standard_from_local and not standard_word and local_expression:
        standard_word = local_expression

    if not standard_word and not local_expression:
        return None, None, True

    missing = []
    if not standard_word:
        missing.append("standard_word")
    if not ipa and not local_expression:
        missing.append("ipa 或 local_expression（至少需要一个非空）")
    if missing:
        return None, f"第 {row_number} 行缺少字段: {', '.join(missing)}", False

    return ParsedVocabularyRow(
        standard_word=standard_word,
        local_expression=local_expression,
        ipa=ipa,
        notes=notes,
    ), None, False


def parse_table_file(path: Path, fill_standard_from_local: bool = False) -> VocabularyParseResult:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    elif suffix == ".tsv":
        frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=str, keep_default_na=False)
    else:
        raise ValueError(f"Unsupported table file type: {suffix}")

    column_map = _build_column_map(frame.columns)
    required = set()
    if not fill_standard_from_local:
        required.add("standard_word")
    missing = sorted(required.difference(column_map))
    if "local_expression" not in column_map and "ipa" not in column_map:
        missing.append("local_expression 或 ipa（至少需要一个）")
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    rows: list[ParsedVocabularyRow] = []
    errors: list[str] = []
    skipped_count = 0
    for index, row in frame.iterrows():
        parsed, error, skipped = _validate_row(
            standard_word=_clean_cell(row.get(column_map.get("standard_word", ""))) if "standard_word" in column_map else "",
            local_expression=_clean_cell(row.get(column_map.get("local_expression", ""))) if "local_expression" in column_map else "",
            ipa=_clean_cell(row.get(column_map.get("ipa", ""))) if "ipa" in column_map else "",
            notes=_clean_cell(row.get(column_map.get("notes", ""))) if "notes" in column_map else "",
            row_number=int(index) + 2,
            fill_standard_from_local=fill_standard_from_local,
        )
        if skipped:
            skipped_count += 1
        elif error:
            errors.append(error)
        elif parsed is not None:
            rows.append(parsed)

    return VocabularyParseResult(
        rows=rows,
        errors=errors,
        skipped_count=skipped_count,
        parser_mode="table",
    )


_BRACKET_PATTERNS = {
    "ipa": re.compile(r"\[([^\]]*)\]"),
    "notes": re.compile(r"\{([^}]*)\}"),
    "local_expression": re.compile(r"(?:\(([^)]*)\)|（([^）]*)）)"),
}


def parse_bracket_document_text(text: str, fill_standard_from_local: bool = False) -> tuple[list[ParsedVocabularyRow], list[str]]:
    rows: list[ParsedVocabularyRow] = []
    errors: list[str] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        ipa_match = _BRACKET_PATTERNS["ipa"].search(line)
        notes_match = _BRACKET_PATTERNS["notes"].search(line)
        local_match = _BRACKET_PATTERNS["local_expression"].search(line)

        ipa = ipa_match.group(1).strip() if ipa_match else ""
        notes = notes_match.group(1).strip() if notes_match else ""
        local_expression = ""
        if local_match:
            local_expression = (local_match.group(1) or local_match.group(2) or "").strip()

        standard_word = line
        for pattern in _BRACKET_PATTERNS.values():
            standard_word = pattern.sub("", standard_word)
        standard_word = standard_word.strip()

        parsed, error, _ = _validate_row(
            standard_word=standard_word,
            local_expression=local_expression,
            ipa=ipa,
            notes=notes,
            row_number=line_number,
            fill_standard_from_local=fill_standard_from_local,
        )
        if error:
            errors.append(error)
        elif parsed is not None:
            rows.append(parsed)

    return rows, errors


def parse_whitespace_document_text(text: str, fill_standard_from_local: bool = False) -> tuple[list[ParsedVocabularyRow], list[str]]:
    rows: list[ParsedVocabularyRow] = []
    errors: list[str] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        parts = line.split(maxsplit=3)
        if fill_standard_from_local and len(parts) == 1:
            parsed, error, _ = _validate_row(
                standard_word="",
                local_expression=parts[0],
                ipa="",
                notes="",
                row_number=line_number,
                fill_standard_from_local=True,
            )
        elif len(parts) < 2:
            errors.append(f"第 {line_number} 行缺少字段: standard_word")
            continue
        else:
            parsed, error, _ = _validate_row(
                standard_word=parts[0],
                local_expression=parts[1] if len(parts) > 1 else "",
                ipa=parts[2] if len(parts) > 2 else "",
                notes=parts[3] if len(parts) > 3 else "",
                row_number=line_number,
                fill_standard_from_local=fill_standard_from_local,
            )
        if error:
            errors.append(error)
        elif parsed is not None:
            rows.append(parsed)

    return rows, errors


def _read_docx_text(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    return "\n\n".join(paragraph.text for paragraph in document.paragraphs)


def _decode_plain_text_bytes(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "big5"):
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            continue
        if text.strip():
            return text.replace("\x00", "")
    return ""


def _read_doc_text(path: Path) -> str:
    antiword = shutil.which("antiword")
    if antiword:
        result = subprocess.run(
            [antiword, str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

    textutil = shutil.which("textutil")
    if textutil:
        result = subprocess.run(
            [textutil, "-convert", "txt", "-stdout", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

    text = _decode_plain_text_bytes(path.read_bytes())
    if text.strip():
        return text

    raise ValueError(
        ".doc files require antiword or textutil on this server; "
        "please convert to .docx, csv, tsv, xls, or xlsx"
    )


def parse_document_file(path: Path, parser_mode: str, fill_standard_from_local: bool = False) -> VocabularyParseResult:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        text = _read_docx_text(path)
    elif suffix == ".doc":
        text = _read_doc_text(path)
    else:
        raise ValueError(f"Unsupported document file type: {suffix}")

    if parser_mode == "doc_bracket":
        rows, errors = parse_bracket_document_text(text, fill_standard_from_local=fill_standard_from_local)
    elif parser_mode == "doc_whitespace":
        rows, errors = parse_whitespace_document_text(text, fill_standard_from_local=fill_standard_from_local)
    else:
        bracket_rows, bracket_errors = parse_bracket_document_text(text, fill_standard_from_local=fill_standard_from_local)
        if bracket_rows and not bracket_errors:
            rows, errors = bracket_rows, bracket_errors
            parser_mode = "doc_bracket"
        else:
            rows, errors = parse_whitespace_document_text(text, fill_standard_from_local=fill_standard_from_local)
            parser_mode = "doc_whitespace"

    return VocabularyParseResult(
        rows=rows,
        errors=errors,
        skipped_count=0,
        parser_mode=parser_mode,
    )


def parse_vocabulary_file(path: Path | str, parser_mode: str = "auto", fill_standard_from_local: bool = False) -> VocabularyParseResult:
    file_path = Path(path)
    mode = parser_mode or "auto"
    if mode not in {"auto", "table", "doc_whitespace", "doc_bracket"}:
        raise ValueError(f"Unsupported parser_mode: {parser_mode}")

    suffix = file_path.suffix.lower()
    if mode == "table" or (mode == "auto" and suffix in _TABLE_SUFFIXES):
        return parse_table_file(file_path, fill_standard_from_local=fill_standard_from_local)
    if mode in {"doc_whitespace", "doc_bracket"} or (mode == "auto" and suffix in _DOC_SUFFIXES):
        return parse_document_file(file_path, mode, fill_standard_from_local=fill_standard_from_local)

    raise ValueError(f"Unsupported vocabulary file type: {suffix}")


def parse_uploaded_vocabulary_file(
    *,
    filename: str,
    content: bytes,
    parser_mode: str = "auto",
    fill_standard_from_local: bool = False,
) -> VocabularyParseResult:
    suffix = Path(filename).suffix.lower()
    fd, temp_name = mkstemp(suffix=suffix)
    temp_path = Path(temp_name)
    try:
        with open(fd, "wb", closefd=True) as tmp:
            tmp.write(content)
        return parse_vocabulary_file(temp_path, parser_mode=parser_mode, fill_standard_from_local=fill_standard_from_local)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
