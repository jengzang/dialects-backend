import re
import json
from contextlib import contextmanager
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import mkstemp, TemporaryFile
from typing import BinaryIO, Iterable, Optional

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
    error_groups: list[dict] = field(default_factory=list)


class _ErrorGroups:
    """Group validation failures while preserving indexes into legacy errors."""

    def __init__(self):
        self.groups: dict[tuple[str, ...], dict] = {}
        self.error_count = 0

    def add(self, fields: list[str], row_number: int):
        key = tuple(fields)
        if key not in self.groups:
            self.groups[key] = {"code": "missing_fields", "fields": fields,
                                "row_numbers": [], "error_indexes": []}
        self.groups[key]["row_numbers"].append(row_number)
        self.groups[key]["error_indexes"].append(self.error_count)
        self.error_count += 1


_COLUMN_ALIASES = {
    "standard_word": {
        "standard_word",
        "written",
        "释义",
        "釋義",
        "书面",
        "書面",
        "标准词",
        "標準詞",
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
        "详细释义",
        "詳細釋義",
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
    error_groups: _ErrorGroups | None = None,
) -> tuple[Optional[ParsedVocabularyRow], Optional[str], bool]:
    if fill_standard_from_local and not standard_word and local_expression:
        standard_word = local_expression

    if not standard_word and not local_expression and not ipa:
        return None, None, True

    missing = []
    if not standard_word:
        missing.append("standard_word")
    if not ipa and not local_expression:
        missing.append("ipa 或 local_expression（至少需要一个非空）")
    if missing:
        if error_groups is not None:
            fields = []
            if not standard_word:
                fields.append("standard_word")
            if not ipa and not local_expression:
                fields.append("local_expression_or_ipa")
            error_groups.add(fields, row_number)
        return None, f"第 {row_number} 行缺少字段: {', '.join(missing)}", False

    return ParsedVocabularyRow(
        standard_word=standard_word,
        local_expression=local_expression,
        ipa=ipa,
        notes=notes,
    ), None, False


TABLE_CHUNK_SIZE = 512


def _table_records(path: Path):
    """Yield a header followed by (spreadsheet row number, mapping) records."""
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        with pd.read_csv(path, sep="\t" if suffix == ".tsv" else ",",
                         dtype=str, keep_default_na=False,
                         chunksize=TABLE_CHUNK_SIZE) as reader:
            first = True
            for frame in reader:
                if first:
                    yield frame.columns
                    first = False
                for index, values in zip(frame.index, frame.itertuples(index=False, name=None)):
                    yield int(index) + 2, dict(zip(frame.columns, values))
        return
    if suffix == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.worksheets[0]
            sheet.reset_dimensions()
            records = sheet.iter_rows()

            def cell_value(cell):
                if cell.data_type == "e" or cell.value is None:
                    return ""
                value = cell.value
                if cell.data_type == "n" and isinstance(value, float) and value.is_integer():
                    return int(value)
                return value

            raw_headers = [cell_value(cell) for cell in next(records, ())]
            headers = []
            # Match pandas' duplicate-header suffixes; first alias remains authoritative.
            for index, value in enumerate(raw_headers):
                name = str(value) if value != "" else f"Unnamed: {index}"
                original = name
                duplicate = 0
                while name in headers:
                    duplicate += 1
                    name = f"{original}.{duplicate}"
                headers.append(name)
            yield headers
            pending_blank = 0
            for row_number, cells in enumerate(records, start=2):
                values = [cell_value(cell) for cell in cells]
                # Excel errors become blank during validation, but pandas treats
                # them as present when locating the final populated row.
                if not any(value != "" or cell.data_type == "e"
                           for cell, value in zip(cells, values)):
                    pending_blank += 1
                    continue
                # pandas ignores trailing empty spreadsheet rows, but counts interior ones.
                for blank_number in range(row_number - pending_blank, row_number):
                    yield blank_number, {}
                pending_blank = 0
                yield row_number, dict(zip(headers, values))
        finally:
            workbook.close()
        return
    if suffix == ".xls":
        # Legacy binary Excel still uses pandas/xlrd's workbook allocation.
        frame = pd.read_excel(path, dtype=str, keep_default_na=False)
        yield frame.columns
        for index, values in zip(frame.index, frame.itertuples(index=False, name=None)):
            yield int(index) + 2, dict(zip(frame.columns, values))
        return
    raise ValueError(f"Unsupported table file type: {suffix}")


def parse_table_file(path: Path, fill_standard_from_local: bool = False, *, _rows=None) -> VocabularyParseResult:
    records = _table_records(path)
    try:
        return _parse_table_records(records, fill_standard_from_local, _rows)
    finally:
        records.close()


def _parse_table_records(records, fill_standard_from_local, row_sink):
    column_map = _build_column_map(next(records, ()))
    required = set()
    if not fill_standard_from_local:
        required.add("standard_word")
    missing = sorted(required.difference(column_map))
    if "local_expression" not in column_map and "ipa" not in column_map:
        missing.append("local_expression 或 ipa（至少需要一个）")
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    rows = [] if row_sink is None else row_sink
    errors: list[str] = []
    skipped_count = 0
    error_groups = _ErrorGroups()
    for row_number, row in records:
        parsed, error, skipped = _validate_row(
            standard_word=_clean_cell(row.get(column_map.get("standard_word", ""))) if "standard_word" in column_map else "",
            local_expression=_clean_cell(row.get(column_map.get("local_expression", ""))) if "local_expression" in column_map else "",
            ipa=_clean_cell(row.get(column_map.get("ipa", ""))) if "ipa" in column_map else "",
            notes=_clean_cell(row.get(column_map.get("notes", ""))) if "notes" in column_map else "",
            row_number=row_number,
            fill_standard_from_local=fill_standard_from_local,
            error_groups=error_groups,
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
        error_groups=list(error_groups.groups.values()),
    )


_BRACKET_PATTERNS = {
    "ipa": re.compile(r"\[([^\]]*)\]"),
    "notes": re.compile(r"\{([^}]*)\}"),
    "local_expression": re.compile(r"(?:\(([^)]*)\)|（([^）]*)）)"),
}


def parse_bracket_document_text(text: str, fill_standard_from_local: bool = False, *, _error_groups: _ErrorGroups | None = None) -> tuple[list[ParsedVocabularyRow], list[str]]:
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
            error_groups=_error_groups,
        )
        if error:
            errors.append(error)
        elif parsed is not None:
            rows.append(parsed)

    return rows, errors


def parse_whitespace_document_text(text: str, fill_standard_from_local: bool = False, *, _error_groups: _ErrorGroups | None = None) -> tuple[list[ParsedVocabularyRow], list[str]]:
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
                error_groups=_error_groups,
            )
        elif len(parts) < 2:
            errors.append(f"第 {line_number} 行缺少字段: standard_word")
            if _error_groups is not None:
                _error_groups.add(["standard_word"], line_number)
            continue
        else:
            parsed, error, _ = _validate_row(
                standard_word=parts[0],
                local_expression=parts[1] if len(parts) > 1 else "",
                ipa=parts[2] if len(parts) > 2 else "",
                notes=parts[3] if len(parts) > 3 else "",
                row_number=line_number,
                fill_standard_from_local=fill_standard_from_local,
                error_groups=_error_groups,
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

    error_groups = _ErrorGroups()
    if parser_mode == "doc_bracket":
        rows, errors = parse_bracket_document_text(text, fill_standard_from_local=fill_standard_from_local, _error_groups=error_groups)
    elif parser_mode == "doc_whitespace":
        rows, errors = parse_whitespace_document_text(text, fill_standard_from_local=fill_standard_from_local, _error_groups=error_groups)
    else:
        bracket_rows, bracket_errors = parse_bracket_document_text(text, fill_standard_from_local=fill_standard_from_local, _error_groups=error_groups)
        if bracket_rows and not bracket_errors:
            rows, errors = bracket_rows, bracket_errors
            parser_mode = "doc_bracket"
        else:
            error_groups = _ErrorGroups()
            rows, errors = parse_whitespace_document_text(text, fill_standard_from_local=fill_standard_from_local, _error_groups=error_groups)
            parser_mode = "doc_whitespace"

    return VocabularyParseResult(
        rows=rows,
        errors=errors,
        skipped_count=0,
        parser_mode=parser_mode,
        error_groups=list(error_groups.groups.values()),
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
    content: bytes | BinaryIO,
    parser_mode: str = "auto",
    fill_standard_from_local: bool = False,
) -> VocabularyParseResult:
    suffix = Path(filename).suffix.lower()
    fd, temp_name = mkstemp(suffix=suffix)
    temp_path = Path(temp_name)
    try:
        with open(fd, "wb", closefd=True) as tmp:
            if isinstance(content, bytes):
                tmp.write(content)
            else:
                shutil.copyfileobj(content, tmp, length=1024 * 1024)
        return parse_vocabulary_file(temp_path, parser_mode=parser_mode, fill_standard_from_local=fill_standard_from_local)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


class _StagedRows:
    """Disk-backed, replayable rows; must stay inside the staging context."""
    def __init__(self):
        self._file = TemporaryFile(mode="w+t", encoding="utf-8")
        self._count = 0

    def append(self, row):
        self._file.write(json.dumps([row.standard_word, row.local_expression, row.ipa, row.notes],
                                    ensure_ascii=False) + "\n")
        self._count += 1

    def __len__(self):
        return self._count

    def __iter__(self):
        self._file.seek(0)
        for line in self._file:
            yield ParsedVocabularyRow(*json.loads(line))

    @property
    def closed(self):
        return self._file.closed

    def close(self):
        self._file.close()


@contextmanager
def staged_uploaded_vocabulary_file(
    *, filename: str, content: bytes | BinaryIO, parser_mode: str = "auto",
    fill_standard_from_local: bool = False,
):
    """Stage valid rows on disk; retain every error for the existing response contract.

    File-like input is read from its current position and remains caller-owned.
    XLS and document libraries retain their existing whole-document allocations.
    """
    suffix = Path(filename).suffix.lower()
    rows = _StagedRows()
    try:
        fd, temp_name = mkstemp(suffix=suffix)
        temp_path = Path(temp_name)
        try:
            with open(fd, "wb", closefd=True) as tmp:
                if isinstance(content, bytes):
                    tmp.write(content)
                else:
                    shutil.copyfileobj(content, tmp, length=1024 * 1024)
            mode = parser_mode or "auto"
            if mode == "table" or (mode == "auto" and suffix in _TABLE_SUFFIXES):
                result = parse_table_file(temp_path, fill_standard_from_local, _rows=rows)
            else:
                result = parse_vocabulary_file(temp_path, parser_mode, fill_standard_from_local)
                for row in result.rows:
                    rows.append(row)
            result = VocabularyParseResult(rows, result.errors, result.skipped_count, result.parser_mode, result.error_groups)
        finally:
            temp_path.unlink(missing_ok=True)
        yield result
    finally:
        rows.close()
