# Skill: Proto-Language Reconstruction via Decision Tree Autoencoder

## Implementation

**Source Code**: `reference/recon.py`

Key functions/classes: reconstruct(), impute(), denoise(), get_syllables()

## Objective
Reconstruct proto-language phonological categories (ancestral sound system) from modern dialect pronunciations using decision tree-based autoencoders for denoising and clustering, combined with logistic regression for missing value imputation.

## Mathematical Foundation

### Decision Tree Autoencoder

A decision tree acts as an autoencoder by:
1. **Encoding**: Map input to leaf nodes (latent representation)
2. **Decoding**: Reconstruct input from leaf node predictions

```
input → tree.apply(input) → leaf_id → tree.predict(input) → reconstructed
```

Each leaf node represents a proto-language phonological category.

### Entropy-based Splitting

Decision tree uses entropy criterion for splitting:
```
H(S) = -Σ p_i log₂(p_i)
Information Gain = H(parent) - Σ (|S_child| / |S_parent|) × H(S_child)
```

Split only if information gain > `min_impurity_decrease`.

### Iterative Imputation

Uses MICE (Multivariate Imputation by Chained Equations):
```
For each feature with missing values:
    1. Predict using other features (logistic regression)
    2. Update feature values
    3. Repeat until convergence
```

## Implementation Details

### Core Functions

```python
def impute(data: DataFrame) -> DataFrame:
    """
    Fill missing pronunciations using iterative imputation

    Algorithm:
    1. Convert strings to categorical codes
    2. Use IterativeImputer with LogisticRegression
    3. Convert codes back to strings

    Parameters:
        data: Pronunciation data with missing values

    Returns:
        imputed: Complete pronunciation data
    """

def denoise(data: DataFrame) -> tuple[Pipeline, DataFrame, ndarray]:
    """
    Denoise data using decision tree autoencoder

    Algorithm:
    1. One-hot encode pronunciations
    2. Train DecisionTreeClassifier to predict itself
    3. Reconstruct data from tree predictions
    4. Return tree, reconstructed data, and leaf assignments

    Parameters:
        data: Pronunciation data

    Returns:
        pipeline: Trained encoder-decoder pipeline
        reconstructed: Denoised data
        leaf_ids: Leaf node assignments (clustering)
    """

def get_syllables(data: DataFrame, labels: ndarray) -> DataFrame:
    """
    Extract proto-language syllable table from clustering

    Each leaf node = one proto-language syllable
    Aggregate modern reflexes by frequency

    Parameters:
        data: Modern dialect pronunciations
        labels: Leaf node assignments from decision tree

    Returns:
        syllables: Proto-language syllable table with:
            - Representative pronunciation per dialect
            - Frequency distribution of reflexes
    """

def reconstruct(
    data: DataFrame,
    min_sample: int = 3,
    initial_mid: float = 0.002,
    final_mid: float = 0.002,
    tone_mid: float = 0.01
) -> tuple[DataFrame, ndarray, ndarray, ndarray]:
    """
    Reconstruct proto-language initial/final/tone categories

    Trains separate decision trees for each component:
    - Initial tree: reconstructs proto-initials
    - Final tree: reconstructs proto-finals
    - Tone tree: reconstructs proto-tones

    Parameters:
        data: Modern dialect pronunciations
        min_sample: Minimum samples per leaf
        initial_mid: Min impurity decrease for initials
        final_mid: Min impurity decrease for finals
        tone_mid: Min impurity decrease for tones

    Returns:
        reconstructed: Reconstructed pronunciations
        initial_labels: Proto-initial categories
        final_labels: Proto-final categories
        tone_labels: Proto-tone categories
    """
```

### Algorithm Workflow

```
Input: Modern dialect pronunciations (with missing values)

Phase 1: Data Preparation
├─ Impute missing values (IterativeImputer + LogisticRegression)
└─ One-hot encode all pronunciations

Phase 2: Denoising (Optional)
├─ Train decision tree autoencoder
├─ Reconstruct data (removes noise)
└─ Extract leaf assignments (proto-syllables)

Phase 3: Component-wise Reconstruction
├─ Train initial tree (min_impurity_decrease=0.002)
│  └─ Each leaf = one proto-initial
├─ Train final tree (min_impurity_decrease=0.002)
│  └─ Each leaf = one proto-final
└─ Train tone tree (min_impurity_decrease=0.01)
   └─ Each leaf = one proto-tone

Phase 4: Syllable Table Generation
├─ Group by proto-categories
├─ Aggregate modern reflexes
└─ Compute frequency distributions

Output: Proto-language phonological system
```

## Usage Example

### Basic Reconstruction

```python
import pandas as pd
import sincomp.datasets
import sincomp.preprocess as prep
from scripts.recon import impute, denoise, reconstruct, get_syllables

# Load dataset
ccr = sincomp.datasets.get('CCR')

# Transform to wide format
wide = prep.transform(
    ccr,
    index='cid',
    columns='did',
    values=['initial', 'final', 'tone']
)

# Step 1: Impute missing values
imputed = impute(wide)
print(f"Missing values: {(wide == '').sum().sum()} → {(imputed == '').sum().sum()}")

# Step 2: Reconstruct proto-language
reconstructed, initial_labels, final_labels, tone_labels = reconstruct(
    imputed,
    min_sample=5,
    initial_mid=0.002,
    final_mid=0.002,
    tone_mid=0.01
)

# Step 3: Extract proto-syllables
syllables = get_syllables(reconstructed, initial_labels)
print(f"Proto-syllables: {len(syllables)}")
print(syllables.head())
```

### Denoising Only

```python
# Denoise without full reconstruction
pipeline, denoised, leaf_ids = denoise(imputed)

# Analyze clustering
n_clusters = len(np.unique(leaf_ids))
print(f"Number of proto-syllables: {n_clusters}")

# Visualize cluster sizes
cluster_sizes = pd.Series(leaf_ids).value_counts()
print(cluster_sizes.describe())
```

### Component-wise Analysis

```python
# Reconstruct with different parameters for each component
reconstructed, i_labels, f_labels, t_labels = reconstruct(
    imputed,
    min_sample=3,
    initial_mid=0.001,  # More fine-grained initials
    final_mid=0.005,    # Coarser finals
    tone_mid=0.02       # Coarsest tones
)

# Analyze proto-categories
print(f"Proto-initials: {len(np.unique(i_labels))}")
print(f"Proto-finals: {len(np.unique(f_labels))}")
print(f"Proto-tones: {len(np.unique(t_labels))}")

# Cross-tabulate
proto_system = pd.DataFrame({
    'initial': i_labels,
    'final': f_labels,
    'tone': t_labels
})
print(proto_system.value_counts())
```

### Frequency Analysis

```python
def analyze_reflexes(data, labels, dialect='Beijing'):
    """
    Analyze how proto-categories are reflected in modern dialect
    """
    reflex_table = pd.DataFrame({
        'proto': labels,
        'modern': data.loc[:, (dialect, 'initial')]
    })

    # Count reflexes
    reflexes = reflex_table.groupby('proto')['modern'].value_counts()
    print(f"Reflexes in {dialect}:")
    print(reflexes.head(20))

    # Regularity: proportion of most common reflex
    regularity = reflexes.groupby(level=0).max() / reflexes.groupby(level=0).sum()
    print(f"\nMean regularity: {regularity.mean():.2%}")

# Analyze
analyze_reflexes(reconstructed, initial_labels, 'Beijing')
```

## Hyperparameter Tuning

### Grid Search for Optimal Parameters

```python
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import silhouette_score

def tune_reconstruction(data):
    """
    Find optimal min_impurity_decrease values
    """
    param_grid = {
        'initial_mid': [0.0005, 0.001, 0.002, 0.005],
        'final_mid': [0.001, 0.002, 0.005, 0.01],
        'tone_mid': [0.005, 0.01, 0.02, 0.05]
    }

    best_score = -np.inf
    best_params = None

    for i_mid in param_grid['initial_mid']:
        for f_mid in param_grid['final_mid']:
            for t_mid in param_grid['tone_mid']:
                recon, i_lab, f_lab, t_lab = reconstruct(
                    data,
                    initial_mid=i_mid,
                    final_mid=f_mid,
                    tone_mid=t_mid
                )

                # Evaluate using silhouette score
                features = encode_features(data)
                score = silhouette_score(features, i_lab)

                if score > best_score:
                    best_score = score
                    best_params = (i_mid, f_mid, t_mid)

    print(f"Best parameters: {best_params}")
    print(f"Best score: {best_score:.3f}")
    return best_params
```

## Evaluation Metrics

### 1. Reconstruction Accuracy

```python
def reconstruction_accuracy(original, reconstructed):
    """
    Measure how well reconstruction preserves original data
    """
    accuracy = (original == reconstructed).mean().mean()
    return accuracy

acc = reconstruction_accuracy(imputed, reconstructed)
print(f"Reconstruction accuracy: {acc:.2%}")
```

### 2. Cluster Quality

```python
from sklearn.metrics import silhouette_score, davies_bouldin_score

def evaluate_clustering(features, labels):
    """
    Evaluate proto-category clustering quality
    """
    silhouette = silhouette_score(features, labels)
    davies_bouldin = davies_bouldin_score(features, labels)

    print(f"Silhouette score: {silhouette:.3f} (higher is better)")
    print(f"Davies-Bouldin index: {davies_bouldin:.3f} (lower is better)")

# Evaluate
features = encode_features(imputed)
evaluate_clustering(features, initial_labels)
```

### 3. Linguistic Plausibility

```python
def check_sound_changes(proto_labels, modern_data):
    """
    Check if reconstructed sound changes are linguistically plausible

    Common sound change patterns:
    - Voicing/devoicing
    - Palatalization
    - Lenition
    - Tone splits
    """
    changes = []

    for proto_cat in np.unique(proto_labels):
        mask = proto_labels == proto_cat
        modern_forms = modern_data[mask].value_counts()

        # Check for systematic patterns
        if len(modern_forms) > 1:
            changes.append({
                'proto': proto_cat,
                'reflexes': modern_forms.to_dict(),
                'regularity': modern_forms.iloc[0] / modern_forms.sum()
            })

    return pd.DataFrame(changes)

# Analyze
sound_changes = check_sound_changes(initial_labels, imputed.loc[:, ('Beijing', 'initial')])
print(sound_changes.sort_values('regularity', ascending=False))
```

## Innovation Opportunities

### 1. Neural Autoencoder

Replace decision tree with neural network:

```python
import torch
import torch.nn as nn

class NeuralProtoReconstructor(nn.Module):
    def __init__(self, input_dim, latent_dim=50):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, input_dim)
        )

    def forward(self, x):
        latent = self.encoder(x)
        reconstructed = self.decoder(latent)
        return reconstructed, latent

# Training
model = NeuralProtoReconstructor(input_dim, latent_dim=50)
optimizer = torch.optim.Adam(model.parameters())
criterion = nn.MSELoss()

for epoch in range(100):
    reconstructed, latent = model(features)
    loss = criterion(reconstructed, features)
    loss.backward()
    optimizer.step()

# Extract proto-categories via clustering
from sklearn.cluster import KMeans
proto_labels = KMeans(n_clusters=50).fit_predict(latent.detach().numpy())
```

**Advantages**:
- Non-linear transformations
- Continuous latent space
- Better generalization

### 2. Variational Autoencoder (VAE)

Add probabilistic interpretation:

```python
class VAEProtoReconstructor(nn.Module):
    def __init__(self, input_dim, latent_dim=50):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU()
        )
        self.fc_mu = nn.Linear(128, latent_dim)
        self.fc_logvar = nn.Linear(128, latent_dim)

        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, input_dim)
        )

    def encode(self, x):
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_logvar(h)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        return self.decoder(z), mu, logvar

# VAE loss
def vae_loss(recon_x, x, mu, logvar):
    recon_loss = F.mse_loss(recon_x, x, reduction='sum')
    kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    return recon_loss + kl_loss
```

**Advantages**:
- Uncertainty quantification
- Smooth latent space
- Generative model (can sample proto-forms)

### 3. Phylogenetic Tree Integration

Incorporate known phylogenetic relationships:

```python
def phylogenetic_reconstruction(data, tree_structure):
    """
    Reconstruct proto-language respecting phylogenetic tree

    Algorithm:
    1. Reconstruct internal nodes bottom-up
    2. Use Fitch algorithm for parsimony
    3. Constrain reconstruction to tree topology
    """
    # Fitch algorithm
    def fitch_upward(node):
        if node.is_leaf():
            return {node.pronunciation}
        else:
            left_set = fitch_upward(node.left)
            right_set = fitch_upward(node.right)
            intersection = left_set & right_set
            return intersection if intersection else left_set | right_set

    def fitch_downward(node, parent_set):
        if node.is_leaf():
            return
        node_set = fitch_upward(node)
        if parent_set & node_set:
            node.pronunciation = min(parent_set & node_set)
        else:
            node.pronunciation = min(node_set)
        fitch_downward(node.left, node_set)
        fitch_downward(node.right, node_set)

    # Reconstruct
    root_set = fitch_upward(tree_structure.root)
    tree_structure.root.pronunciation = min(root_set)
    fitch_downward(tree_structure.root, root_set)

    return tree_structure
```

### 4. Multi-level Reconstruction

Reconstruct multiple time depths:

```python
def multi_level_reconstruction(data, time_depths=[100, 500, 1000, 2000]):
    """
    Reconstruct proto-languages at multiple time depths

    Uses hierarchical clustering with different thresholds
    """
    reconstructions = {}

    for depth in time_depths:
        # Adjust min_impurity_decrease based on time depth
        mid = 0.001 * (depth / 1000)

        recon, labels = reconstruct(
            data,
            initial_mid=mid,
            final_mid=mid,
            tone_mid=mid * 5
        )

        reconstructions[depth] = {
            'data': recon,
            'labels': labels,
            'n_categories': len(np.unique(labels))
        }

    return reconstructions

# Visualize time depth vs. number of categories
depths = [100, 500, 1000, 2000]
n_cats = [reconstructions[d]['n_categories'] for d in depths]
plt.plot(depths, n_cats)
plt.xlabel('Time depth (years)')
plt.ylabel('Number of proto-categories')
plt.title('Proto-language complexity over time')
```

## Dependencies

- numpy
- pandas
- scikit-learn
- scipy
- joblib

## Related Files

- `scripts/recon.py`: Full implementation
- `src/sincomp/preprocess.py`: Data preprocessing
- `src/sincomp/auxiliary.py`: Helper functions
- `notebooks/encode.ipynb`: Example notebook

## Linguistic Interpretation

### Proto-Category Interpretation

Each leaf node in the decision tree represents a proto-phonological category. The interpretation:

1. **Proto-Initial**: Ancestral consonant category
   - Example: *p, *pʰ, *b (voiceless, aspirated, voiced stops)

2. **Proto-Final**: Ancestral rhyme category
   - Example: *-an, *-ang, *-am (different nasal codas)

3. **Proto-Tone**: Ancestral tone category
   - Example: *1, *2, *3, *4 (level, rising, departing, entering)

### Sound Change Patterns

The reconstruction reveals systematic sound changes:

```python
# Example: Voicing contrast lost in Mandarin
Proto: *b, *p, *pʰ
Modern Mandarin: p, p, pʰ (merger of *b and *p)

# Example: Tone split conditioned by voicing
Proto: *1 (level tone)
Modern: 1 (after voiceless), 2 (after voiced)
```

This skill enables historical-comparative linguistics research and dialect classification based on shared innovations.
