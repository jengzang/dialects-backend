# Skill: SVD Cross-Dataset Polyphone Aligner

## Implementation

**Source Code**: `reference/align.py`

Key functions/classes: align_chars(), preprocess_chars()

## Objective
Automatically align polyphonic characters and resolve ID mappings across disparate datasets (e.g., Xiaoxuetang vs. Yubao) using matrix decomposition, eliminating manual character-ID tagging.

## Mathematical Foundation

### SVD-based Alignment

Let X be a co-occurrence matrix of monophonic characters across datasets. Perform Singular Value Decomposition:

```
X = U Σ Vᵀ
```

To find latent vector y₁ for polyphonic character x₁ in Dataset 1, compute the pseudo-inverse:

```
y₁ = U₁† x₁
```

where U₁† is the Moore-Penrose pseudo-inverse of U₁.

### Distance Metric

The distance between characters across datasets simplifies to Euclidean distance in latent space:

```
d²(x₁, x₂) = |y₁ - y₂|²
```

Characters with small distances are likely the same character with different IDs.

## Implementation Details

### Core Functions

```python
def preprocess_chars(
    dataset: DataFrame,
    chars: Series | ndarray | None = None
) -> tuple[ndarray, ndarray, ndarray | None]:
    """
    Preprocess dataset to extract character information

    Parameters:
        dataset: Long-format dataset with cid, initial, final, tone
        chars: Optional cid to character mapping

    Returns:
        cids: Character IDs
        simplified: Simplified Chinese characters
        traditional: Traditional Chinese characters (or None)
    """

def align_chars(
    *char_lists: list[tuple[ndarray, ndarray | None, ndarray | None]]
) -> tuple[DataFrame, list[DataFrame]]:
    """
    Align characters across datasets based on character forms

    Parameters:
        char_lists: List of (cids, simplified, traditional) tuples for each dataset

    Returns:
        monophones: Aligned monophonic characters DataFrame with columns:
            - character: Character form (simplified preferred)
            - simplified: Simplified form
            - traditional: Traditional form
            - 0, 1, ...: Character IDs from each dataset
        polyphones: List of polyphonic character DataFrames (one per dataset)
    """
```

### Character Form Handling

The implementation uses **OpenCC** for simplified/traditional conversion:

```python
import opencc

converter = opencc.OpenCC('t2s')  # Traditional to Simplified
simplified = chars.map(converter.convert)
```

**Alignment Strategy**:
1. If dataset has both simplified and traditional: strict alignment on both
2. If only simplified: align on simplified only
3. If only traditional: align on traditional only

### Monophonic vs Polyphonic

- **Monophonic**: Characters with unique character form (one-to-one mapping)
- **Polyphonic**: Characters with same form but different IDs (one-to-many mapping)

The algorithm:
1. Aligns all monophonic characters first (exact match on character form)
2. Separates polyphonic characters for further processing
3. Uses SVD on monophonic co-occurrence matrix to project polyphonic characters

## Usage Example

```python
import sincomp.datasets
import sincomp.align

# Load multiple datasets
ccr = sincomp.datasets.get('CCR')
mcpdict = sincomp.datasets.get('MCPDict')

# Preprocess characters
ccr_chars = sincomp.align.preprocess_chars(ccr)
mcpdict_chars = sincomp.align.preprocess_chars(mcpdict)

# Align characters
monophones, polyphones = sincomp.align.align_chars(ccr_chars, mcpdict_chars)

print(f"Aligned monophones: {len(monophones)}")
print(f"CCR polyphones: {len(polyphones[0])}")
print(f"MCPDict polyphones: {len(polyphones[1])}")

# View alignment
print(monophones.head())
# Output:
#   character simplified traditional    0      1
# 0    一        一         一         00001  m001
# 1    丁        丁         丁         00002  m002
# ...
```

## Algorithm Workflow

### Phase 1: Monophonic Alignment

```python
# Step 1: Extract character forms from each dataset
for dataset in datasets:
    cids, simplified, traditional = preprocess_chars(dataset)

# Step 2: Merge on character forms
chars = DataFrame(columns=['simplified', 'traditional'])
for i, (cids, s, t) in enumerate(char_lists):
    if s is not None and t is not None:
        # Strict alignment on both forms
        chars = chars.merge(
            DataFrame({i: cids, 'simplified': s, 'traditional': t}),
            how='outer',
            on=['simplified', 'traditional']
        )
    elif s is not None:
        # Align on simplified only
        chars = chars.merge(
            DataFrame({i: cids, 'simplified': s}),
            how='outer',
            on='simplified'
        )
    # ... similar for traditional only

# Step 3: Separate monophones and polyphones
is_polyphonic = chars['character'].duplicated(keep=False)
monophones = chars[~is_polyphonic]
polyphones = [chars[is_polyphonic & chars[i].notna()] for i in range(len(datasets))]
```

### Phase 2: Polyphonic Alignment (SVD-based)

```python
# Step 1: Build co-occurrence matrix from monophones
X = build_cooccurrence_matrix(monophones, datasets)

# Step 2: SVD decomposition
U, Sigma, Vt = np.linalg.svd(X, full_matrices=False)

# Step 3: Project polyphonic characters
for dataset_idx, polyphone_chars in enumerate(polyphones):
    # Get pronunciation vectors for polyphonic characters
    x_poly = get_pronunciation_vectors(polyphone_chars, datasets[dataset_idx])

    # Project to latent space
    U_pinv = np.linalg.pinv(U)
    y_poly = U_pinv @ x_poly

    # Find nearest neighbors across datasets
    for other_idx in range(len(datasets)):
        if other_idx != dataset_idx:
            y_other = U_pinv @ get_pronunciation_vectors(polyphones[other_idx], datasets[other_idx])
            distances = cdist(y_poly, y_other, metric='euclidean')
            # Assign matches based on minimum distance
```

### Phase 3: Hierarchical Clustering

```python
from scipy.cluster.hierarchy import linkage, fcluster

# Compute distance matrix
distances = compute_pairwise_distances(y_vectors)

# Hierarchical clustering
Z = linkage(distances, method='ward')
clusters = fcluster(Z, t=threshold, criterion='distance')

# Group characters by cluster
aligned_chars = group_by_cluster(clusters, char_ids)
```

## Performance Considerations

- **Time Complexity**: O(n² × d) for SVD, where n = characters, d = dialects
- **Space Complexity**: O(n × d) for co-occurrence matrix
- **Scalability**: Works well for datasets with 1000-10000 characters
- **Accuracy**: Depends on monophonic character overlap between datasets

## Innovation Opportunities

### 1. Bipartite Graph Matching

Model alignment as a **Bipartite Graph Matching** problem:

```python
from scipy.optimize import linear_sum_assignment

def bipartite_matching(cost_matrix):
    """
    Optimal assignment using Hungarian Algorithm

    Parameters:
        cost_matrix: Distance matrix between characters (n1 × n2)

    Returns:
        row_ind, col_ind: Optimal matching indices
    """
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return row_ind, col_ind

# Usage
distances = compute_distances(dataset1_chars, dataset2_chars)
matches = bipartite_matching(distances)
```

**Advantages**:
- Guarantees optimal one-to-one matching
- Polynomial time complexity O(n³)
- No need for threshold tuning

### 2. Optimal Transport (Sinkhorn Distance)

Use **Optimal Transport** for soft alignment:

```python
import ot

def sinkhorn_alignment(X1, X2, reg=0.1):
    """
    Compute optimal transport plan using Sinkhorn algorithm

    Parameters:
        X1, X2: Feature matrices for two datasets
        reg: Regularization parameter

    Returns:
        transport_plan: Soft alignment matrix (n1 × n2)
    """
    # Compute cost matrix (Euclidean distance)
    M = ot.dist(X1, X2, metric='euclidean')

    # Uniform distributions
    a = np.ones(len(X1)) / len(X1)
    b = np.ones(len(X2)) / len(X2)

    # Compute transport plan
    transport_plan = ot.sinkhorn(a, b, M, reg)

    return transport_plan

# Usage
X1 = get_embeddings(dataset1)
X2 = get_embeddings(dataset2)
plan = sinkhorn_alignment(X1, X2)

# Extract hard alignment
matches = plan.argmax(axis=1)
```

**Advantages**:
- Handles many-to-many relationships
- Robust to noise and outliers
- Differentiable (can be used in end-to-end learning)

### 3. Deep Metric Learning

Learn a distance metric using neural networks:

```python
import torch
import torch.nn as nn

class CharacterEncoder(nn.Module):
    def __init__(self, input_dim, embedding_dim):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, embedding_dim)
        )

    def forward(self, x):
        return self.encoder(x)

# Triplet loss for metric learning
def triplet_loss(anchor, positive, negative, margin=1.0):
    distance_positive = (anchor - positive).pow(2).sum(1)
    distance_negative = (anchor - negative).pow(2).sum(1)
    losses = F.relu(distance_positive - distance_negative + margin)
    return losses.mean()
```

## Dependencies

- numpy
- pandas
- scipy (for SVD and clustering)
- scikit-learn
- opencc-python-reimplemented (for Chinese character conversion)

## Related Files

- `src/sincomp/align.py`: Full implementation
- `src/sincomp/factorize.py`: Matrix factorization utilities
- `tests/test_align.py`: Unit tests
- `notebooks/mandarin.ipynb`: Example notebook
