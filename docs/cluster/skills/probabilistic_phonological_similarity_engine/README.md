# Skill: Probabilistic Phonological Similarity Engine

## Location
`src/sincomp/similarity.py` - `chi2()` and `entropy()` functions

## Objective
Construct robust dialect-to-dialect distance/similarity matrices based solely on phonological category correspondences, ignoring raw phonetic values to avoid transcription standard biases.

## Mathematical Foundation

### 1. Conditional Entropy Method

Measures how much certainty dialect A provides about dialect B's pronunciation:

```
H(s_b | s_a) = E[-log P(s_b | s_a)]
```

To mitigate data sparsity, approximates joint conditional entropy by taking minimum of sub-components (initials, finals, tones).

Symmetrical distance:
```
D(a,b) = 1/2 (H(s_b | s_a) + H(s_a | s_b))
```

### 2. Chi-square Test (χ²)

Assesses independence of co-occurring phonetic categories:

```
χ² = Σ(O - E)² / E
```

The χ² statistic is standardized to Gaussian N(0,1) due to large degrees of freedom:

```
standardized χ² = (χ² - dof) / √(2·dof)
```

where dof = degrees of freedom

## Implementation Details

### Core Functions

**`cross_features(data, column=3)`**: Constructs cross-features from phonetic components
- Combines initial/final/tone into paired features
- Returns: array of shape (n_chars, n_dialects, n_cross_features)

**`encode_features(features)`**: One-hot encodes phonetic features
- Uses `sklearn.feature_extraction.text.CountVectorizer`
- Handles missing values with `SimpleImputer`
- Returns: sparse matrix and category counts

**`freq2prob(freqs, limits)`**: Estimates probabilities from frequency counts
- Normalizes frequencies within each category
- Returns: probability array

**`chi2_block(features, feature_categories, feature_probs, targets, target_categories, target_probs)`**: Computes chi-square in blocks
- Memory-efficient block computation
- Standardizes chi-square to normal distribution
- Returns: standardized chi-square matrix

**`_entropy(features, feature_limits, targets, target_limits)`**: Computes conditional entropy
- Uses sparse matrix operations for efficiency
- Formula: `H(Y|X) = (f(x,y) * log f(x) - f(x,y) * log f(x,y)) / f(x)`
- Returns: conditional entropy matrix

### Main API Functions

```python
def chi2(
    src: Dataset | DataFrame | ndarray,
    dest: Dataset | DataFrame | ndarray | None = None,
    feature_num: int = 3,
    blocksize: tuple[int, int] = (100, 100),
    parallel: int = 1
) -> DataFrame | ndarray:
    """
    Computes chi-square similarity between dialects

    Parameters:
        src: Source dialect data (wide format)
        dest: Target dialect data (None = same as src)
        feature_num: Number of features (3 = initial, final, tone)
        blocksize: Block size for parallel computation
        parallel: Number of parallel jobs

    Returns:
        Similarity matrix (higher = more similar)
    """

def entropy(
    src: Dataset | DataFrame | ndarray,
    dest: Dataset | DataFrame | ndarray | None = None,
    feature_num: int = 3
) -> DataFrame | ndarray:
    """
    Computes conditional entropy distance between dialects

    Parameters:
        src: Source dialect data (wide format)
        dest: Target dialect data (None = same as src)
        feature_num: Number of features (3 = initial, final, tone)

    Returns:
        Distance matrix (lower = more similar)
    """
```

## Usage Example

```python
import sincomp.datasets
import sincomp.preprocess
import sincomp.similarity

# Load dataset
ccr = sincomp.datasets.get('CCR')

# Transform to wide format
data = sincomp.preprocess.transform(
    ccr,
    index='cid',
    columns='did',
    values=['initial', 'final', 'tone'],
    aggfunc='first',
    fill_value=''
)

# Compute chi-square similarity
chi2_sim = sincomp.similarity.chi2(data)
print(f"Chi-square similarity shape: {chi2_sim.shape}")

# Compute conditional entropy distance
entropy_dist = sincomp.similarity.entropy(data)
print(f"Entropy distance shape: {entropy_dist.shape}")

# Save results
chi2_sim.to_csv('CCR_chi2.csv')
entropy_dist.to_csv('CCR_entropy.csv')
```

## Command-line Usage

```bash
# Calculate similarity for all dialects (may take a while)
python3 -O -m sincomp.similarity
```

This generates:
- `CCR_chi2.csv`: Chi-square similarity matrix
- `CCR_entropy.csv`: Conditional entropy distance matrix

## Performance Considerations

- **Parallel computation**: Use `parallel` parameter for large datasets
- **Block size**: Adjust `blocksize` based on available memory
- **Sparse matrices**: Efficiently handles missing data
- **Optimization flag**: Use `-O` flag to disable assertions

## Innovation Opportunities

### 1. Bayesian Inference with Dirichlet Priors

Replace simple frequency counting `P(s_b | s_a) = count(s_a, s_b) / count(s_a)` with Bayesian smoothing:

```python
from scipy.stats import dirichlet

def bayesian_prob(counts, alpha=1.0):
    """Estimate probabilities with Dirichlet prior"""
    return (counts + alpha) / (counts.sum() + alpha * len(counts))
```

### 2. Weighted Character Importance

Weight characters by historical linguistic significance using TF-IDF-like structures:

```python
from sklearn.feature_extraction.text import TfidfTransformer

def weighted_similarity(data, weights):
    """Compute similarity with character weights"""
    # Weight by inverse document frequency
    idf = TfidfTransformer().fit(data)
    weighted_data = data * idf.idf_
    return chi2(weighted_data)
```

### 3. Adaptive Feature Selection

Automatically select most informative phonetic features:

```python
from sklearn.feature_selection import mutual_info_classif

def select_features(data, labels, k=100):
    """Select top k features by mutual information"""
    mi = mutual_info_classif(data, labels)
    top_k = np.argsort(mi)[-k:]
    return data[:, top_k]
```

## Dependencies

- numpy
- pandas
- scipy
- scikit-learn >= 1.2
- joblib (for parallel computation)

## Related Files

- `src/sincomp/similarity.py`: Full implementation
- `src/sincomp/preprocess.py`: Data transformation utilities
- `tests/test_similarity.py`: Unit tests
