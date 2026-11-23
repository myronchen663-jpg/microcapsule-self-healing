from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata
from settings import *
from numerics import seed32

def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exponent = np.exp(shifted)
    return exponent / exponent.sum()

def _dense_test_arrays(test, common_models) -> dict[str, Any]:
    COMMON_MODELS = tuple(common_models)
    test = test.loc[test['model_name'].isin(COMMON_MODELS)].copy()
    endpoint_reverse = {value: key for key, value in ENDPOINT_SOURCE.items()}
    test['endpoint_key'] = test['endpoint'].map(endpoint_reverse)
    if test['endpoint_key'].isna().any():
        raise AssertionError('Unknown test endpoint')
    families = sorted(test['syn_scenario_family_id'].astype(str).unique().tolist())
    if len(families) != 50:
        raise AssertionError('Test family count mismatch')
    family_index = {family: index for index, family in enumerate(families)}
    observed = np.empty((50, len(ENDPOINTS), 10), dtype=np.float64)
    prediction = np.empty((50, len(ENDPOINTS), len(COMMON_MODELS), 10), dtype=np.float64)
    lower = np.empty_like(prediction)
    upper = np.empty_like(prediction)
    row_ids = np.empty((50, 10), dtype='U64')
    for family in families:
        family_rows = sorted(test.loc[test['syn_scenario_family_id'].eq(family), 'syn_row_id'].astype(str).unique().tolist())
        if len(family_rows) != 10:
            raise AssertionError('Test rows-per-family mismatch')
        family_position = family_index[family]
        row_ids[family_position] = family_rows
        for endpoint_position, endpoint in enumerate(ENDPOINTS):
            endpoint_name = ENDPOINT_SOURCE[endpoint]
            for row_position, row_id in enumerate(family_rows):
                subset = test.loc[test['syn_scenario_family_id'].eq(family) & test['syn_row_id'].astype(str).eq(row_id) & test['endpoint'].eq(endpoint_name)].set_index('model_name')
                if set(subset.index) != set(COMMON_MODELS):
                    raise AssertionError('Test model grid mismatch')
                observed_values = subset['observed_syn'].to_numpy(dtype=np.float64)
                if np.max(observed_values) - np.min(observed_values) > 1e-12:
                    raise AssertionError('Observed test endpoint differs by model')
                observed[family_position, endpoint_position, row_position] = observed_values[0]
                for model_position, model in enumerate(COMMON_MODELS):
                    prediction[family_position, endpoint_position, model_position, row_position] = float(subset.loc[model, 'prediction'])
                    lower[family_position, endpoint_position, model_position, row_position] = float(subset.loc[model, 'lower90'])
                    upper[family_position, endpoint_position, model_position, row_position] = float(subset.loc[model, 'upper90'])
    return {'common_models': COMMON_MODELS, 'test': test, 'families': families, 'row_ids': row_ids, 'observed': observed, 'prediction': prediction, 'lower': lower, 'upper': upper}

def _normal_score_correlation(residual: np.ndarray) -> np.ndarray:
    correlations = []
    for endpoint_position in range(len(ENDPOINTS)):
        endpoint_residual = residual[endpoint_position]
        scores = np.empty_like(endpoint_residual)
        n_rows = endpoint_residual.shape[1]
        for model_position in range(endpoint_residual.shape[0]):
            ranks = rankdata(endpoint_residual[model_position], method='average')
            scores[model_position] = norm.ppf((ranks - 0.5) / float(n_rows))
        correlations.append(np.corrcoef(scores))
    return 0.5 * (np.abs(correlations[0]) + np.abs(correlations[1]))

def compute_weights(test_arrays: dict[str, Any]) -> dict[str, Any]:
    COMMON_MODELS = test_arrays['common_models']
    observed = test_arrays['observed']
    prediction = test_arrays['prediction']
    lower = test_arrays['lower']
    upper = test_arrays['upper']
    pre = np.empty((B_WEIGHT, len(COMMON_MODELS)), dtype=np.float64)
    rmse_store = np.empty((B_WEIGHT, len(ENDPOINTS), len(COMMON_MODELS)))
    coverage_store = np.empty_like(rmse_store)
    for bootstrap_index in range(1, B_WEIGHT + 1):
        rng = np.random.default_rng(seed32('weight_bootstrap', bootstrap_index))
        sampled = rng.choice(50, size=50, replace=True)
        observed_b = observed[sampled]
        prediction_b = prediction[sampled]
        lower_b = lower[sampled]
        upper_b = upper[sampled]
        residual = (observed_b[:, :, None, :] - prediction_b).transpose(1, 2, 0, 3).reshape(len(ENDPOINTS), len(COMMON_MODELS), -1)
        rmse = np.sqrt(np.mean(residual ** 2, axis=2))
        coverage = np.mean((observed_b[:, :, None, :] >= lower_b) & (observed_b[:, :, None, :] <= upper_b), axis=(0, 3))
        rmse_store[bootstrap_index - 1] = rmse
        coverage_store[bootstrap_index - 1] = coverage
        relative = rmse / np.min(rmse, axis=1, keepdims=True)
        relative_joint = np.sqrt(relative[0] * relative[1])
        coverage_penalty = 0.5 * np.sum(((coverage - 0.9) / 0.05) ** 2, axis=0)
        quality = -2.0 * np.log(relative_joint) - 0.25 * coverage_penalty
        soft = _softmax(quality)
        rho = _normal_score_correlation(residual)
        redundancy = np.ones(len(COMMON_MODELS), dtype=np.float64)
        for model_position in range(len(COMMON_MODELS)):
            for other_position in range(len(COMMON_MODELS)):
                if other_position == model_position:
                    continue
                redundancy[model_position] += soft[other_position] * np.clip((rho[model_position, other_position] - 0.6) / 0.4, 0.0, 1.0)
        adjusted = soft / redundancy
        adjusted /= adjusted.sum()
        pre[bootstrap_index - 1] = 0.05 + 0.8 * adjusted
    pre_mean = pre.mean(axis=0)
    eta_star = None
    weights = None
    for eta_step in range(1001):
        eta = eta_step / 1000.0
        candidate = (1.0 - eta) * pre_mean + eta / len(COMMON_MODELS)
        n_eff = 1.0 / np.sum(candidate ** 2)
        if float(np.max(candidate)) <= 0.55 and n_eff >= 2.5:
            eta_star = eta
            weights = candidate
            break
    if eta_star is None or weights is None:
        raise AssertionError('Weight equal-blend search failed')
    final_bootstrap = (1.0 - eta_star) * pre + eta_star / len(COMMON_MODELS)
    weight_ci_low = np.quantile(final_bootstrap, 0.025, axis=0)
    weight_ci_high = np.quantile(final_bootstrap, 0.975, axis=0)
    weight_ci_width = weight_ci_high - weight_ci_low
    weight_confidence = float(np.clip(1.0 - np.max(weight_ci_width) / 0.4, 0.0, 1.0))
    full_weights = np.zeros(len(MODELS), dtype=np.float64)
    full_bootstrap = np.zeros((B_WEIGHT, len(MODELS)), dtype=np.float64)
    for common_position, model in enumerate(COMMON_MODELS):
        model_position = MODEL_INDEX[model]
        full_weights[model_position] = weights[common_position]
        full_bootstrap[:, model_position] = final_bootstrap[:, common_position]
    weight_status = 'equal_blend' if eta_star > 0 else 'bootstrap'
    return {'common_models': COMMON_MODELS, 'common_index': np.asarray([MODEL_INDEX[m] for m in COMMON_MODELS], dtype=np.int64), 'weights': full_weights, 'weight_bootstrap': full_bootstrap, 'weight_status': weight_status, 'eta_star': float(eta_star), 'n_eff': float(1.0 / np.sum(weights ** 2)), 'weight_ci_low': weight_ci_low, 'weight_ci_high': weight_ci_high, 'weight_ci_width': weight_ci_width, 'weight_confidence': weight_confidence, 'bootstrap_rmse': rmse_store, 'bootstrap_coverage': coverage_store}

def _ece10(probability: np.ndarray, label: np.ndarray, family: np.ndarray, row_id: np.ndarray) -> float:
    order = np.lexsort((row_id.astype(str), family.astype(str), probability))
    probability_sorted = probability[order]
    label_sorted = label[order]
    if len(probability_sorted) % 10 != 0:
        raise AssertionError('ECE equal-frequency bins require a multiple of ten')
    width = len(probability_sorted) // 10
    return float(np.mean([abs(probability_sorted[start:start + width].mean() - label_sorted[start:start + width].mean()) for start in range(0, len(probability_sorted), width)]))

def _auc_regularized(probability: np.ndarray, label: np.ndarray) -> float:
    positive = label.astype(bool)
    n_positive = int(positive.sum())
    n_negative = int(len(label) - n_positive)
    if n_positive * n_negative == 0:
        return 0.5
    ranks = rankdata(probability, method='average')
    concordant_plus_half_ties = float(ranks[positive].sum() - n_positive * (n_positive + 1) / 2.0)
    return float((concordant_plus_half_ties + 0.5) / (n_positive * n_negative + 1.0))

def _point_metrics(probability: np.ndarray, label: np.ndarray, family: np.ndarray, row_id: np.ndarray, reference_brier: float) -> dict[str, float]:
    clipped = np.clip(probability, EPS_CAL, 1.0 - EPS_CAL)
    brier = float(np.mean((clipped - label) ** 2))
    nll = float(-np.mean(label * np.log(clipped) + (1.0 - label) * np.log1p(-clipped)))
    return {'brier': brier, 'ece10': _ece10(clipped, label, family, row_id), 'nll': nll, 'bss': float(1.0 - brier / reference_brier), 'auc_reg': _auc_regularized(clipped, label)}

def _base_grade(score: np.ndarray, probability: np.ndarray, lower: np.ndarray, width: np.ndarray) -> np.ndarray:
    output = np.full(len(score), 'D', dtype='U1')
    c_mask = (score >= 40.0) & (probability >= 0.3)
    output[c_mask] = 'C'
    b_mask = (score >= 60.0) & (probability >= 0.6) & (lower >= 0.4) & (width <= 0.35)
    output[b_mask] = 'B'
    a_mask = (score >= 75.0) & (probability >= 0.75) & (lower >= 0.6) & (width <= 0.25)
    output[a_mask] = 'A'
    return output
