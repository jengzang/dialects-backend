# Skill: GLM Dialect Classifier and Isogloss Mapper

## Location
- `src/sincomp/compare.py` - `compliance()` function
- `scripts/dialect_classifier.py` - `train_classifier()` function
- `scripts/isogloss.py` - `isogloss()` function

## Objective
Classify dialects continuously (e.g., predicting probability of being Mandarin) and generate smooth geographical isoglosses using Generalized Linear Models (GLM) and L2-normalized rule conformities.

## Mathematical Foundation

### Rule Conformity (Cosine Similarity)

Conformity to phonological rules quantified using L2-normalized inner products:

```
s(k₁, k₂) = (k₁ᵀ · k₂) / (|k₁|₂ · |k₂|₂)
```

where k₁ and k₂ are pronunciation frequency vectors for two character sets.

### Logistic Regression Classification

```
P(Y=1 | X=x) = σ(wᵀ φ(x) + b)
```

where:
- σ is the sigmoid function
- φ(x) is the feature transformation
- w, b are learned parameters

### Exponential Family Distribution

The conditional distribution p(x|y) is modeled via Exponential Family:
- **Beta distribution**: For bounded continuous features [0, 1]
- **Gaussian distribution**: For unbounded continuous features

## Implementation Details

### Part 1: Rule Compliance Computation

**Location**: `src/sincomp/compare.py`

```python
def load_rules(fname: str, characters: Series = None) -> DataFrame:
    """
    Load phonetic rules from JSON file

    Parameters:
        fname: Path to rules JSON file
        characters: Optional cid to character mapping for display

    Returns:
        rules: DataFrame with columns:
            - id: Rule ID
            - feature: Phonetic feature (initial/final/tone)
            - cid1, cid2: Character sets for comparison
            - char1, char2: Character forms (if characters provided)
    """

def compliance(
    data: DataFrame,
    rules: DataFrame,
    dtype: np.dtype = np.float32,
    norm: int | None = 2
) -> DataFrame:
    """
    Compute dialect compliance with phonetic rules

    Parameters:
        data: Dialect pronunciation data (wide format)
        rules: Phonetic rules DataFrame
        dtype: Data type for computation
        norm: Normalization norm (2 = L2/cosine similarity, None = no normalization)

    Returns:
        similarities: Compliance matrix (n_dialects × n_rules)
            Values in [0, 1], higher = better compliance
    """
```

**Algorithm**:
1. Group rules by phonetic feature (initial/final/tone)
2. One-hot encode pronunciations using `CountVectorizer`
3. For each rule:
   - Extract character sets cid1 and cid2
   - Compute pronunciation frequency vectors k₁ and k₂
   - Calculate cosine similarity: s(k₁, k₂)
4. Return compliance matrix

### Part 2: Dialect Classification

**Location**: `scripts/dialect_classifier.py`

```python
def train_classifier(
    rules: DataFrame,
    annotations: DataFrame,
    resample: int = 0,
    samples: int = 500,
    min_rate: float = 0.5,
    max_rate: float = 0.8
) -> Pipeline:
    """
    Train dialect classifier using rule compliance features

    Parameters:
        rules: Phonetic rules for computing compliance
        annotations: Training data with columns:
            - dataset: Dataset name
            - did: Dialect ID
            - stratify: Optional grouping for cross-validation
            - label: Binary classification label (0/1)
        resample: Number of resampling iterations for data augmentation
        samples: Number of samples per resampling
        min_rate: Minimum sampling rate
        max_rate: Maximum sampling rate

    Returns:
        pipeline: Trained sklearn Pipeline with:
            - KNNImputer: Fill missing values
            - LogisticRegressionCV: L1-regularized logistic regression
    """
```

**Algorithm**:
1. **Feature Extraction**: Compute rule compliance for all dialects
2. **Data Augmentation**: Resample characters to create synthetic training samples
3. **Imputation**: Use KNN to fill missing character data
4. **Cross-Validation**: StratifiedGroupKFold to prevent data leakage
5. **Training**: LogisticRegressionCV with L1 regularization for feature selection
6. **Output**: Trained pipeline that predicts P(dialect belongs to class | features)

### Part 3: Isogloss Mapping

**Location**: `scripts/isogloss.py`

```python
def isogloss(
    data: DataFrame,
    lat: str,
    lon: str,
    val: str,
    name: str = None,
    ax = None,
    proj = ccrs.PlateCarree(),
    background = None,
    background_extent = None,
    geo = None,
    fill: bool = True,
    cmap = None,
    color = None,
    extent = None,
    coverage: float = 1,
    resolution: int = 100,
    levels = np.linspace(0, 1, 11),
    alpha: float = None,
    title: str = None,
    **kwargs
) -> Axes:
    """
    Generate isogloss contour map with geographical background

    Parameters:
        data: DataFrame with dialect locations and values
        lat, lon: Column names for latitude and longitude
        val: Column name for values to plot (e.g., probability)
        proj: Cartopy projection
        background: Background image (e.g., map)
        geo: GeoDataFrame for political boundaries
        fill: Whether to fill contours
        cmap: Colormap name
        levels: Contour levels (default: 0, 0.1, ..., 1.0)
        resolution: Grid resolution for interpolation

    Returns:
        ax: Matplotlib axes with isogloss map
    """
```

**Algorithm**:
1. **Spatial Interpolation**: Interpolate discrete dialect probabilities to continuous grid
2. **Contour Generation**: Create contour lines at specified levels (e.g., 0.25, 0.5, 0.75)
3. **Background Rendering**: Add geographical map and political boundaries
4. **Visualization**: Plot filled contours with colormap

## Usage Example

### Step 1: Define Rules

```json
// rules.json
[
  {
    "id": "rule1",
    "feature": "initial",
    "cid1": ["00001", "00002", "00003"],
    "cid2": ["00010", "00011", "00012"],
    "description": "Voiced initials become voiceless"
  },
  {
    "id": "rule2",
    "feature": "tone",
    "cid1": ["00020", "00021"],
    "cid2": ["00030", "00031"],
    "description": "Tone merging pattern"
  }
]
```

### Step 2: Compute Compliance

```python
import sincomp.datasets
import sincomp.preprocess
import sincomp.compare

# Load data
ccr = sincomp.datasets.get('CCR')
data = sincomp.preprocess.transform(ccr)

# Load rules
rules = sincomp.compare.load_rules('rules.json')

# Compute compliance
compliance_matrix = sincomp.compare.compliance(data, rules)
print(f"Compliance shape: {compliance_matrix.shape}")  # (n_dialects, n_rules)
```

### Step 3: Train Classifier

```python
import pandas as pd
from scripts.dialect_classifier import train_classifier

# Prepare annotations
annotations = pd.DataFrame({
    'dataset': ['CCR'] * 100,
    'did': dialect_ids,
    'label': labels,  # 0 or 1
    'stratify': groups  # For cross-validation
})

# Train classifier
classifier = train_classifier(
    rules=rules,
    annotations=annotations,
    resample=10,
    samples=500
)

# Predict probabilities
probabilities = classifier.predict_proba(compliance_matrix)[:, 1]
```

### Step 4: Generate Isogloss Map

```python
import geopandas as gpd
from scripts.isogloss import isogloss

# Prepare data with coordinates
map_data = pd.DataFrame({
    'lat': latitudes,
    'lon': longitudes,
    'probability': probabilities
})

# Load geographical boundaries
china_map = gpd.read_file('china_provinces.shp')

# Generate isogloss map
fig, ax = plt.subplots(figsize=(12, 10), subplot_kw={'projection': ccrs.PlateCarree()})
isogloss(
    data=map_data,
    lat='lat',
    lon='lon',
    val='probability',
    geo=china_map,
    levels=[0.25, 0.5, 0.75],
    fill=True,
    cmap='RdYlBu_r',
    title='Mandarin Probability Isogloss'
)
plt.savefig('isogloss_map.png', dpi=300, bbox_inches='tight')
```

## Command-line Usage

```bash
# Train dialect classifier
python3 scripts/dialect_classifier.py \
    --rules rules.json \
    --annotations annotations.csv \
    --output classifier.pkl

# Generate isogloss map
python3 scripts/isogloss.py \
    --data dialect_probabilities.csv \
    --rules rules.json \
    --output isogloss_map.png
```

## Key Features

### 1. Active Learning Support

The classifier can be trained with a small set of human-annotated labels:

```python
# Start with small labeled set
initial_labels = get_initial_labels(n=50)

# Train initial classifier
classifier = train_classifier(rules, initial_labels)

# Active learning loop
for iteration in range(10):
    # Predict on unlabeled data
    probabilities = classifier.predict_proba(unlabeled_data)

    # Select most uncertain samples
    uncertainty = np.abs(probabilities[:, 1] - 0.5)
    query_indices = np.argsort(uncertainty)[:10]

    # Get human labels
    new_labels = human_annotate(query_indices)

    # Retrain with expanded dataset
    all_labels = pd.concat([initial_labels, new_labels])
    classifier = train_classifier(rules, all_labels)
```

### 2. Feature Selection via L1 Regularization

LogisticRegressionCV automatically selects most critical linguistic rules:

```python
# Get feature importance
coefficients = classifier.named_steps['logisticregression'].coef_[0]
important_rules = rules.iloc[np.argsort(np.abs(coefficients))[-10:]]
print("Top 10 most important rules:")
print(important_rules[['id', 'description']])
```

### 3. Spatial Interpolation Methods

Multiple interpolation methods available:

```python
from scipy.interpolate import griddata

# Linear interpolation
grid_z = griddata(
    points=(lons, lats),
    values=probabilities,
    xi=(grid_lon, grid_lat),
    method='linear'
)

# Cubic interpolation (smoother)
grid_z = griddata(
    points=(lons, lats),
    values=probabilities,
    xi=(grid_lon, grid_lat),
    method='cubic'
)

# Radial basis function (most flexible)
from scipy.interpolate import Rbf
rbf = Rbf(lons, lats, probabilities, function='multiquadric')
grid_z = rbf(grid_lon, grid_lat)
```

## Innovation Opportunities

### 1. Spatial Autoregressive (SAR) Model

Add geographical continuity constraint to GLM:

```python
import pysal
from pysal.model import spreg

def train_spatial_classifier(X, y, coords, W=None):
    """
    Train classifier with spatial autoregressive term

    Parameters:
        X: Feature matrix
        y: Labels
        coords: Geographical coordinates
        W: Spatial weight matrix (optional)

    Returns:
        model: Spatial logistic regression model
    """
    if W is None:
        # Build spatial weight matrix from coordinates
        W = pysal.lib.weights.DistanceBand.from_array(
            coords,
            threshold=100,  # km
            binary=True
        )

    # Spatial lag model
    model = spreg.GM_Lag(
        y.reshape(-1, 1),
        X,
        W,
        name_y='label',
        name_x=feature_names
    )

    return model
```

### 2. Laplacian Regularization

Add graph-based smoothness penalty:

```python
def laplacian_regularization(W, lambda_reg=0.1):
    """
    Compute Laplacian regularization term

    Parameters:
        W: Spatial weight matrix (n × n)
        lambda_reg: Regularization strength

    Returns:
        L: Laplacian matrix
    """
    # Degree matrix
    D = np.diag(W.sum(axis=1))

    # Graph Laplacian
    L = D - W

    return lambda_reg * L

# Modified loss function
def spatial_loss(w, X, y, L):
    # Standard logistic loss
    logistic_loss = -np.mean(y * np.log(sigmoid(X @ w)) +
                              (1 - y) * np.log(1 - sigmoid(X @ w)))

    # Spatial smoothness penalty
    spatial_penalty = w.T @ L @ w

    return logistic_loss + spatial_penalty
```

### 3. Gaussian Process Classification

Model spatial correlation explicitly:

```python
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF, WhiteKernel

def train_gp_classifier(X, y, coords):
    """
    Train Gaussian Process classifier with spatial kernel

    Parameters:
        X: Feature matrix
        y: Labels
        coords: Geographical coordinates

    Returns:
        gp: Trained GP classifier
    """
    # Spatial kernel (RBF on coordinates)
    spatial_kernel = RBF(length_scale=100.0, length_scale_bounds=(10, 1000))

    # Feature kernel (RBF on features)
    feature_kernel = RBF(length_scale=1.0)

    # Combined kernel
    kernel = spatial_kernel + feature_kernel + WhiteKernel()

    # Train GP
    gp = GaussianProcessClassifier(kernel=kernel, n_restarts_optimizer=10)
    gp.fit(np.hstack([coords, X]), y)

    return gp

# Predict with uncertainty
probabilities, std = gp.predict_proba(test_data), gp.predict_std(test_data)
```

**Advantages**:
- Naturally incorporates spatial correlation
- Provides uncertainty estimates
- Smooth probability surfaces
- Interpretable length scales

## Dependencies

- numpy
- pandas
- scikit-learn >= 1.2
- scipy
- cartopy (for mapping)
- geopandas (for geographical data)
- matplotlib
- joblib

## Related Files

- `src/sincomp/compare.py`: Rule compliance computation
- `scripts/dialect_classifier.py`: Classifier training
- `scripts/isogloss.py`: Isogloss map generation
- `src/sincomp/plot/geography.py`: Geographical plotting utilities
- `tests/test_compare.py`: Unit tests
