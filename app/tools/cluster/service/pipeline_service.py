"""
Cluster execution pipeline services.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from app.tools.cluster.config import DIST_EPSILON


def choose_execution_space(algorithm: str) -> str:
    if algorithm not in {"kmeans", "gmm"}:
        return "distance_matrix"
    return "embedded_distance"


def classical_mds(distance_matrix: np.ndarray, n_components: int) -> np.ndarray:
    size = distance_matrix.shape[0]
    if size <= 1:
        return np.zeros((size, 1), dtype=float)

    squared = distance_matrix ** 2
    centering = np.eye(size) - np.ones((size, size)) / size
    gram = -0.5 * centering @ squared @ centering
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    positive = eigenvalues > DIST_EPSILON
    eigenvalues = eigenvalues[positive][:n_components]
    eigenvectors = eigenvectors[:, positive][:, :n_components]
    if eigenvalues.size == 0:
        return np.zeros((size, n_components), dtype=float)
    return eigenvectors * np.sqrt(eigenvalues)


def prepare_feature_space(matrix: np.ndarray) -> np.ndarray:
    if matrix.shape[0] <= 1:
        return matrix

    scaler = StandardScaler()
    transformed = scaler.fit_transform(matrix)
    if transformed.size == 0 or np.allclose(np.var(transformed, axis=0), 0.0):
        return transformed
    if transformed.shape[1] > 24 and transformed.shape[0] > 3:
        max_components = min(24, transformed.shape[0] - 1, transformed.shape[1])
        if max_components >= 2:
            from sklearn.decomposition import PCA

            transformed = PCA(n_components=max_components, random_state=42).fit_transform(
                transformed
            )
    return transformed


def run_agglomerative(
    distance_matrix: np.ndarray,
    n_clusters: int,
    linkage: str,
) -> np.ndarray:
    if linkage == "ward":
        raise ValueError("agglomerative linkage 'ward' is not supported for distance matrices")
    try:
        model = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric="precomputed",
            linkage=linkage,
        )
    except TypeError:
        model = AgglomerativeClustering(
            n_clusters=n_clusters,
            affinity="precomputed",
            linkage=linkage,
        )
    return model.fit_predict(distance_matrix)


def run_dbscan(distance_matrix: np.ndarray, eps: float, min_samples: int) -> np.ndarray:
    model = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    return model.fit_predict(distance_matrix)


def run_kmeans(
    matrix: np.ndarray,
    n_clusters: int,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = model.fit_predict(matrix)
    centroid_distance = np.linalg.norm(matrix - model.cluster_centers_[labels], axis=1)
    return labels, centroid_distance


def run_gmm(
    matrix: np.ndarray,
    n_clusters: int,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    model = GaussianMixture(n_components=n_clusters, random_state=random_state)
    labels = model.fit_predict(matrix)
    membership = model.predict_proba(matrix).max(axis=1)
    return labels, membership


def compute_metrics(
    labels: np.ndarray,
    execution_matrix: Optional[np.ndarray] = None,
    distance_matrix: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    unique_labels = sorted(label for label in set(labels.tolist()) if label != -1)
    if len(unique_labels) < 2:
        return metrics

    if distance_matrix is not None:
        try:
            metrics["silhouette_score"] = float(
                silhouette_score(distance_matrix, labels, metric="precomputed")
            )
        except Exception:
            pass

    if execution_matrix is None and distance_matrix is not None:
        execution_matrix = classical_mds(
            distance_matrix,
            n_components=min(8, max(distance_matrix.shape[0] - 1, 1)),
        )

    if execution_matrix is not None:
        try:
            if "silhouette_score" not in metrics:
                metrics["silhouette_score"] = float(
                    silhouette_score(execution_matrix, labels)
                )
        except Exception:
            pass
        try:
            metrics["davies_bouldin_index"] = float(
                davies_bouldin_score(execution_matrix, labels)
            )
        except Exception:
            pass
        try:
            metrics["calinski_harabasz_score"] = float(
                calinski_harabasz_score(execution_matrix, labels)
            )
        except Exception:
            pass

    return metrics
