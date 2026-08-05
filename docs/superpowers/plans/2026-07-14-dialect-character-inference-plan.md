# Dialect Character Inference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fast, explainable dialect character-table inference API that fills missing `聲母`, `韻母`, and `調類` fields from a user-selected reference dialect table without using machine learning.

**Architecture:** Add a dedicated inference service that reads the selected reference dialect from `dialects_user.db` / `dialects_admin.db`, bridges input characters through `characters.db`, and independently infers initials, finals, and tone classes. The algorithm is deterministic: exact same-character lookup first, then same Middle Chinese bucket voting, then coarser statistical fallback with evidence and confidence metadata.

**Tech Stack:** FastAPI, Pydantic v2, SQLite via the existing `get_db_pool`, existing `get_dialects_db` / `get_query_db` dependency selection, Python `unittest` / `pytest`.

---

## Key Constraints

- Do not use machine learning. The API must respond quickly and be explainable.
- Do not infer tone values. Only infer:
  - `聲母`
  - `韻母`
  - `調類`, represented internally and in existing data as `聲調`
- Do not infer full syllables.
- Do not use nearby-dialect migration automatically. The caller must explicitly pass `reference_location`.
- Infer the three components independently. A confident initial must not force a final or tone.
- Preserve user-provided values by default.
- Return candidates, confidence, method, bucket, evidence characters, and review status.
- Treat Middle Chinese multi-position characters as ambiguous evidence, not as single-ground-truth rows.

## Current Data and Code Facts

- Runtime dialect reading data is selected through `app/sql/db_selector.py`.
- Dialect tables live at constants in `app/common/path.py`:
  - `DIALECTS_DB_USER`
  - `DIALECTS_DB_ADMIN`
  - `CHARACTERS_DB_PATH`
- The `dialects` table contains `簡稱`, `漢字`, `音節`, `聲母`, `韻母`, `聲調`, `註釋`, `多音字`.
- `characters.db.characters` contains the Middle Chinese bridge fields: `攝`, `呼`, `等`, `韻`, `入`, `調`, `清濁`, `系`, `組`, `母`, `部位`, `方式`, `多地位標記`.
- Existing join patterns are in `app/service/core/matrix.py`, especially `build_phonology_classification_matrix` and `_query_pho_pie_rows`.
- Existing core routes are registered in `app/routes/__init__.py`.

## File Structure

- Create: `app/schemas/core/inference.py`
  - Pydantic request/response models for preview inference.
- Modify: `app/schemas/__init__.py`
  - Export the new schema classes for route imports.
- Create: `app/service/core/dialect_character_inference.py`
  - All inference logic, SQL loading, bucket construction, scoring, and response assembly.
- Create: `app/routes/core/inference.py`
  - `POST /api/dialect-character-inference/preview`.
- Modify: `app/routes/__init__.py`
  - Register the new route under `/api`.
- Create: `tests/test_dialect_character_inference.py`
  - Service-level and route-level tests using temporary SQLite databases.
- Optional Modify: `README.md`
  - Add a short API note after implementation is complete.

---

### Task 1: Add Request and Response Schemas

**Files:**
- Create: `app/schemas/core/inference.py`
- Modify: `app/schemas/__init__.py`
- Test: `tests/test_dialect_character_inference.py`

- [ ] **Step 1: Write failing schema tests**

Create `tests/test_dialect_character_inference.py` with these initial tests:

```python
import unittest

from pydantic import ValidationError

from app.schemas.core.inference import DialectCharacterInferenceRequest


class DialectCharacterInferenceSchemaTests(unittest.TestCase):
    def test_request_accepts_minimal_preview_payload(self) -> None:
        payload = DialectCharacterInferenceRequest(
            reference_location="廣州",
            items=[
                {"char": "學"},
                {"char": "東", "initial": "t", "final": None, "tone_class": None},
            ],
        )

        self.assertEqual(payload.reference_location, "廣州")
        self.assertEqual(payload.table_name, "characters")
        self.assertTrue(payload.options.preserve_user_values)
        self.assertEqual(payload.items[0].char, "學")

    def test_request_rejects_empty_reference_location(self) -> None:
        with self.assertRaises(ValidationError):
            DialectCharacterInferenceRequest(
                reference_location="",
                items=[{"char": "學"}],
            )

    def test_request_rejects_empty_items(self) -> None:
        with self.assertRaises(ValidationError):
            DialectCharacterInferenceRequest(
                reference_location="廣州",
                items=[],
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: FAIL with an import error for `app.schemas.core.inference`.

- [ ] **Step 3: Add schema implementation**

Create `app/schemas/core/inference.py`:

```python
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


InferenceFeature = Literal["initial", "final", "tone_class"]


class DialectCharacterInferenceItem(BaseModel):
    char: str = Field(..., min_length=1, max_length=1)
    initial: Optional[str] = None
    final: Optional[str] = None
    tone_class: Optional[str] = None


class DialectCharacterInferenceOptions(BaseModel):
    preserve_user_values: bool = True
    max_candidates: int = Field(default=3, ge=1, le=10)
    min_evidence_count: int = Field(default=3, ge=1, le=100)
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    include_existing_reference_reading: bool = True


class DialectCharacterInferenceRequest(BaseModel):
    reference_location: str = Field(..., min_length=1)
    table_name: str = "characters"
    items: List[DialectCharacterInferenceItem] = Field(..., min_length=1, max_length=5000)
    options: DialectCharacterInferenceOptions = Field(default_factory=DialectCharacterInferenceOptions)

    @field_validator("reference_location")
    @classmethod
    def normalize_reference_location(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("reference_location cannot be empty")
        return text

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        from app.common.constants import VALID_CHARACTER_TABLES

        if value not in VALID_CHARACTER_TABLES:
            raise ValueError(f"Invalid table_name: {value}. Must be one of {VALID_CHARACTER_TABLES}")
        return value


class InferenceCandidate(BaseModel):
    value: str
    score: float
    count: int
    evidence_chars: List[str] = Field(default_factory=list)


class InferenceDecision(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0
    method: Literal["preserved", "exact_char", "middle_chinese_bucket", "fallback_bucket", "unresolved"]
    bucket: Dict[str, Any] = Field(default_factory=dict)
    evidence_chars: List[str] = Field(default_factory=list)
    alternatives: List[InferenceCandidate] = Field(default_factory=list)
    needs_review: bool = False
    reason: Optional[str] = None


class DialectCharacterInferenceResultItem(BaseModel):
    char: str
    input: Dict[str, Optional[str]]
    inferred: Dict[InferenceFeature, InferenceDecision]
    middle_chinese_positions: List[Dict[str, Any]] = Field(default_factory=list)
    reference_readings: List[Dict[str, Optional[str]]] = Field(default_factory=list)
    status: Literal["complete", "partial", "needs_review", "unresolved"]


class DialectCharacterInferenceSummary(BaseModel):
    total: int
    filled_initial: int
    filled_final: int
    filled_tone_class: int
    needs_review: int
    unresolved: int


class DialectCharacterInferenceResponse(BaseModel):
    reference_location: str
    table_name: str
    summary: DialectCharacterInferenceSummary
    items: List[DialectCharacterInferenceResultItem]
```

Modify `app/schemas/__init__.py` to export:

```python
from .core.inference import (
    DialectCharacterInferenceRequest,
    DialectCharacterInferenceResponse,
)
```

Also add both names to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/core/inference.py app/schemas/__init__.py tests/test_dialect_character_inference.py
git commit -m "test: add dialect character inference schemas"
```

---

### Task 2: Implement Exact Same-Character Inference

**Files:**
- Create: `app/service/core/dialect_character_inference.py`
- Test: `tests/test_dialect_character_inference.py`

- [ ] **Step 1: Add failing service test for exact reference lookup**

Append to `tests/test_dialect_character_inference.py`:

```python
import sqlite3
import tempfile
from pathlib import Path

from app.schemas.core.inference import DialectCharacterInferenceRequest
from app.service.core.dialect_character_inference import infer_dialect_character_table


class DialectCharacterInferenceServiceTests(unittest.TestCase):
    def _create_dialect_db(self, tmpdir: str) -> str:
        db_path = Path(tmpdir) / "dialects.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE dialects (
                    簡稱 TEXT,
                    漢字 TEXT,
                    音節 TEXT,
                    聲母 TEXT,
                    韻母 TEXT,
                    聲調 TEXT,
                    註釋 TEXT,
                    多音字 TEXT
                )
                """
            )
            conn.executemany(
                "INSERT INTO dialects VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("參考點", "東", "tuŋ1", "t", "uŋ", "陰平", "", ""),
                    ("參考點", "學", "hɔk8", "h", "ɔk", "陽入", "", ""),
                ],
            )
        return str(db_path)

    def _create_characters_db(self, tmpdir: str) -> str:
        db_path = Path(tmpdir) / "characters.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE characters (
                    攝 TEXT,
                    呼 TEXT,
                    等 TEXT,
                    韻 TEXT,
                    入 TEXT,
                    調 TEXT,
                    清濁 TEXT,
                    系 TEXT,
                    組 TEXT,
                    母 TEXT,
                    部位 TEXT,
                    方式 TEXT,
                    漢字 TEXT,
                    釋義 TEXT,
                    多聲母 TEXT,
                    多等 TEXT,
                    多韻 TEXT,
                    多調 TEXT,
                    多地位標記 TEXT
                )
                """
            )
            conn.executemany(
                "INSERT INTO characters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("通", "開", "一", "東", "舒", "平", "全清", "端", "端", "端", "齒", "塞", "東", "", "", "", "", "", ""),
                    ("江", "開", "二", "覺", "入", "入", "全濁", "見", "見", "匣", "喉", "擦", "學", "", "", "", "", "", ""),
                ],
            )
        return str(db_path)

    def test_exact_same_character_fills_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dialect_db = self._create_dialect_db(tmpdir)
            characters_db = self._create_characters_db(tmpdir)
            request = DialectCharacterInferenceRequest(
                reference_location="參考點",
                items=[{"char": "學"}],
            )

            result = infer_dialect_character_table(
                request,
                dialect_db_path=dialect_db,
                character_db_path=characters_db,
            )

        item = result.items[0]
        self.assertEqual(item.inferred["initial"].value, "h")
        self.assertEqual(item.inferred["final"].value, "ɔk")
        self.assertEqual(item.inferred["tone_class"].value, "陽入")
        self.assertEqual(item.inferred["initial"].method, "exact_char")
        self.assertEqual(item.status, "complete")

    def test_preserves_user_provided_values_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dialect_db = self._create_dialect_db(tmpdir)
            characters_db = self._create_characters_db(tmpdir)
            request = DialectCharacterInferenceRequest(
                reference_location="參考點",
                items=[{"char": "學", "initial": "x"}],
            )

            result = infer_dialect_character_table(
                request,
                dialect_db_path=dialect_db,
                character_db_path=characters_db,
            )

        self.assertEqual(result.items[0].inferred["initial"].value, "x")
        self.assertEqual(result.items[0].inferred["initial"].method, "preserved")
        self.assertEqual(result.items[0].inferred["final"].value, "ɔk")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: FAIL with import error for `app.service.core.dialect_character_inference`.

- [ ] **Step 3: Add minimal exact lookup implementation**

Create `app/service/core/dialect_character_inference.py`:

```python
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from app.common.path import CHARACTERS_DB_PATH
from app.schemas.core.inference import (
    DialectCharacterInferenceRequest,
    DialectCharacterInferenceResponse,
    DialectCharacterInferenceResultItem,
    DialectCharacterInferenceSummary,
    InferenceDecision,
)
from app.sql.db_pool import get_db_pool


FEATURE_TO_COLUMN = {
    "initial": "聲母",
    "final": "韻母",
    "tone_class": "聲調",
}

INPUT_FEATURES = ("initial", "final", "tone_class")
MC_COLUMNS = ["攝", "呼", "等", "韻", "入", "調", "清濁", "系", "組", "母", "部位", "方式", "多地位標記"]


def _unique_chars(items) -> List[str]:
    seen = set()
    chars = []
    for item in items:
        if item.char not in seen:
            seen.add(item.char)
            chars.append(item.char)
    return chars


def _load_reference_readings(dialect_db_path: str, reference_location: str, chars: Iterable[str]) -> Dict[str, List[Dict[str, Optional[str]]]]:
    char_list = list(chars)
    if not char_list:
        return {}

    pool = get_db_pool(dialect_db_path)
    placeholders = ",".join("?" for _ in char_list)
    query = f"""
        SELECT 漢字, 音節, 聲母, 韻母, 聲調, 註釋, 多音字
        FROM dialects
        WHERE 簡稱 = ?
          AND 漢字 IN ({placeholders})
    """
    grouped: Dict[str, List[Dict[str, Optional[str]]]] = defaultdict(list)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, [reference_location] + char_list)
        for row in cursor.fetchall():
            grouped[row["漢字"]].append(
                {
                    "syllable": row["音節"],
                    "initial": row["聲母"],
                    "final": row["韻母"],
                    "tone_class": row["聲調"],
                    "note": row["註釋"],
                    "read_mark": row["多音字"],
                }
            )
    return dict(grouped)


def _load_middle_chinese_positions(character_db_path: str, chars: Iterable[str], table_name: str) -> Dict[str, List[Dict[str, Any]]]:
    char_list = list(chars)
    if not char_list:
        return {}

    from app.common.constants import get_table_schema

    schema = get_table_schema(table_name)
    char_col = schema["char_column"]
    hierarchy = schema["hierarchy"]
    select_cols = [char_col] + [col for col in MC_COLUMNS if col in hierarchy or col == schema.get("multi_status_column")]
    if schema.get("has_multi_status") and schema.get("multi_status_column") not in select_cols:
        select_cols.append(schema.get("multi_status_column"))

    pool = get_db_pool(character_db_path)
    placeholders = ",".join("?" for _ in char_list)
    query = f"""
        SELECT {", ".join(select_cols)}
        FROM {table_name}
        WHERE {char_col} IN ({placeholders})
    """
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, char_list)
        for row in cursor.fetchall():
            char = row[char_col]
            grouped[char].append({key: row[key] for key in row.keys() if key != char_col})
    return dict(grouped)


def _decision_from_user(value: Optional[str]) -> InferenceDecision:
    return InferenceDecision(
        value=value,
        confidence=1.0,
        method="preserved",
        needs_review=False,
        reason="user_provided",
    )


def _decision_from_exact(feature: str, readings: List[Dict[str, Optional[str]]], max_candidates: int) -> InferenceDecision:
    counts: Dict[str, int] = defaultdict(int)
    for reading in readings:
        value = reading.get(feature)
        if value:
            counts[value] += 1
    if not counts:
        return InferenceDecision(method="unresolved", reason="reference_char_has_no_feature_value", needs_review=True)

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    winner, count = ranked[0]
    total = sum(counts.values())
    confidence = count / total if total else 0.0
    return InferenceDecision(
        value=winner,
        confidence=round(confidence, 4),
        method="exact_char",
        evidence_chars=[],
        alternatives=[
            {"value": value, "score": round(n / total, 4), "count": n, "evidence_chars": []}
            for value, n in ranked[1:max_candidates]
        ],
        needs_review=len(ranked) > 1,
        reason="same_character_in_reference",
    )


def _unresolved(reason: str) -> InferenceDecision:
    return InferenceDecision(method="unresolved", needs_review=True, reason=reason)


def _item_status(decisions: Dict[str, InferenceDecision]) -> str:
    unresolved = [decision for decision in decisions.values() if decision.method == "unresolved"]
    needs_review = [decision for decision in decisions.values() if decision.needs_review]
    if len(unresolved) == len(decisions):
        return "unresolved"
    if unresolved:
        return "partial"
    if needs_review:
        return "needs_review"
    return "complete"


def _build_summary(items: List[DialectCharacterInferenceResultItem]) -> DialectCharacterInferenceSummary:
    return DialectCharacterInferenceSummary(
        total=len(items),
        filled_initial=sum(1 for item in items if item.inferred["initial"].value),
        filled_final=sum(1 for item in items if item.inferred["final"].value),
        filled_tone_class=sum(1 for item in items if item.inferred["tone_class"].value),
        needs_review=sum(1 for item in items if item.status == "needs_review"),
        unresolved=sum(1 for item in items if item.status == "unresolved"),
    )


def infer_dialect_character_table(
    request: DialectCharacterInferenceRequest,
    *,
    dialect_db_path: str,
    character_db_path: str = CHARACTERS_DB_PATH,
) -> DialectCharacterInferenceResponse:
    chars = _unique_chars(request.items)
    reference_by_char = _load_reference_readings(dialect_db_path, request.reference_location, chars)
    mc_by_char = _load_middle_chinese_positions(character_db_path, chars, request.table_name)

    result_items: List[DialectCharacterInferenceResultItem] = []
    for item in request.items:
        readings = reference_by_char.get(item.char, [])
        decisions: Dict[str, InferenceDecision] = {}
        input_values = {
            "initial": item.initial,
            "final": item.final,
            "tone_class": item.tone_class,
        }

        for feature in INPUT_FEATURES:
            user_value = input_values[feature]
            if user_value and request.options.preserve_user_values:
                decisions[feature] = _decision_from_user(user_value)
            elif readings:
                decisions[feature] = _decision_from_exact(
                    feature,
                    readings,
                    request.options.max_candidates,
                )
            else:
                decisions[feature] = _unresolved("no_same_character_reference_reading")

        result_items.append(
            DialectCharacterInferenceResultItem(
                char=item.char,
                input=input_values,
                inferred=decisions,
                middle_chinese_positions=mc_by_char.get(item.char, []),
                reference_readings=readings if request.options.include_existing_reference_reading else [],
                status=_item_status(decisions),
            )
        )

    return DialectCharacterInferenceResponse(
        reference_location=request.reference_location,
        table_name=request.table_name,
        summary=_build_summary(result_items),
        items=result_items,
    )
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/service/core/dialect_character_inference.py tests/test_dialect_character_inference.py
git commit -m "feat: add exact dialect character inference"
```

---

### Task 3: Add Middle Chinese Bucket Voting

**Files:**
- Modify: `app/service/core/dialect_character_inference.py`
- Test: `tests/test_dialect_character_inference.py`

- [ ] **Step 1: Add failing tests for bucket inference**

Append to the service test class:

```python
    def test_middle_chinese_bucket_fills_when_same_character_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dialect_db = self._create_dialect_db(tmpdir)
            characters_db = self._create_characters_db(tmpdir)
            with sqlite3.connect(dialect_db) as conn:
                conn.executemany(
                    "INSERT INTO dialects VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        ("參考點", "合", "hap8", "h", "ap", "陽入", "", ""),
                        ("參考點", "盒", "hap8", "h", "ap", "陽入", "", ""),
                        ("參考點", "核", "hat8", "h", "at", "陽入", "", ""),
                    ],
                )
            with sqlite3.connect(characters_db) as conn:
                conn.executemany(
                    "INSERT INTO characters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        ("咸", "開", "一", "合", "入", "入", "全濁", "見", "見", "匣", "喉", "擦", "合", "", "", "", "", "", ""),
                        ("咸", "開", "一", "合", "入", "入", "全濁", "見", "見", "匣", "喉", "擦", "盒", "", "", "", "", "", ""),
                        ("咸", "開", "一", "合", "入", "入", "全濁", "見", "見", "匣", "喉", "擦", "核", "", "", "", "", "", ""),
                        ("咸", "開", "一", "合", "入", "入", "全濁", "見", "見", "匣", "喉", "擦", "洽", "", "", "", "", "", ""),
                    ],
                )
            request = DialectCharacterInferenceRequest(
                reference_location="參考點",
                items=[{"char": "洽"}],
            )

            result = infer_dialect_character_table(
                request,
                dialect_db_path=dialect_db,
                character_db_path=characters_db,
            )

        item = result.items[0]
        self.assertEqual(item.inferred["initial"].value, "h")
        self.assertEqual(item.inferred["initial"].method, "middle_chinese_bucket")
        self.assertIn("合", item.inferred["initial"].evidence_chars)
        self.assertEqual(item.inferred["tone_class"].value, "陽入")

    def test_bucket_inference_marks_low_evidence_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dialect_db = self._create_dialect_db(tmpdir)
            characters_db = self._create_characters_db(tmpdir)
            with sqlite3.connect(characters_db) as conn:
                conn.execute(
                    "INSERT INTO characters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("江", "開", "二", "覺", "入", "入", "全濁", "見", "見", "匣", "喉", "擦", "覺", "", "", "", "", "", ""),
                )
            request = DialectCharacterInferenceRequest(
                reference_location="參考點",
                items=[{"char": "覺"}],
            )

            result = infer_dialect_character_table(
                request,
                dialect_db_path=dialect_db,
                character_db_path=characters_db,
            )

        self.assertTrue(result.items[0].inferred["initial"].needs_review)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: FAIL because unresolved missing characters are not bucket-inferred.

- [ ] **Step 3: Implement reference inventory and bucket scoring**

Modify `app/service/core/dialect_character_inference.py` with these helpers:

```python
FEATURE_BUCKETS = {
    "initial": [
        ["母", "清濁"],
        ["母"],
        ["組"],
    ],
    "final": [
        ["攝", "韻", "等", "呼", "入"],
        ["攝", "韻", "入"],
        ["攝", "韻"],
        ["攝"],
    ],
    "tone_class": [
        ["清濁", "調", "入"],
        ["清濁", "調"],
        ["調", "入"],
        ["調"],
    ],
}


def _bucket_key(position: Dict[str, Any], fields: List[str]) -> Optional[tuple]:
    values = []
    for field in fields:
        value = position.get(field)
        if value is None or value == "":
            return None
        values.append(value)
    return tuple(values)


def _load_reference_inventory(
    dialect_db_path: str,
    character_db_path: str,
    reference_location: str,
    table_name: str,
) -> List[Dict[str, Any]]:
    from app.common.constants import get_table_schema

    schema = get_table_schema(table_name)
    char_col = schema["char_column"]
    select_cols = [char_col] + [col for col in MC_COLUMNS if col in schema["hierarchy"] or col == schema.get("multi_status_column")]
    if schema.get("has_multi_status") and schema.get("multi_status_column") not in select_cols:
        select_cols.append(schema.get("multi_status_column"))

    pool = get_db_pool(dialect_db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"ATTACH DATABASE '{character_db_path}' AS chars_db")
        query = f"""
            SELECT
                d.漢字,
                d.聲母,
                d.韻母,
                d.聲調,
                c.{", c.".join(select_cols[1:])}
            FROM dialects d
            INNER JOIN chars_db.{table_name} c ON d.漢字 = c.{char_col}
            WHERE d.簡稱 = ?
              AND d.漢字 IS NOT NULL
              AND d.聲母 IS NOT NULL
              AND d.韻母 IS NOT NULL
              AND d.聲調 IS NOT NULL
        """
        cursor.execute(query, [reference_location])
        rows = []
        for row in cursor.fetchall():
            rows.append({key: row[key] for key in row.keys()})
        cursor.execute("DETACH DATABASE chars_db")
    return rows


def _build_bucket_index(reference_rows: List[Dict[str, Any]]) -> Dict[str, Dict[tuple, List[Dict[str, Any]]]]:
    index: Dict[str, Dict[tuple, List[Dict[str, Any]]]] = {
        "initial": defaultdict(list),
        "final": defaultdict(list),
        "tone_class": defaultdict(list),
    }
    for row in reference_rows:
        for feature, bucket_levels in FEATURE_BUCKETS.items():
            for fields in bucket_levels:
                key = (tuple(fields), _bucket_key(row, fields))
                if key[1] is not None:
                    index[feature][key].append(row)
    return index


def _decision_from_bucket(
    feature: str,
    positions: List[Dict[str, Any]],
    bucket_index: Dict[str, Dict[tuple, List[Dict[str, Any]]]],
    *,
    max_candidates: int,
    min_evidence_count: int,
    confidence_threshold: float,
) -> InferenceDecision:
    target_column = FEATURE_TO_COLUMN[feature]
    for fields in FEATURE_BUCKETS[feature]:
        aggregate: Dict[str, set] = defaultdict(set)
        bucket_value = None
        for position in positions:
            key_value = _bucket_key(position, fields)
            if key_value is None:
                continue
            bucket_value = key_value
            for row in bucket_index[feature].get((tuple(fields), key_value), []):
                value = row.get(target_column)
                char = row.get("漢字")
                if value and char:
                    aggregate[value].add(char)

        if not aggregate:
            continue

        ranked = sorted(aggregate.items(), key=lambda item: (-len(item[1]), item[0]))
        total = sum(len(chars) for chars in aggregate.values())
        winner, evidence = ranked[0]
        confidence = len(evidence) / total if total else 0.0
        evidence_count = len(evidence)
        method = "middle_chinese_bucket" if fields == FEATURE_BUCKETS[feature][0] else "fallback_bucket"
        return InferenceDecision(
            value=winner,
            confidence=round(confidence, 4),
            method=method,
            bucket={field: value for field, value in zip(fields, bucket_value or [])},
            evidence_chars=sorted(evidence),
            alternatives=[
                {
                    "value": value,
                    "score": round(len(chars) / total, 4),
                    "count": len(chars),
                    "evidence_chars": sorted(chars),
                }
                for value, chars in ranked[1:max_candidates]
            ],
            needs_review=evidence_count < min_evidence_count or confidence < confidence_threshold or len(ranked) > 1,
            reason="middle_chinese_bucket_vote",
        )

    return _unresolved("no_middle_chinese_bucket_evidence")
```

Then update `infer_dialect_character_table`:

```python
    reference_inventory = _load_reference_inventory(
        dialect_db_path,
        character_db_path,
        request.reference_location,
        request.table_name,
    )
    bucket_index = _build_bucket_index(reference_inventory)
```

And replace the missing-character unresolved branch with:

```python
            else:
                decisions[feature] = _decision_from_bucket(
                    feature,
                    mc_by_char.get(item.char, []),
                    bucket_index,
                    max_candidates=request.options.max_candidates,
                    min_evidence_count=request.options.min_evidence_count,
                    confidence_threshold=request.options.confidence_threshold,
                )
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/service/core/dialect_character_inference.py tests/test_dialect_character_inference.py
git commit -m "feat: add middle chinese bucket inference"
```

---

### Task 4: Add the FastAPI Preview Endpoint

**Files:**
- Create: `app/routes/core/inference.py`
- Modify: `app/routes/__init__.py`
- Test: `tests/test_dialect_character_inference.py`

- [ ] **Step 1: Add failing route test**

Append:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.core.inference import router as inference_router


class DialectCharacterInferenceRouteTests(unittest.TestCase):
    def test_preview_route_returns_service_response(self) -> None:
        app = FastAPI()
        app.include_router(inference_router, prefix="/api")

        def fake_dialects_db():
            return "unused-dialects.db"

        app.dependency_overrides = {}

        with patch(
            "app.routes.core.inference.infer_dialect_character_table",
        ) as mock_service:
            mock_service.return_value = {
                "reference_location": "參考點",
                "table_name": "characters",
                "summary": {
                    "total": 1,
                    "filled_initial": 1,
                    "filled_final": 1,
                    "filled_tone_class": 1,
                    "needs_review": 0,
                    "unresolved": 0,
                },
                "items": [],
            }
            response = TestClient(app).post(
                "/api/dialect-character-inference/preview",
                json={"reference_location": "參考點", "items": [{"char": "學"}]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["total"], 1)
        self.assertTrue(mock_service.called)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: FAIL with import error for route module.

- [ ] **Step 3: Add route implementation**

Create `app/routes/core/inference.py`:

```python
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.core.inference import (
    DialectCharacterInferenceRequest,
    DialectCharacterInferenceResponse,
)
from app.service.core.dialect_character_inference import infer_dialect_character_table
from app.sql.db_selector import get_dialects_db

router = APIRouter()


@router.post(
    "/dialect-character-inference/preview",
    response_model=DialectCharacterInferenceResponse,
)
async def preview_dialect_character_inference(
    payload: DialectCharacterInferenceRequest,
    dialects_db: str = Depends(get_dialects_db),
):
    try:
        return await asyncio.to_thread(
            infer_dialect_character_table,
            payload,
            dialect_db_path=dialects_db,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(exc)}")
```

Modify `app/routes/__init__.py`:

```python
from app.routes.core.inference import router as inference_router
```

Inside `setup_main_routes`:

```python
    app.include_router(inference_router, prefix="/api", tags=["query"], dependencies=[Depends(ApiLimiter)])
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/core/inference.py app/routes/__init__.py tests/test_dialect_character_inference.py
git commit -m "feat: add dialect character inference preview api"
```

---

### Task 5: Add Validation and Performance Guards

**Files:**
- Modify: `app/service/core/dialect_character_inference.py`
- Modify: `app/schemas/core/inference.py`
- Test: `tests/test_dialect_character_inference.py`

- [ ] **Step 1: Add failing tests for missing reference and large payload guard**

Append:

```python
    def test_missing_reference_location_data_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dialect_db = self._create_dialect_db(tmpdir)
            characters_db = self._create_characters_db(tmpdir)
            request = DialectCharacterInferenceRequest(
                reference_location="不存在",
                items=[{"char": "學"}],
            )

            with self.assertRaises(ValueError):
                infer_dialect_character_table(
                    request,
                    dialect_db_path=dialect_db,
                    character_db_path=characters_db,
                )

    def test_request_caps_items_at_5000(self) -> None:
        with self.assertRaises(ValidationError):
            DialectCharacterInferenceRequest(
                reference_location="參考點",
                items=[{"char": "學"} for _ in range(5001)],
            )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: FAIL because missing reference currently returns unresolved instead of a 400-worthy error.

- [ ] **Step 3: Add reference existence validation**

Add to `app/service/core/dialect_character_inference.py`:

```python
def _reference_location_exists(dialect_db_path: str, reference_location: str) -> bool:
    pool = get_db_pool(dialect_db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM dialects WHERE 簡稱 = ? LIMIT 1",
            [reference_location],
        )
        return cursor.fetchone() is not None
```

At the start of `infer_dialect_character_table`:

```python
    if not _reference_location_exists(dialect_db_path, request.reference_location):
        raise ValueError(f"Reference location has no dialect data: {request.reference_location}")
```

Confirm `items` already has `max_length=5000` in the schema from Task 1.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/service/core/dialect_character_inference.py app/schemas/core/inference.py tests/test_dialect_character_inference.py
git commit -m "feat: add inference validation guards"
```

---

### Task 6: Document the API

**Files:**
- Modify: `README.md`
- Optional Create: `docs/api/dialect-character-inference.md`

- [ ] **Step 1: Add API documentation**

Add this section to `README.md` near the core query APIs:

```markdown
### 方言字表推导

`POST /api/dialect-character-inference/preview` fills missing `聲母`, `韻母`, and `調類` values for a submitted character table using one explicitly selected reference dialect. It does not infer tone values and does not infer full syllables.

The algorithm is deterministic and explainable:

1. Preserve user-provided fields by default.
2. Use the same character in the selected reference dialect when available.
3. Use Middle Chinese bucket voting through `characters.db`.
4. Fall back to coarser buckets only when stricter buckets have no evidence.

Request:

```json
{
  "reference_location": "廣州",
  "table_name": "characters",
  "items": [
    {"char": "學", "initial": null, "final": null, "tone_class": null}
  ],
  "options": {
    "preserve_user_values": true,
    "max_candidates": 3,
    "min_evidence_count": 3,
    "confidence_threshold": 0.75
  }
}
```

Response items include one independent decision each for `initial`, `final`, and `tone_class`, with `method`, `confidence`, `bucket`, `evidence_chars`, `alternatives`, and `needs_review`.
```
```

- [ ] **Step 2: Run documentation sanity check**

Run:

```bash
rg -n "dialect-character-inference|方言字表推导" README.md docs
```

Expected: At least the new README section appears.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document dialect character inference api"
```

---

### Task 7: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run targeted test suite**

Run:

```bash
pytest tests/test_dialect_character_inference.py -q
```

Expected: PASS.

- [ ] **Step 2: Run related phonology tests**

Run:

```bash
pytest tests/test_phonology_multitable_support.py tests/test_search_custom_routes.py -q
```

Expected: PASS.

- [ ] **Step 3: Compile touched Python files**

Run:

```bash
python -m py_compile app/schemas/core/inference.py app/service/core/dialect_character_inference.py app/routes/core/inference.py app/routes/__init__.py app/schemas/__init__.py
```

Expected: no output and exit code 0.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git diff -- app/schemas/core/inference.py app/schemas/__init__.py app/service/core/dialect_character_inference.py app/routes/core/inference.py app/routes/__init__.py tests/test_dialect_character_inference.py README.md
```

Expected: only inference-related changes.

- [ ] **Step 5: Commit final fixes if needed**

If final verification required changes:

```bash
git add app/schemas/core/inference.py app/schemas/__init__.py app/service/core/dialect_character_inference.py app/routes/core/inference.py app/routes/__init__.py tests/test_dialect_character_inference.py README.md
git commit -m "fix: polish dialect character inference"
```

If no changes remain, skip this commit.

---

## Self-Review

- Spec coverage:
  - Explicit reference dialect only: covered by `reference_location`.
  - No machine learning: architecture and algorithm are deterministic SQL/statistics.
  - No tone value inference: only `tone_class` maps to existing `聲調`.
  - Independent initial/final/tone inference: `INPUT_FEATURES` loop and `FEATURE_BUCKETS`.
  - Middle Chinese bridge: uses `characters.db` and bucket fields.
  - Fast response: synchronous preview endpoint with 5000-item request cap and set-based SQL.
  - Explainability: response contains method, bucket, evidence, alternatives, confidence, review status.
- Placeholder scan: no `TBD`, no `TODO`, no vague "handle later" instructions.
- Type consistency:
  - Request model uses `tone_class`; database column mapping uses `聲調`.
  - Service response uses `DialectCharacterInferenceResponse`.
  - Route path is consistently `/api/dialect-character-inference/preview`.

## Implementation Notes

- The bucket implementation in Task 3 intentionally indexes all configured bucket levels for the selected reference location. This is faster than repeated SQL per input character.
- Multi-position characters are naturally represented as multiple `positions`; the algorithm aggregates across positions and marks weak/competing evidence with `needs_review`.
- If production evidence shows payloads larger than 5000 are common, add an async task/export workflow later. Do not add it in the first implementation.
