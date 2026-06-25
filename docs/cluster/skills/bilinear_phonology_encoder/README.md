# Skill: Bilinear Phonology Encoder

## Implementation

**Source Code**: `reference/models.py`

This skill contains the complete implementation of the bilinear phonology encoder, including:
- `Processor` class: Feature encoding (lines 21-135)
- `EncoderBase` class: Base encoder architecture (lines 138-450)
- `BilinearEncoder` class: Bilinear transformation implementation (lines 612-665)

## Objective
Map discrete, high-dimensional, sparse dialect pronunciation data into low-dimensional, dense continuous vectors (embeddings) by decoupling pronunciation generation into a bilinear interaction between dialect-specific transformations and character-specific latent representations.

## Mathematical Foundation

The pronunciation of character n in dialect m is modeled as a residual fitting via bilinear transformation:

```
z̃_mnk = α_mi · t_ijk · z_nj + z_nk
```

where:
- `α_mi` is the dialect embedding
- `z_nj` is the character embedding
- `t_ijk` is a shared transformation tensor

The final prediction probability `y_mnol` for phonological features (initial, final, tone) uses Softmax:

```
y_mnol = σ(w_olk · z̃_mnk + b_ol)
```

## Implementation Details

### Core Classes

**`Processor` class**: Encodes dialect/character/target features to integer IDs
- Uses `sklearn.preprocessing.OrdinalEncoder`
- Handles missing values (ID=0) and unknown values
- Methods: `encode_dialect()`, `encode_char()`, `encode_target()`

**`EncoderBase` class**: Base encoder with embedding layers
- Dialect embeddings: `dialect_embs` (list of tf.Variable)
- Character embeddings: `char_embs` (list of tf.Variable)
- Target embeddings: `target_embs` (list of tf.Variable)
- Optional target biases

**`BilinearEncoder` class**: Implements bilinear transformation
- Inherits from `EncoderBase`
- Weight tensor: shape `(dialect_emb_size, char_emb_size, output_emb_size)`
- Supports residual connections when `residual=True`

### Key Functions

```python
def encode_dialect(dialects: tf.Tensor) -> tf.Tensor:
    """Converts dialect features to embeddings"""

def encode_char(chars: tf.Tensor) -> tf.Tensor:
    """Converts character features to embeddings"""

def transform(dialect_emb: tf.Tensor, char_emb: tf.Tensor) -> tf.Tensor:
    """Applies bilinear transformation: output = dialect_emb @ weight @ char_emb"""
    # Implementation: tf.tensordot(dialect_emb, self.weight, axes=[[-1], [0]])

def decode(output_emb: tf.Tensor) -> list[tf.Tensor]:
    """Projects output embeddings to pronunciation predictions"""

def loss(dialects, chars, targets, train=False) -> tuple[tf.Tensor, tf.Tensor]:
    """Computes cross-entropy loss and accuracy"""

def train(optimizer, data, target_weights=None) -> tuple[tf.Tensor, tf.Tensor]:
    """Training loop with gradient descent"""
```

## Usage Example

```python
import sincomp.models
import tensorflow as tf

# Create processor
processor = sincomp.models.Processor(
    dialect_vocabs=[dialect_ids],
    char_vocabs=[char_ids],
    target_vocabs=[initial_list, final_list, tone_list]
)

# Create bilinear encoder
encoder = sincomp.models.BilinearEncoder(
    dialect_vocab_sizes=processor.dialect_vocab_sizes,
    char_vocab_sizes=processor.char_vocab_sizes,
    target_vocab_sizes=processor.target_vocab_sizes,
    dialect_emb_size=20,
    char_emb_size=20,
    output_emb_size=20,
    residual=True
)

# Encode data
dialect_ids, char_ids, target_ids = processor(dialects, chars, targets)

# Train
optimizer = tf.optimizers.Adam(learning_rate=0.001)
loss, acc = encoder.train(optimizer, dataset)
```

## Innovation Opportunities

Replace the linear residual transformation with **Multi-Head Attention** mechanism. This would allow the model to capture non-linear phonological dependencies (e.g., how tone conditionally affects initial consonant voicing), which the original author noted was a limitation of linear models.

### Proposed Enhancement

```python
class AttentionBilinearEncoder(EncoderBase):
    def __init__(self, *args, num_heads=4, **kwargs):
        super().__init__(*args, **kwargs)
        self.attention = tf.keras.layers.MultiHeadAttention(
            num_heads=num_heads,
            key_dim=self.char_emb_size
        )

    def transform(self, dialect_emb, char_emb):
        # Use dialect as query, character as key/value
        attended = self.attention(
            query=dialect_emb[:, None, :],
            key=char_emb[:, None, :],
            value=char_emb[:, None, :]
        )
        return tf.squeeze(attended, axis=1)
```

## Dependencies

- TensorFlow >= 2.8
- scikit-learn >= 1.2
- numpy
- pandas

## Related Files

- `src/sincomp/models.py`: Full implementation
- `scripts/model.py`: Training script
- `tests/test_models.py`: Unit tests
