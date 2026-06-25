# Skill: KNN-based Missing Pronunciation Imputation

## Location
`src/sincomp/preprocess.py` - `impute()`, `impute_dialect()`, `character_distances()`

## Objective
Fill missing pronunciation values in dialect data using K-Nearest Neighbors (KNN) algorithm based on character pronunciation similarity, enabling complete datasets for downstream analysis.

## Mathematical Foundation

### Character Distance Metric

Characters are represented as sparse binary vectors based on their pronunciations across dialects:
```
x_i = [p_i1, p_i2, ..., p_in]  # pronunciation vector for character i
```

Distance between characters computed as **cosine distance**:
```
d(x_i, x_j) = 1 - cos(x_i, x_j) = 1 - (x_i · x_j) / (||x_i|| ||x_j||)
```

### KNN Imputation

For missing pronunciation of character i in dialect d:
1. Find k nearest neighbors with non-missing values in dialect d
2. Weight neighbors by inverse distance
3. Select pronunciation with highest weighted frequency

```
weight_j = 1 / (distance(i, j) + ε)
imputed_value = argmax_p Σ(weight_j · I(p_j == p))
```

where ε is a small constant to avoid division by zero.

## Implementation Details

### Core Functions

```python
def character_distances(
    data1: ndarray,
    data2: ndarray | None = None,
    n_jobs: int = 1
) -> ndarray:
    """
    Compute pairwise character distances based on pronunciations

    Parameters:
        data1: Pronunciation matrix (n_chars × n_dialects)
        data2: Optional second matrix (for cross-dataset distances)
        n_jobs: Number of parallel jobs

    Returns:
        distances: Distance matrix (n_chars1 × n_chars2)

    Algorithm:
    1. One-hot encode pronunciations using CountVectorizer
    2. Create sparse binary matrix
    3. Compute cosine distances
    """

def impute_dialect(
    data: ndarray,
    distances: ndarray,
    n_neighbors: int = 3,
    output: ndarray | None = None
) -> ndarray:
    """
    Impute missing values for single dialect

    Parameters:
        data: Pronunciation data with missing values (empty strings)
        distances: Pre-computed character distances
        n_neighbors: Number of neighbors to consider
        output: Optional output array

    Returns:
        imputed: Data with missing values filled

    Algorithm:
    1. Identify missing values
    2. For each missing value:
       a. Find k nearest neighbors with non-missing values
       b. Compute inverse-distance weights
       c. Select most frequent pronunciation (weighted)
    """

def impute(
    data: ndarray | DataFrame,
    n_neighbors: int = 3,
    n_jobs: int = 1
) -> ndarray | DataFrame:
    """
    Impute missing values across all dialects

    Parameters:
        data: Full pronunciation matrix (n_chars × n_features)
        n_neighbors: Number of neighbors for imputation
        n_jobs: Number of parallel jobs

    Returns:
        imputed: Complete pronunciation matrix

    Algorithm:
    1. Compute character distances once
    2. Impute each dialect column in parallel
    3. Return complete matrix
    """
```

### Algorithm Workflow

```
Input: Pronunciation matrix with missing values

Step 1: Compute Character Distances
├─ One-hot encode all pronunciations
├─ Create sparse binary matrix
└─ Compute pairwise cosine distances

Step 2: For each dialect (parallel):
├─ Identify characters with missing pronunciations
├─ For each missing character:
│  ├─ Find k nearest neighbors (non-missing)
│  ├─ Compute weights: w_j = 1 / (d_j + ε)
│  ├─ Count weighted pronunciation frequencies
│  └─ Select pronunciation with max weight
└─ Fill missing values

Output: Complete pronunciation matrix
```

## Usage Example

### Basic Imputation

```python
import numpy as np
import pandas as pd
import sincomp.preprocess as prep

# Create sample data with missing values
data = pd.DataFrame({
    'dialect1_initial': ['p', 'pʰ', '', 't', 'tʰ'],
    'dialect1_final': ['a', 'a', 'i', 'i', ''],
    'dialect2_initial': ['p', '', 'ts', 't', 'tʰ'],
    'dialect2_final': ['a', 'a', 'i', '', 'u']
})

# Impute missing values
imputed = prep.impute(data, n_neighbors=3)
print(imputed)
```

### With Real Dataset

```python
import sincomp.datasets
import sincomp.preprocess as prep

# Load dataset
ccr = sincomp.datasets.get('CCR')

# Transform to wide format
wide = prep.transform(
    ccr,
    index='cid',
    columns='did',
    values=['initial', 'final', 'tone'],
    fill_value=''
)

# Count missing values
missing_before = (wide == '').sum().sum()
print(f"Missing values before: {missing_before}")

# Impute
imputed = prep.impute(wide.values, n_neighbors=5, n_jobs=4)
imputed_df = pd.DataFrame(
    imputed,
    index=wide.index,
    columns=wide.columns
)

# Count missing values after
missing_after = (imputed_df == '').sum().sum()
print(f"Missing values after: {missing_after}")
```

### Custom Distance Computation

```python
# Compute distances separately for reuse
distances = prep.character_distances(data.values, n_jobs=4)

# Impute multiple times with different k
for k in [3, 5, 7]:
    imputed = prep.impute_dialect(
        data.values[:, 0],  # Single dialect
        distances,
        n_neighbors=k
    )
    print(f"k={k}: {imputed}")
```

## Performance Considerations

### Time Complexity
- **Distance computation**: O(n² × d × v) where n=characters, d=dialects, v=vocabulary size
- **Imputation per dialect**: O(m × k × log n) where m=missing values, k=neighbors
- **Total**: O(n² × d × v + m × d × k × log n)

### Space Complexity
- **Distance matrix**: O(n²)
- **Sparse encoding**: O(n × d × v) but sparse
- **Memory-efficient**: Uses sparse matrices throughout

### Optimization Strategies

1. **Parallel Processing**:
```python
# Parallelize dialect imputation
imputed = prep.impute(data, n_jobs=-1)  # Use all CPUs
```

2. **Batch Processing**:
```python
# Process large datasets in batches
batch_size = 1000
for i in range(0, len(data), batch_size):
    batch = data[i:i+batch_size]
    imputed_batch = prep.impute(batch)
```

3. **Pre-compute Distances**:
```python
# Compute once, reuse multiple times
distances = prep.character_distances(data)
for dialect_idx in range(data.shape[1]):
    imputed_col = prep.impute_dialect(
        data[:, dialect_idx],
        distances,
        n_neighbors=3
    )
```

## Evaluation Metrics

### Imputation Accuracy

```python
def evaluate_imputation(original, imputed, test_mask):
    """
    Evaluate imputation accuracy on held-out values

    Parameters:
        original: Original data with all values
        imputed: Imputed data
        test_mask: Boolean mask of held-out values

    Returns:
        accuracy: Proportion of correct imputations
    """
    correct = (original[test_mask] == imputed[test_mask]).sum()
    total = test_mask.sum()
    return correct / total

# Example usage
# 1. Hold out 10% of values
test_mask = np.random.rand(*data.shape) < 0.1
data_with_missing = data.copy()
data_with_missing[test_mask] = ''

# 2. Impute
imputed = prep.impute(data_with_missing)

# 3. Evaluate
accuracy = evaluate_imputation(data, imputed, test_mask)
print(f"Imputation accuracy: {accuracy:.2%}")
```

## Innovation Opportunities

### 1. Deep Learning-based Imputation

Replace KNN with neural network:

```python
import torch
import torch.nn as nn

class PronunciationImputer(nn.Module):
    def __init__(self, n_chars, n_dialects, embedding_dim=64):
        super().__init__()
        self.char_emb = nn.Embedding(n_chars, embedding_dim)
        self.dialect_emb = nn.Embedding(n_dialects, embedding_dim)
        self.decoder = nn.Sequential(
            nn.Linear(embedding_dim * 2, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, vocab_size)
        )

    def forward(self, char_ids, dialect_ids):
        char_vec = self.char_emb(char_ids)
        dialect_vec = self.dialect_emb(dialect_ids)
        combined = torch.cat([char_vec, dialect_vec], dim=-1)
        return self.decoder(combined)

# Training
model = PronunciationImputer(n_chars, n_dialects)
optimizer = torch.optim.Adam(model.parameters())
criterion = nn.CrossEntropyLoss()

for epoch in range(100):
    # Train on non-missing values
    predictions = model(char_ids, dialect_ids)
    loss = criterion(predictions, target_pronunciations)
    loss.backward()
    optimizer.step()

# Imputation
with torch.no_grad():
    imputed = model(missing_char_ids, missing_dialect_ids).argmax(dim=-1)
```

**Advantages**:
- Learns complex patterns
- Can incorporate additional features (geography, historical relationships)
- Better generalization

### 2. Matrix Completion Methods

Use matrix factorization for imputation:

```python
from sklearn.decomposition import NMF

def matrix_completion_impute(data, n_components=50):
    """
    Impute using Non-negative Matrix Factorization

    data = W @ H
    where W: character factors, H: dialect factors
    """
    # Encode to numeric
    encoder = LabelEncoder()
    numeric_data = encoder.fit_transform(data.ravel()).reshape(data.shape)

    # Replace missing with mean
    mask = data != ''
    numeric_data[~mask] = numeric_data[mask].mean()

    # NMF
    nmf = NMF(n_components=n_components, max_iter=500)
    W = nmf.fit_transform(numeric_data)
    H = nmf.components_

    # Reconstruct
    reconstructed = W @ H

    # Decode back to pronunciations
    imputed = encoder.inverse_transform(
        reconstructed.round().astype(int).ravel()
    ).reshape(data.shape)

    return imputed
```

### 3. Probabilistic Imputation

Use Bayesian methods for uncertainty quantification:

```python
from sklearn.gaussian_process import GaussianProcessRegressor

def probabilistic_impute(data, distances):
    """
    Impute with uncertainty estimates using Gaussian Process

    Returns both imputed values and confidence intervals
    """
    gp = GaussianProcessRegressor(
        kernel=RBF(length_scale=1.0),
        alpha=0.1
    )

    imputed = []
    uncertainties = []

    for i in range(data.shape[1]):
        # Train on non-missing
        mask = data[:, i] != ''
        X_train = distances[mask][:, mask]
        y_train = encode(data[mask, i])

        gp.fit(X_train, y_train)

        # Predict missing
        X_test = distances[~mask][:, mask]
        y_pred, y_std = gp.predict(X_test, return_std=True)

        imputed.append(decode(y_pred))
        uncertainties.append(y_std)

    return imputed, uncertainties
```

### 4. Ensemble Methods

Combine multiple imputation strategies:

```python
def ensemble_impute(data, methods=['knn', 'matrix', 'gp']):
    """
    Ensemble imputation using multiple methods

    Voting strategy:
    - If all methods agree: use that value
    - If methods disagree: use most frequent
    - Weight by method confidence
    """
    imputations = []

    if 'knn' in methods:
        imputations.append(knn_impute(data))
    if 'matrix' in methods:
        imputations.append(matrix_completion_impute(data))
    if 'gp' in methods:
        imputations.append(probabilistic_impute(data)[0])

    # Majority voting
    ensemble = np.array(imputations)
    imputed = np.apply_along_axis(
        lambda x: np.bincount(x).argmax(),
        axis=0,
        arr=ensemble
    )

    return imputed
```

## Dependencies

- numpy
- pandas
- scikit-learn
- scipy (for sparse matrices)
- joblib (for parallel processing)

## Related Files

- `src/sincomp/preprocess.py`: Full implementation
- `src/sincomp/auxiliary.py`: Helper functions for encoding
- `tests/test_preprocess.py`: Unit tests

## Comparison with Other Methods

| Method | Accuracy | Speed | Memory | Uncertainty |
|--------|----------|-------|--------|-------------|
| KNN | Good | Fast | Low | No |
| Matrix Factorization | Better | Medium | Medium | No |
| Gaussian Process | Best | Slow | High | Yes |
| Neural Network | Best | Fast (after training) | Medium | Possible |
| Ensemble | Best | Slow | High | Yes |

**Recommendation**: Use KNN for quick imputation, Neural Network for production systems, Gaussian Process when uncertainty is critical.
