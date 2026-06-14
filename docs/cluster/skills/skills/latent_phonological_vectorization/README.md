# Skill: Latent Phonological Vectorization

## Implementation

**Source Code**: `reference/factorize.py`

Key functions/classes: factorize(), _solve_char_embs(), _solve_phone_embs()

## Objective
Directly vectorize dialect phonological categories (音类) without strictly aligning all characters, transforming character homophony relationships into dense, comparable dialect vectors.

## Mathematical Foundation

### Homophony Similarity Matrix

A membership matrix A^(i) defines if character c belongs to phonological category C.

Character similarity computed as cosine similarity:
```
S^(i) = A^(i)ᵀ · A^(i)
```

### Low-Rank Decomposition

Flatten similarity matrices into sparse vector s, then apply SVD:
```
S = U Σ Vᵀ
```

Dense dialect vector:
```
X = Σ Vᵀ
```

**Key Property**: Euclidean distance in latent space equals the number of character pairs with differing phonological categories.

## Implementation Details

### Core Algorithm: Alternating Least Squares

The factorization alternates between solving for character embeddings and pronunciation embeddings:

**Step 1: Solve for character embeddings** (given pronunciation embeddings)
```
minimize ||cooc ⊙ (char_embs @ phone_embs.T) - cooc||² + λ||char_embs||²
```

**Step 2: Solve for pronunciation embeddings** (given character embeddings)
```
minimize ||cooc ⊙ (char_embs @ phone_embs.T) - cooc||² + λ||phone_embs||²
```

### Key Functions

```python
def _solve_char_embs(
    cooc: ndarray,
    phone_embs: ndarray,
    limits: ndarray,
    phone_indeces: list,
    l2: float = 0.0
) -> ndarray:
    """
    Solve for character embeddings using least squares with L2 regularization

    Parameters:
        cooc: Character-dialect co-occurrence matrix (n_chars, n_dialects)
        phone_embs: Pronunciation embedding matrix
        limits: Dialect pronunciation boundaries
        phone_indeces: Character to pronunciation index mapping
        l2: L2 regularization coefficient

    Returns:
        char_embs: Character embeddings (n_chars, embedding_size)
    """

def _solve_phone_embs(
    cooc: ndarray,
    char_embs: ndarray,
    char_indeces: list[list[int]],
    l2: float = 0.0
) -> ndarray:
    """
    Solve for pronunciation embeddings using least squares

    Parameters:
        cooc: Character-dialect co-occurrence matrix
        char_embs: Character embedding matrix
        char_indeces: Dialect-pronunciation to character index mapping
        l2: L2 regularization coefficient

    Returns:
        phone_embs: Pronunciation embeddings (n_phones, embedding_size)
    """

def factorize(
    data: ndarray,
    embedding_size: int = 128,
    max_iter: int = 10,
    tol: float = 0.0001,
    min_dialect_coverage: float | int = 0.2,
    min_character_coverage: float | int = 0.2,
    min_dialects: float | int = 10,
    min_characters: float | int = 100,
    l2: float = 0.0001
) -> tuple[ndarray, ndarray, ndarray, ndarray, list]:
    """
    Matrix factorization of dialect pronunciation data

    Parameters:
        data: Long-format data (dialect_id, char_id, initial, final, tone)
        embedding_size: Dimension of embeddings
        max_iter: Maximum iterations
        tol: Convergence tolerance
        min_dialect_coverage: Minimum dialect coverage for characters
        min_character_coverage: Minimum character coverage for dialects
        min_dialects: Minimum number of dialects
        min_characters: Minimum number of characters
        l2: L2 regularization coefficient

    Returns:
        char_embs: Character embeddings (n_chars, embedding_size)
        phone_embs: Pronunciation embeddings (n_phones, embedding_size)
        char_ids: Character IDs
        dialect_ids: Dialect IDs
        phone_lists: List of pronunciations per dialect
    """
```

## Usage Example

```python
import sincomp.datasets
import sincomp.factorize
import numpy as np

# Load dataset
ccr = sincomp.datasets.get('CCR')

# Prepare data in long format
data = ccr[['did', 'cid', 'initial', 'final', 'tone']].values

# Factorize
char_embs, phone_embs, char_ids, dialect_ids, phone_lists = \
    sincomp.factorize.factorize(
        data,
        embedding_size=128,
        max_iter=20,
        tol=0.0001,
        l2=0.0001
    )

print(f"Character embeddings: {char_embs.shape}")
print(f"Pronunciation embeddings: {phone_embs.shape}")

# Compute character similarity
char_similarity = char_embs @ char_embs.T
print(f"Character similarity matrix: {char_similarity.shape}")

# Find similar characters
char_idx = 0
similarities = char_similarity[char_idx]
top_similar = np.argsort(similarities)[-10:]
print(f"Top similar characters to {char_ids[char_idx]}: {char_ids[top_similar]}")
```

## Algorithm Workflow

1. **Data Filtering**:
   - Remove characters with low dialect coverage
   - Remove dialects with low character coverage
   - Ensure minimum number of dialects and characters

2. **Initialization**:
   - Random initialization of character embeddings
   - Build co-occurrence matrix (characters × dialects)

3. **Alternating Optimization**:
   ```
   for iteration in range(max_iter):
       # Fix phone_embs, solve for char_embs
       char_embs = _solve_char_embs(cooc, phone_embs, ...)

       # Fix char_embs, solve for phone_embs
       phone_embs = _solve_phone_embs(cooc, char_embs, ...)

       # Check convergence
       if loss_change < tol:
           break
   ```

4. **Output**:
   - Character embeddings (dense vectors)
   - Pronunciation embeddings (dense vectors)
   - Metadata (IDs and pronunciation lists)

## Performance Considerations

- **Memory**: O(n_chars × embedding_size + n_phones × embedding_size)
- **Time**: O(max_iter × (n_chars × n_dialects × embedding_size²))
- **Convergence**: Typically converges in 5-15 iterations
- **Regularization**: L2 regularization prevents overfitting

## Innovation Opportunities

### Graph Neural Networks (GNN)

Since the sparse vector s represents an adjacency matrix of a homophony graph, apply **Graph Neural Networks** instead of linear SVD:

```python
import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GraphSAGE

class HomophonyGNN(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.5, training=self.training)
        x = self.conv2(x, edge_index)
        return x

# Build homophony graph
edge_index = build_homophony_edges(data)  # Characters with same pronunciation
x = torch.eye(n_chars)  # Initial features

# Train GNN
model = HomophonyGNN(n_chars, 256, embedding_size)
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

for epoch in range(100):
    optimizer.zero_grad()
    embeddings = model(x, edge_index)
    loss = reconstruction_loss(embeddings, edge_index)
    loss.backward()
    optimizer.step()
```

### Advantages of GNN Approach

1. **Non-linear transformations**: Captures complex phonological patterns
2. **Graph structure**: Explicitly models homophony relationships
3. **Neighborhood aggregation**: Learns from similar characters
4. **Scalability**: Handles large graphs efficiently with mini-batching

### Alternative: Node2Vec

```python
from node2vec import Node2Vec

# Build homophony graph
G = build_homophony_graph(data)

# Train Node2Vec
node2vec = Node2Vec(
    G,
    dimensions=embedding_size,
    walk_length=30,
    num_walks=200,
    workers=4
)

model = node2vec.fit(window=10, min_count=1, batch_words=4)
char_embs = model.wv.vectors
```

## Dependencies

- numpy
- pandas
- scikit-learn
- scipy (for sparse matrices)

## Related Files

- `src/sincomp/factorize.py`: Full implementation
- `src/sincomp/preprocess.py`: Data preprocessing
- `notebooks/encode.ipynb`: Example notebook
- `tests/test_factorize.py`: Unit tests
