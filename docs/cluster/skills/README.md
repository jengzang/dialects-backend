# SinComp Core Algorithmic Skills

This directory contains extracted algorithmic skills from the SinComp project. Each skill is a **self-contained, portable module** that can be directly copied to other projects.

## Directory Structure

Each skill is organized as a standalone folder:

```
skills/
├── skill_name/
│   ├── README.md          # Skill documentation
│   └── reference/         # Source code implementation
│       ├── module.py      # Main implementation
│       └── ...            # Additional files
```

**Key Feature**: You can copy any skill folder to another project and have immediate access to both documentation and working code - no need to hunt for files in the original repository!

## Skills Overview

### 1. Bilinear Phonology Encoder
**File**: `bilinear_phonology_encoder.md`
**Location**: `src/sincomp/models.py`

Neural network model that maps discrete dialect pronunciation data into dense continuous embeddings using bilinear transformations between dialect-specific and character-specific representations.

**Key Features**:
- TensorFlow-based implementation
- Handles missing and unknown values
- Supports residual connections
- Cross-entropy loss with sparse softmax

**Use Cases**:
- Dialect pronunciation prediction
- Phonological feature extraction
- Cross-dialect transfer learning

---

### 2. Probabilistic Phonological Similarity Engine
**File**: `probabilistic_phonological_similarity_engine.md`
**Location**: `src/sincomp/similarity.py`

Computes robust dialect-to-dialect similarity matrices using chi-square tests and conditional entropy, ignoring raw phonetic values to avoid transcription biases.

**Key Features**:
- Chi-square similarity (standardized to N(0,1))
- Conditional entropy distance
- Sparse matrix operations for efficiency
- Parallel computation support

**Use Cases**:
- Dialect clustering
- Phylogenetic tree construction
- Dialect distance measurement

---

### 3. Latent Phonological Vectorization
**File**: `latent_phonological_vectorization.md`
**Location**: `src/sincomp/factorize.py`

Transforms character homophony relationships into dense dialect vectors using matrix factorization with alternating least squares.

**Key Features**:
- SVD-based factorization
- Alternating least squares optimization
- L2 regularization
- Coverage-based filtering

**Use Cases**:
- Dialect embedding
- Phonological category discovery
- Dimensionality reduction

---

### 4. SVD Cross-Dataset Polyphone Aligner
**File**: `svd_cross_dataset_polyphone_aligner.md`
**Location**: `src/sincomp/align.py`

Automatically aligns polyphonic characters across disparate datasets using SVD and pseudo-inverse projection, eliminating manual character-ID mapping.

**Key Features**:
- SVD-based alignment
- Handles simplified/traditional Chinese
- Hierarchical clustering
- Pseudo-inverse projection

**Use Cases**:
- Dataset integration
- Character ID mapping
- Cross-corpus alignment

---

### 5. GLM Dialect Classifier and Isogloss Mapper
**File**: `glm_dialect_classifier_and_isogloss_mapper.md`
**Location**: `src/sincomp/compare.py`, `scripts/dialect_classifier.py`, `scripts/isogloss.py`

Classifies dialects using logistic regression on phonological rule compliance and generates geographical isogloss maps.

**Key Features**:
- Cosine similarity-based rule compliance
- L1-regularized logistic regression
- Active learning support
- Geographical contour mapping

**Use Cases**:
- Dialect classification
- Isogloss boundary detection
- Geographical linguistic analysis

---

### 6. IPA Phonetic Normalization and Syllable Segmentation
**File**: `ipa_phonetic_normalization_and_syllable_segmentation.md`
**Location**: `src/sincomp/preprocess.py`

Standardizes IPA transcriptions and segments syllables into initial, final, and tone components using regex or CRF-based methods.

**Key Features**:
- 400+ IPA character mappings
- Regex-based fast segmentation
- CRF-based accurate segmentation
- Romanization type classification (pinyin, jyutping, etc.)

**Use Cases**:
- IPA data cleaning
- Syllable structure analysis
- Cross-transcription system normalization
- Romanization detection

---

### 7. KNN-based Missing Pronunciation Imputation
**File**: `knn_missing_pronunciation_imputation.md`
**Location**: `src/sincomp/preprocess.py`

Fills missing pronunciation values using K-Nearest Neighbors based on character pronunciation similarity across dialects.

**Key Features**:
- Cosine distance-based character similarity
- Inverse-distance weighted voting
- Parallel processing support
- Sparse matrix optimization

**Use Cases**:
- Missing data imputation
- Dataset completion
- Pronunciation prediction
- Data quality improvement

---

### 8. Proto-Language Reconstruction via Decision Tree Autoencoder
**File**: `proto_language_reconstruction_via_decision_tree_autoencoder.md`
**Location**: `scripts/recon.py`

Reconstructs ancestral phonological categories from modern dialect pronunciations using decision tree autoencoders for denoising and clustering.

**Key Features**:
- Decision tree-based autoencoder
- Entropy-based category discovery
- Component-wise reconstruction (initial/final/tone)
- Iterative imputation with logistic regression

**Use Cases**:
- Historical linguistics research
- Proto-language reconstruction
- Sound change pattern discovery
- Dialect phylogeny analysis

---

## How to Use These Skills

Each skill document contains:

1. **Mathematical Foundation**: Theoretical basis and formulas
2. **Implementation Details**: Core functions and algorithms
3. **Usage Examples**: Code snippets demonstrating usage
4. **Innovation Opportunities**: Suggestions for improvements and extensions
5. **Dependencies**: Required libraries and versions
6. **Related Files**: Links to implementation and tests

## Integration Guide

To integrate a skill into your project:

1. **Read the skill document** to understand the algorithm
2. **Check dependencies** and install required packages
3. **Copy relevant code** from the specified location in `src/sincomp/`
4. **Adapt to your data format** (see usage examples)
5. **Consider innovations** suggested in each document

## Skill Dependencies

### Common Dependencies
- numpy
- pandas
- scipy
- scikit-learn >= 1.2

### Skill-Specific Dependencies
- **Bilinear Encoder**: TensorFlow >= 2.8
- **Similarity Engine**: joblib (for parallel computation)
- **Factorize**: scipy.sparse
- **Aligner**: opencc-python-reimplemented
- **Classifier/Mapper**: cartopy, geopandas, matplotlib

## Contributing

When extracting new skills from the codebase:

1. Create a new markdown file in this directory
2. Follow the existing skill document structure
3. Include mathematical foundations and implementation details
4. Provide usage examples and innovation opportunities
5. Update this README with the new skill

## References

For more information about the SinComp project and its algorithms, see:

- [基于矩阵分解的方言字音对齐](https://zhuanlan.zhihu.com/p/20230566259)
- [基于方言之间的预测相似度进行方言聚类](https://zhuanlan.zhihu.com/p/464735745)
- [什么是官话？——兼及方言分类的概率模型](https://zhuanlan.zhihu.com/p/629007299)
- [使用双线性编码建模多方言音系](https://zhuanlan.zhihu.com/p/659731592)

## License

These skills are extracted from the SinComp project, which is licensed under the MIT License. See the main project LICENSE file for details.
