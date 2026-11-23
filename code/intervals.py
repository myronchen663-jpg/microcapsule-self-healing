from __future__ import annotations
from typing import Any
import numpy as np
class IntervalCalibrator:

    def __init__(self, level: float=0.9) -> None:
        if not 0.0 < level < 1.0:
            raise ValueError('level must be in (0, 1)')
        self.level = float(level)
        self.quantile_: float | None = None
        self.normalized_: bool = False
        self.n_calibration_: int = 0

    def fit(self, y_true: np.ndarray, prediction: np.ndarray, predictive_scale: np.ndarray | None=None) -> 'IntervalCalibrator':
        y = np.asarray(y_true, dtype=float)
        centre = np.asarray(prediction, dtype=float)
        if len(y) == 0 or len(y) != len(centre):
            raise ValueError('Calibration arrays must be non-empty and aligned')
        residual = np.abs(y - centre)
        scores = residual
        self.normalized_ = False
        if predictive_scale is not None:
            scale = np.asarray(predictive_scale, dtype=float)
            valid = np.isfinite(scale) & (scale > 1e-08)
            if valid.mean() >= 0.8:
                scores = residual[valid] / scale[valid]
                self.normalized_ = True
        n = len(scores)
        self.n_calibration_ = int(n)
        finite_sample_level = min(1.0, np.ceil((n + 1) * self.level) / n)
        self.quantile_ = float(np.quantile(scores, finite_sample_level, method='higher'))
        return self

    def interval(self, prediction: np.ndarray, predictive_scale: np.ndarray | None=None) -> tuple[np.ndarray, np.ndarray]:
        if self.quantile_ is None:
            raise RuntimeError('Calibrator is not fitted')
        centre = np.asarray(prediction, dtype=float)
        if self.normalized_:
            if predictive_scale is None:
                raise ValueError('This calibrator requires predictive scale')
            radius = self.quantile_ * np.maximum(np.asarray(predictive_scale, dtype=float), 1e-08)
        else:
            radius = np.full_like(centre, self.quantile_)
        return (centre - radius, centre + radius)

def distribution_scale(draws: np.ndarray) -> np.ndarray:
    values = np.asarray(draws, dtype=float)
    if values.ndim != 2:
        raise ValueError('draws must have shape (draw, row)')
    return np.maximum(np.std(values, axis=0, ddof=1), 1e-08)

def _family_split_and_subsample(groups: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels = np.asarray(groups).astype(str)
    families = np.array(sorted(set(labels.tolist())))
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(families))
    n_fit = len(families) // 2
    fit_families = families[order[:n_fit]]
    eval_families = families[order[n_fit:]]
    subsample: list[int] = []
    for family in sorted(fit_families.tolist()):
        rows = np.where(labels == family)[0]
        subsample.append(int(rng.choice(rows)))
    fit_mask = np.isin(labels, fit_families)
    eval_mask = np.isin(labels, eval_families)
    return (np.asarray(subsample, dtype=int), fit_mask, eval_mask)
