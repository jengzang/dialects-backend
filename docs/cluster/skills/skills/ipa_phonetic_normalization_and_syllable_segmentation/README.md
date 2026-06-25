# Skill: IPA Phonetic Normalization and Syllable Segmentation

## Implementation

**Source Code**: `reference/preprocess.py, reference/romanization_classifier.csv`

Key functions/classes: clean_ipa(), RegexParser, CRFParser, RomanizationClassifier

## Objective
Standardize and clean IPA (International Phonetic Alphabet) transcriptions of Chinese dialect pronunciations, and segment syllables into initial, final, and tone components using regex or CRF-based methods.

## Mathematical Foundation

### Character Normalization
Maps non-standard IPA characters to standard IPA characters using predefined mapping tables:
```
clean_char = CHAR_MAP[raw_char]
```

### Syllable Segmentation Pattern
```
syllable = initial + final + tone
```

where:
- **initial**: consonants + diacritics (can be empty ∅)
- **final**: vowels + consonants + diacritics + suprasegmentals
- **tone**: tone markers (1-5, superscripts, or tone bars)

### CRF-based Segmentation
Uses Conditional Random Fields for sequence labeling with BIOSE tagging scheme:
- **B**: Beginning of element
- **I**: Inside element
- **E**: End of element
- **S**: Single-character element
- **O**: Other (not part of any element)

Tags: `{B,I,E,S,O}-{I,F,T}` where I=initial, F=final, T=tone

## Implementation Details

### Core Components

**1. IPA Character Sets**
- `_CONSONANTS`: 200+ consonant characters
- `_VOWELS`: 40+ vowel characters
- `_DIACRITICS`: 100+ diacritic marks
- `_SUPRASEGMENTALS`: Length markers, stress marks
- `_TONES`: Tone numbers and tone bars

**2. Character Mapping Tables**
- `_CHAR_MAP`: Non-standard → standard IPA
- `_STRING_MAP`: Multi-character replacements
- `_TYPE_MAP`: Character → type (consonant/vowel/diacritic/tone)
- `_MANNER_MAP`: Consonant → manner of articulation

### Key Functions

```python
def clean_ipa(raw: Series, force: bool = False) -> Series:
    """
    Clean and standardize IPA transcriptions

    Parameters:
        raw: Raw IPA strings
        force: If True, remove all non-IPA characters

    Returns:
        clean: Standardized IPA strings
    """

def clean_initial(raw: Series) -> Series:
    """Clean initial consonants, allowing ∅ for zero initial"""

def clean_final(raw: Series) -> Series:
    """Clean finals (vowels + consonants + diacritics)"""

def clean_tone(raw: Series) -> Series:
    """Clean tone markers, allowing ∅ for neutral tone"""

def normalize_initial(origin: Series) -> Series:
    """
    Normalize initials to standard forms
    - Convert digraphs (dz, ts, tʃ, etc.)
    - Standardize aspiration and labialization markers
    """

def tone2super(origin: Series) -> Series:
    """Convert tone digits to superscripts (1→¹, 2→², etc.)"""
```

### Segmentation Methods

**1. Regex-based Parser**

```python
class RegexParser:
    def __init__(self, pattern: str):
        """
        Parameters:
            pattern: Regex with 3 groups (initial, final, tone)
        """
        self.pattern = pattern

    def parse(self, syllable: str) -> tuple[str, str, str]:
        """Segment single syllable"""

    def parse_batch(self, syllables: ndarray) -> DataFrame:
        """Segment batch of syllables"""
```

Default pattern:
```python
pattern = (
    f'([{DIACRITICS}]*[{CONSONANTS}][{CONSONANTS}{DIACRITICS}]*|)'  # initial
    f'([{DIACRITICS}]*[{LETTERS}][{LETTERS|DIACRITICS|SUPRASEGMENTALS}]*)'  # final
    f'([{TONES}]*)'  # tone
)
```

**2. CRF-based Parser**

```python
class CRFParser:
    def __init__(self, path: str):
        """Load pre-trained CRF model"""
        self.model = CRF(model_filename=path)

    def parse(self, syllable: str) -> tuple[str, str, str]:
        """
        Segment using CRF sequence labeling

        Steps:
        1. Extract features: str2fea(syllable)
        2. Predict tags: model.predict_single(features)
        3. Segment: segment(syllable, tags)
        """
```

**Feature Extraction for CRF**:
```python
def str2fea(s: str) -> list[dict]:
    """
    Extract features for each character

    Features:
        - char: character itself
        - type: consonant/vowel/diacritic/tone
        - manner: plosive/fricative/nasal/etc. (for consonants)
        - context: -1, 0, +1 positions
    """
```

## Usage Example

### Basic Cleaning

```python
import pandas as pd
import sincomp.preprocess as prep

# Raw IPA data
raw_data = pd.Series(['pʰa55', 'tsʰɿ35', 'tɕʰy213'])

# Clean IPA
clean = prep.clean_ipa(raw_data)
print(clean)
# Output: ['pʰa⁵⁵', 'tsʰɿ³⁵', 'tɕʰy²¹³']

# Normalize initials
normalized = prep.normalize_initial(clean)
```

### Syllable Segmentation (Regex)

```python
# Default regex parser
parser = prep.parse

# Single syllable
initial, final, tone = parser('pʰa⁵⁵')
print(f"Initial: {initial}, Final: {final}, Tone: {tone}")
# Output: Initial: pʰ, Final: a, Tone: ⁵⁵

# Batch processing
syllables = pd.Series(['pʰa⁵⁵', 'tsʰɿ³⁵', 'tɕʰy²¹³'])
result = parser(syllables)
print(result)
#    initial final tone
# 0     pʰ     a   ⁵⁵
# 1    tsʰ     ɿ   ³⁵
# 2   tɕʰ     y  ²¹³
```

### Syllable Segmentation (CRF)

```python
# Load CRF model
crf_parser = prep.CRFParser('path/to/crf_model.pkl')

# Segment syllables
syllables = ['pʰa⁵⁵', 'tsʰɿ³⁵', 'tɕʰy²¹³']
result = crf_parser.parse_batch(syllables)
```

### Complete Pipeline

```python
import sincomp.datasets
import sincomp.preprocess as prep

# Load dataset
ccr = sincomp.datasets.get('CCR')

# Clean and normalize
ccr['syllable'] = prep.clean_ipa(ccr['syllable'])

# Segment into initial, final, tone
segments = prep.parse(ccr['syllable'])
ccr[['initial', 'final', 'tone']] = segments

# Further cleaning
ccr['initial'] = prep.clean_initial(ccr['initial'])
ccr['final'] = prep.clean_final(ccr['final'])
ccr['tone'] = prep.clean_tone(ccr['tone'])

# Normalize
ccr['initial'] = prep.normalize_initial(ccr['initial'])
ccr['tone'] = prep.tone2super(ccr['tone'])
```

## Romanization Type Classification

**Location**: `src/sincomp/preprocess.py` - `RomanizationClassifier`

Automatically detect romanization system type:

```python
# Built-in classifier
classifier = prep.get_romanization_type

# Classify single romanization
rom_type = classifier('ni3 hao3')
print(rom_type)  # Output: 'pinyin'

# Batch classification
roms = ['ni3 hao3', 'nei5 hou2', 'li2 ho2']
types = classifier(roms)
print(types)  # Output: ['pinyin', 'jyutping', 'beh-oe-ji']
```

Supported types:
- **IPA**: International Phonetic Alphabet
- **pinyin**: Mandarin Pinyin
- **jyutping**: Cantonese Jyutping
- **beh-oe-ji**: Hokkien POJ (白話字)
- **romaji**: Japanese Romaji
- **romaja**: Korean Romaja
- **quoc ngu**: Vietnamese Quốc ngữ
- **other**: Other systems

## Performance Considerations

- **Regex parser**: Very fast, O(n) per syllable
- **CRF parser**: Slower but more accurate, O(n²) per syllable
- **Batch processing**: Use vectorized operations for large datasets
- **Memory**: Character sets loaded once at module import

## Innovation Opportunities

### 1. Neural Sequence-to-Sequence Segmentation

Replace CRF with Transformer-based model:

```python
import torch
import torch.nn as nn

class TransformerSegmenter(nn.Module):
    def __init__(self, vocab_size, d_model=128, nhead=4):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model, nhead),
            num_layers=3
        )
        self.classifier = nn.Linear(d_model, 7)  # 7 BIOSE tags

    def forward(self, x):
        x = self.embedding(x)
        x = self.transformer(x)
        return self.classifier(x)
```

**Advantages**:
- Captures long-range dependencies
- Better handling of ambiguous cases
- Can be pre-trained on large corpora

### 2. Multi-task Learning

Train single model for multiple tasks:
- Syllable segmentation
- Romanization type detection
- IPA validation
- Tone sandhi prediction

```python
class MultiTaskSegmenter(nn.Module):
    def __init__(self):
        super().__init__()
        self.shared_encoder = TransformerEncoder(...)
        self.segmentation_head = nn.Linear(d_model, 7)
        self.romanization_head = nn.Linear(d_model, 8)
        self.validation_head = nn.Linear(d_model, 2)

    def forward(self, x):
        features = self.shared_encoder(x)
        return {
            'segments': self.segmentation_head(features),
            'rom_type': self.romanization_head(features),
            'is_valid': self.validation_head(features)
        }
```

### 3. Active Learning for CRF

Improve CRF model with active learning:

```python
def active_learning_crf(unlabeled_data, model, n_queries=100):
    """
    Select most uncertain samples for human annotation

    Uncertainty measures:
    - Entropy of tag probabilities
    - Margin between top-2 predictions
    - Sequence-level confidence
    """
    # Predict with confidence
    predictions, confidences = model.predict_proba(unlabeled_data)

    # Select low-confidence samples
    uncertainty = -np.min(confidences, axis=1)
    query_indices = np.argsort(uncertainty)[-n_queries:]

    return unlabeled_data[query_indices]
```

## Dependencies

- pandas
- numpy
- scikit-learn
- sklearn-crfsuite (for CRF parser)
- joblib

## Related Files

- `src/sincomp/preprocess.py`: Full implementation
- `src/sincomp/romanization_classifier.csv`: Pre-trained romanization classifier
- `scripts/train_romanization_classifier.py`: Training script for romanization classifier
- `tests/test_preprocess.py`: Unit tests
