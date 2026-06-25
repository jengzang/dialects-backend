# Skills Directory Structure

## Overview

This directory contains 8 self-contained, portable algorithmic skills extracted from the SinComp project. Each skill can be independently copied to other projects with all necessary code and documentation.

## Directory Organization

```
skills/
├── README.md                                    # Overview of all skills
├── STRUCTURE.md                                 # This file
│
├── bilinear_phonology_encoder/
│   ├── README.md                                # Skill documentation (4.5K)
│   └── reference/
│       └── models.py                            # TensorFlow implementation (23K)
│
├── probabilistic_phonological_similarity_engine/
│   ├── README.md                                # Skill documentation (6.2K)
│   └── reference/
│       └── similarity.py                        # Chi-square & entropy (22K)
│
├── latent_phonological_vectorization/
│   ├── README.md                                # Skill documentation (8.1K)
│   └── reference/
│       └── factorize.py                         # Matrix factorization (18K)
│
├── svd_cross_dataset_polyphone_aligner/
│   ├── README.md                                # Skill documentation (9.6K)
│   └── reference/
│       └── align.py                             # SVD alignment (32K)
│
├── glm_dialect_classifier_and_isogloss_mapper/
│   ├── README.md                                # Skill documentation (14K)
│   └── reference/
│       ├── compare.py                           # Rule compliance (6.1K)
│       ├── dialect_classifier.py                # Logistic regression (15K)
│       └── isogloss.py                          # Geographical mapping (7.3K)
│
├── ipa_phonetic_normalization_and_syllable_segmentation/
│   ├── README.md                                # Skill documentation (9.6K)
│   └── reference/
│       ├── preprocess.py                        # IPA cleaning & segmentation (43K)
│       └── romanization_classifier.csv          # Pre-trained classifier (18K)
│
├── knn_missing_pronunciation_imputation/
│   ├── README.md                                # Skill documentation (13K)
│   └── reference/
│       └── preprocess.py                        # KNN imputation (43K)
│
└── proto_language_reconstruction_via_decision_tree_autoencoder/
    ├── README.md                                # Skill documentation (17K)
    └── reference/
        └── recon.py                             # Decision tree autoencoder (9.9K)
```

## Total Size

- **Documentation**: ~82K (8 README files)
- **Source Code**: ~252K (12 Python files + 1 CSV)
- **Total**: ~334K

## Usage

### Copying a Skill to Another Project

```bash
# Copy entire skill folder
cp -r skills/bilinear_phonology_encoder /path/to/your/project/

# The skill is now self-contained with:
# - Complete documentation in README.md
# - Working code in reference/
```

### Importing Code

```python
# Option 1: Direct import (add reference/ to Python path)
import sys
sys.path.insert(0, 'bilinear_phonology_encoder/reference')
from models import BilinearEncoder, Processor

# Option 2: Copy to your project structure
# cp bilinear_phonology_encoder/reference/models.py your_project/models/
from your_project.models.models import BilinearEncoder
```

## Skill Categories

### Data Preprocessing (3 skills)
- **IPA Phonetic Normalization**: Clean and standardize IPA transcriptions
- **KNN Missing Pronunciation Imputation**: Fill missing values
- **SVD Cross-Dataset Aligner**: Align characters across datasets

### Similarity & Distance (2 skills)
- **Probabilistic Phonological Similarity Engine**: Chi-square & entropy distances
- **Latent Phonological Vectorization**: Matrix factorization embeddings

### Classification & Modeling (2 skills)
- **Bilinear Phonology Encoder**: Neural network pronunciation model
- **GLM Dialect Classifier**: Logistic regression with isogloss mapping

### Historical Linguistics (1 skill)
- **Proto-Language Reconstruction**: Decision tree autoencoder for ancestral phonology

## Dependencies by Skill

| Skill | Core Dependencies |
|-------|------------------|
| Bilinear Encoder | TensorFlow ≥2.8, scikit-learn |
| Similarity Engine | numpy, pandas, scipy, joblib |
| Vectorization | numpy, pandas, scikit-learn |
| Aligner | numpy, pandas, scipy, opencc |
| GLM Classifier | scikit-learn, cartopy, geopandas |
| IPA Normalization | pandas, sklearn-crfsuite (optional) |
| KNN Imputation | numpy, pandas, scikit-learn, joblib |
| Proto Reconstruction | scikit-learn, pandas, numpy |

## Skill Complexity

| Skill | Lines of Code | Complexity | Learning Curve |
|-------|--------------|------------|----------------|
| IPA Normalization | ~1100 | Medium | Low |
| KNN Imputation | ~1100 | Low | Low |
| Similarity Engine | ~600 | Medium | Medium |
| Aligner | ~900 | High | Medium |
| Vectorization | ~500 | Medium | Medium |
| Bilinear Encoder | ~650 | High | High |
| GLM Classifier | ~700 | Medium | Medium |
| Proto Reconstruction | ~280 | Medium | Medium |

## Quick Start Examples

### 1. Clean IPA Data
```python
from reference.preprocess import clean_ipa, parse
import pandas as pd

# Clean IPA transcriptions
raw = pd.Series(['pʰa55', 'tsʰɿ35'])
clean = clean_ipa(raw)

# Segment syllables
initial, final, tone = parse('pʰa⁵⁵')
```

### 2. Compute Dialect Similarity
```python
from reference.similarity import chi2, entropy

# Compute chi-square similarity
similarity_matrix = chi2(dialect_data)

# Compute conditional entropy distance
distance_matrix = entropy(dialect_data)
```

### 3. Train Dialect Classifier
```python
from reference.compare import compliance, load_rules
from reference.dialect_classifier import train_classifier

# Compute rule compliance
rules = load_rules('rules.json')
features = compliance(data, rules)

# Train classifier
classifier = train_classifier(rules, annotations)
```

## Maintenance

Each skill is independently maintained. When updating:

1. Update code in `reference/`
2. Update documentation in `README.md`
3. Test with examples in README
4. Update version/date in README header

## License

All skills are extracted from SinComp (MIT License).
See main project LICENSE for details.
