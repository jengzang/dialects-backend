# Wenbai Feature Stats And Phonology Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backward-compatible wenbai read statistics to `feature_stats` and `phonology_matrix` without breaking existing response fields.

**Architecture:** Extend the existing aggregation passes instead of redesigning response shapes. `feature_stats` gets inline `read_stats` per feature bucket, while `phonology_matrix` keeps `matrix` unchanged and adds a parallel `matrix_read_stats` tree built from a separate fine-grained query.

**Tech Stack:** FastAPI, Python, SQLite, existing service-layer aggregation helpers, pytest

---

### Task 1: Add failing tests for `feature_stats` read stats

**Files:**
- Modify: `tests/test_phonology_multitable_support.py`
- Modify: `app/service/core/feature_stats.py`

- [ ] **Step 1: Locate the closest existing test pattern**

Run: `rg -n "feature_stats|phonology_matrix" tests app/service/core`
Expected: existing test modules or nearby service tests to extend

- [ ] **Step 2: Write a failing test for `read_stats` shape**

Add a test that prepares rows covering marks `1`, `2`, `3`, and mixed `2+3` in the same bucket, then asserts a payload like:

```python
assert result["data"]["測試點"]["聲母"]["k"]["read_stats"] == {
    "polyphonic": {"count": 3, "char_indices": [0, 1, 2]},
    "wendu": {"count": 2, "char_indices": [1, 2]},
    "baidu": {"count": 2, "char_indices": [1, 3]},
    "wenbai": {"count": 1, "char_indices": [1]},
}
```

- [ ] **Step 3: Run the focused test to verify it fails**

Run: `pytest tests/test_phonology_multitable_support.py -k feature_stats -v`
Expected: FAIL because `read_stats` is missing

- [ ] **Step 4: Commit the failing test**

```bash
git add tests/test_phonology_multitable_support.py
git commit -m "test: cover feature_stats wenbai read stats"
```

### Task 2: Implement `feature_stats.read_stats`

**Files:**
- Modify: `app/service/core/feature_stats.py`
- Test: `tests/test_phonology_multitable_support.py`

- [ ] **Step 1: Add local helpers for mark classification**

Implement private helpers near the top of the file:

```python
def _mark_to_text(value) -> str:
    return "" if value is None else str(value).strip()


def _is_polyphonic_mark(value) -> bool:
    return _mark_to_text(value) in {"1", "2", "3"}


def _is_wendu_mark(value) -> bool:
    return _mark_to_text(value) == "2"


def _is_baidu_mark(value) -> bool:
    return _mark_to_text(value) == "3"
```

- [ ] **Step 2: Extend the main query to include `多音字`**

Change the per-feature query from:

```python
SELECT 簡稱, '{feature}' as feature_type, {feature} as value, 漢字
```

to:

```python
SELECT 簡稱, '{feature}' as feature_type, {feature} as value, 漢字, 多音字
```

- [ ] **Step 3: Add a read-stat aggregation structure**

Create an adjacent structure:

```python
read_grouped = defaultdict(
    lambda: defaultdict(
        lambda: defaultdict(
            lambda: {
                "polyphonic": set(),
                "wendu": set(),
                "baidu": set(),
                "_marks_by_char": defaultdict(set),
            }
        )
    )
)
```

- [ ] **Step 4: Populate mark groups during row scan**

Inside the `for row in all_rows:` loop, update both the existing char grouping and the new mark grouping:

```python
mark = row[4]

if _is_polyphonic_mark(mark):
    read_grouped[location][feature_type][value]["polyphonic"].add(char)
    read_grouped[location][feature_type][value]["_marks_by_char"][char].add(_mark_to_text(mark))
if _is_wendu_mark(mark):
    read_grouped[location][feature_type][value]["wendu"].add(char)
if _is_baidu_mark(mark):
    read_grouped[location][feature_type][value]["baidu"].add(char)
```

- [ ] **Step 5: Finalize `wenbai` and attach `read_stats`**

When building `feature_dict[value]`, derive:

```python
marks_by_char = read_grouped[location][feature][value]["_marks_by_char"]
wenbai_chars = sorted(
    char for char, marks in marks_by_char.items()
    if "2" in marks and "3" in marks
)
```

Then build:

```python
"read_stats": {
    "polyphonic": {
        "count": len(polyphonic_chars),
        "char_indices": sorted(char_to_index[c] for c in polyphonic_chars),
    },
    "wendu": {
        "count": len(wendu_chars),
        "char_indices": sorted(char_to_index[c] for c in wendu_chars),
    },
    "baidu": {
        "count": len(baidu_chars),
        "char_indices": sorted(char_to_index[c] for c in baidu_chars),
    },
    "wenbai": {
        "count": len(wenbai_chars),
        "char_indices": sorted(char_to_index[c] for c in wenbai_chars),
    },
}
```

- [ ] **Step 6: Run the focused test to verify it passes**

Run: `pytest tests/test_phonology_multitable_support.py -k feature_stats -v`
Expected: PASS

- [ ] **Step 7: Commit the implementation**

```bash
git add app/service/core/feature_stats.py tests/test_phonology_multitable_support.py
git commit -m "feat: add wenbai stats to feature_stats"
```

### Task 3: Add failing tests for `phonology_matrix` parallel read stats

**Files:**
- Modify: `tests/test_phonology_multitable_support.py`
- Modify: `app/service/core/matrix.py`

- [ ] **Step 1: Add a failing test for `matrix_read_stats`**

Write a test that asserts:

```python
cell = result["data"]["測試點"]["matrix_read_stats"]["k"]["a"]["陰平"]
assert cell == {
    "polyphonic": {"count": 2, "chars": ["甲", "乙"]},
    "wendu": {"count": 1, "chars": ["乙"]},
    "baidu": {"count": 1, "chars": ["乙"]},
    "wenbai": {"count": 1, "chars": ["乙"]},
}
```

and separately asserts that the original `matrix["k"]["a"]["陰平"]` remains a plain list.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/test_phonology_multitable_support.py -k phonology_matrix -v`
Expected: FAIL because `matrix_read_stats` is missing

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_phonology_multitable_support.py
git commit -m "test: cover phonology_matrix wenbai read stats"
```

### Task 4: Implement `matrix_read_stats`

**Files:**
- Modify: `app/service/core/matrix.py`
- Test: `tests/test_phonology_multitable_support.py`

- [ ] **Step 1: Add helper functions for marks in `matrix.py`**

Add the same private helpers used by `feature_stats`:

```python
def _mark_to_text(value) -> str:
    return "" if value is None else str(value).strip()


def _is_polyphonic_mark(value) -> bool:
    return _mark_to_text(value) in {"1", "2", "3"}


def _is_wendu_mark(value) -> bool:
    return _mark_to_text(value) == "2"


def _is_baidu_mark(value) -> bool:
    return _mark_to_text(value) == "3"
```

- [ ] **Step 2: Keep the existing grouped query for `matrix` unchanged**

Do not alter the current grouped query that builds:

```python
loc_data["matrix"][initial][final][tone] = chars_list
```

This preserves backward compatibility.

- [ ] **Step 3: Add a second fine-grained query for mark-aware rows**

After the current grouped query, add:

```python
detail_query = f"""
    SELECT 簡稱, 聲母, 韻母, 聲調, 漢字, 多音字
    FROM {table}
    WHERE 簡稱 IN ({placeholders})
      AND 簡稱 IS NOT NULL
      AND 聲母 IS NOT NULL
      AND 韻母 IS NOT NULL
      AND 聲調 IS NOT NULL
      AND 漢字 IS NOT NULL
"""
cursor.execute(detail_query)
detail_rows = cursor.fetchall()
```

- [ ] **Step 4: Aggregate `matrix_read_stats` per cell**

Create:

```python
read_stats_by_location = defaultdict(
    lambda: defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: {
                    "polyphonic": set(),
                    "wendu": set(),
                    "baidu": set(),
                    "_marks_by_char": defaultdict(set),
                }
            )
        )
    )
)
```

Then for each row:

```python
cell = read_stats_by_location[location][initial][final][tone]
mark_text = _mark_to_text(mark)
if _is_polyphonic_mark(mark_text):
    cell["polyphonic"].add(char)
    cell["_marks_by_char"][char].add(mark_text)
if _is_wendu_mark(mark_text):
    cell["wendu"].add(char)
if _is_baidu_mark(mark_text):
    cell["baidu"].add(char)
```

- [ ] **Step 5: Finalize `wenbai` and serialize `matrix_read_stats`**

For each location/cell:

```python
wenbai_chars = sorted(
    char for char, marks in cell["_marks_by_char"].items()
    if "2" in marks and "3" in marks
)
serialized_cell = {
    "polyphonic": {"count": len(polyphonic_chars), "chars": sorted(polyphonic_chars)},
    "wendu": {"count": len(wendu_chars), "chars": sorted(wendu_chars)},
    "baidu": {"count": len(baidu_chars), "chars": sorted(baidu_chars)},
    "wenbai": {"count": len(wenbai_chars), "chars": wenbai_chars},
}
```

Then add to the location payload:

```python
"matrix_read_stats": serialized_read_stats_tree
```

- [ ] **Step 6: Run the focused test to verify it passes**

Run: `pytest tests/test_phonology_multitable_support.py -k phonology_matrix -v`
Expected: PASS

- [ ] **Step 7: Commit the implementation**

```bash
git add app/service/core/matrix.py tests/test_phonology_multitable_support.py
git commit -m "feat: add matrix_read_stats to phonology_matrix"
```

### Task 5: Update docs and examples

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-06-21-wenbai-feature-stats-phonology-matrix-design.md`

- [ ] **Step 1: Add `feature_stats.read_stats` response example**

Document an example block showing:

```json
"read_stats": {
  "polyphonic": {"count": 2, "char_indices": [0, 3]},
  "wendu": {"count": 1, "char_indices": [3]},
  "baidu": {"count": 1, "char_indices": [3]},
  "wenbai": {"count": 1, "char_indices": [3]}
}
```

- [ ] **Step 2: Add `phonology_matrix.matrix_read_stats` response example**

Document an example block showing:

```json
"matrix_read_stats": {
  "k": {
    "a": {
      "陰平": {
        "polyphonic": {"count": 1, "chars": ["甲"]},
        "wendu": {"count": 1, "chars": ["甲"]},
        "baidu": {"count": 0, "chars": []},
        "wenbai": {"count": 0, "chars": []}
      }
    }
  }
}
```

- [ ] **Step 3: Run a quick grep sanity check**

Run: `rg -n "read_stats|matrix_read_stats|wenbai" README.md app/service/core tests`
Expected: new fields appear in docs, code, and tests

- [ ] **Step 4: Commit the docs**

```bash
git add README.md docs/superpowers/specs/2026-06-21-wenbai-feature-stats-phonology-matrix-design.md
git commit -m "docs: document wenbai read stats responses"
```

### Task 6: Run full verification

**Files:**
- Test: `tests/test_phonology_multitable_support.py`
- Test: any directly affected matrix / service tests discovered during Task 1

- [ ] **Step 1: Run the directly affected test module**

Run: `pytest tests/test_phonology_multitable_support.py -v`
Expected: PASS

- [ ] **Step 2: Run a broader targeted regression sweep**

Run: `pytest tests -k "phonology or matrix or multitable" -v`
Expected: PASS for all relevant tests

- [ ] **Step 3: Inspect the diff for accidental response-shape changes**

Run: `git diff -- app/service/core/feature_stats.py app/service/core/matrix.py README.md tests/test_phonology_multitable_support.py`
Expected: only additive response fields and test/doc updates

- [ ] **Step 4: Final commit if verification required follow-up edits**

```bash
git add app/service/core/feature_stats.py app/service/core/matrix.py README.md tests/test_phonology_multitable_support.py
git commit -m "test: verify backward-compatible wenbai stats changes"
```
