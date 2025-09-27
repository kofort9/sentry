"""Population Stability Index and Jensen-Shannon divergence calculations."""

from typing import Literal, Tuple

import numpy as np


def bin_counts(
    series: np.ndarray, bins: int = 100, strategy: Literal["quantile", "equal"] = "quantile"
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Bin a series into histogram counts.

    Args:
        series: Input data to bin
        bins: Number of bins
        strategy: "quantile" for equal-sized bins, "equal" for equal-width bins

    Returns:
        Tuple of (bin_edges, counts)
    """
    if strategy == "quantile":
        # Equal-sized bins based on quantiles
        bin_edges = np.percentile(series, np.linspace(0, 100, bins + 1))
        # Remove duplicates and ensure monotonic
        bin_edges = np.unique(bin_edges)
        if len(bin_edges) < 2:
            bin_edges = np.array([series.min(), series.max()])
    else:
        # Equal-width bins
        bin_edges = np.linspace(series.min(), series.max(), bins + 1)

    counts, _ = np.histogram(series, bins=bin_edges)
    return bin_edges, counts


def population_stability_index(
    baseline_counts: np.ndarray, new_counts: np.ndarray, epsilon: float = 1e-6
) -> float:
    """
    Calculate Population Stability Index between two distributions.

    PSI = sum((new - base) * ln(new/base))

    Args:
        baseline_counts: Baseline distribution counts
        new_counts: New distribution counts
        epsilon: Small value to avoid log(0)

    Returns:
        PSI value (higher = more drift)
    """
    # Convert counts to percentages
    baseline_total = np.sum(baseline_counts)
    new_total = np.sum(new_counts)

    if baseline_total == 0 or new_total == 0:
        return 0.0

    baseline_pct = baseline_counts / baseline_total
    new_pct = new_counts / new_total

    # Add epsilon to avoid log(0)
    baseline_pct = np.maximum(baseline_pct, epsilon)
    new_pct = np.maximum(new_pct, epsilon)

    # Calculate PSI
    psi = np.sum((new_pct - baseline_pct) * np.log(new_pct / baseline_pct))

    return float(psi)


def jensen_shannon(p: np.ndarray, q: np.ndarray, epsilon: float = 1e-6) -> float:
    """
    Calculate Jensen-Shannon divergence between two distributions.

    JS = 0.5 * KL(p||m) + 0.5 * KL(q||m)
    where m = 0.5 * (p + q)

    Args:
        p: First distribution
        q: Second distribution
        epsilon: Small value to avoid log(0)

    Returns:
        JS divergence (0-1, higher = more different)
    """
    # Normalize distributions
    p = p / np.sum(p) if np.sum(p) > 0 else p
    q = q / np.sum(q) if np.sum(q) > 0 else q

    # Add epsilon to avoid log(0)
    p = np.maximum(p, epsilon)
    q = np.maximum(q, epsilon)

    # Calculate mixture
    m = 0.5 * (p + q)
    m = np.maximum(m, epsilon)

    # Calculate KL divergences
    kl_pm = np.sum(p * np.log(p / m))
    kl_qm = np.sum(q * np.log(q / m))

    # Jensen-Shannon divergence
    js = 0.5 * kl_pm + 0.5 * kl_qm

    return float(js)
