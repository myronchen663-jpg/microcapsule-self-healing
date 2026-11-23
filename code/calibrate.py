from __future__ import annotations
import math
import json
from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import ensemble as base_engine
from settings import *
from numerics import seed32, weighted_empirical_quantiles, deterministic_rank
RIDGES=(math.inf,8.0,4.0,2.0,1.0)
LAMBDA_GRID=np.asarray((0.0,0.25,0.5,0.75,1.0), dtype=np.float64)
TAU=np.asarray((0.002,0.005,0.005,0.005,0.010,0.005,0.010))

def _sigmoid(value: np.ndarray) -> np.ndarray:
    z = np.asarray(value, dtype=np.float64)
    output = np.empty_like(z)
    positive = z >= 0.0
    output[positive] = 1.0 / (1.0 + np.exp(-z[positive]))
    exponent = np.exp(z[~positive])
    output[~positive] = exponent / (1.0 + exponent)
    return output

def _features(probability: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=np.float64), EPS_CAL, 1.0 - EPS_CAL)
    return np.column_stack((np.ones(len(p), dtype=np.float64), np.log(p), -np.log1p(-p)))

def _fit_beta_calibrator(probability: np.ndarray, label: np.ndarray, ridge: float) -> dict[str, Any]:
    x = _features(probability)
    y = np.asarray(label, dtype=np.float64)
    center = np.asarray((0.0, 1.0, 1.0), dtype=np.float64)

    def objective(theta: np.ndarray) -> tuple[float, np.ndarray]:
        linear = x @ theta
        loss = float(np.logaddexp(0.0, linear).sum() - np.dot(y, linear))
        difference = theta - center
        loss += float(ridge * np.dot(difference, difference))
        gradient = x.T @ (_sigmoid(linear) - y) + 2.0 * ridge * difference
        return (loss, np.asarray(gradient, dtype=np.float64))
    result = minimize(fun=lambda theta: objective(theta)[0], x0=center.copy(), jac=lambda theta: objective(theta)[1], method='L-BFGS-B', bounds=((-10.0, 10.0), (0.0, 10.0), (0.0, 10.0)), options={'maxiter': 500, 'ftol': 1e-12, 'gtol': 1e-08})
    theta = np.asarray(result.x, dtype=np.float64)
    finite = bool(np.isfinite(theta).all() and math.isfinite(float(result.fun)))
    return {'success': bool(result.success and finite), 'theta': theta, 'objective': float(result.fun) if finite else math.inf, 'iterations': int(result.nit), 'status_code': int(result.status), 'message': str(result.message), 'gradient_max_abs': float(np.max(np.abs(result.jac))) if finite else math.inf}

def _apply_map(probability: np.ndarray, theta: np.ndarray, lambda_mix: float) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=np.float64), EPS_CAL, 1.0 - EPS_CAL)
    calibrated = _sigmoid(_features(p) @ np.asarray(theta, dtype=np.float64))
    return np.clip((1.0 - lambda_mix) * p + lambda_mix * calibrated, EPS_CAL, 1.0 - EPS_CAL)

def _apply_bootstrap_maps(probability: np.ndarray, theta: np.ndarray, lambda_mix: float) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=np.float64), EPS_CAL, 1.0 - EPS_CAL)
    params = np.asarray(theta, dtype=np.float64)
    linear = params[:, 0, None] + params[:, 1, None] * np.log(p) - params[:, 2, None] * np.log1p(-p)
    calibrated = _sigmoid(linear)
    return np.clip((1.0 - lambda_mix) * p + lambda_mix * calibrated, EPS_CAL, 1.0 - EPS_CAL)

def _ridge_label(ridge: float) -> str:
    return 'Infinity' if math.isinf(ridge) else f'{ridge:.1f}'

def _point_metrics(probability: np.ndarray, data: dict[str, Any], indices: np.ndarray) -> dict[str, float]:
    return base_engine._point_metrics(np.asarray(probability, dtype=np.float64), data['label'][indices], data['family'][indices], data['row_id'][indices], data['reference_brier'])

def _bootstrap_round_metrics(round_id: int, probability_all: np.ndarray, data: dict[str, Any]) -> tuple[dict[str, float], np.ndarray]:
    eval_indices = np.flatnonzero(data['eval_mask'])
    point = _point_metrics(probability_all[eval_indices], data, eval_indices)
    eval_families = sorted(data['eval_order'])
    family_indices = {family_name: np.flatnonzero(data['family'] == family_name) for family_name in eval_families}
    bootstrap = np.empty((B_CAL, 5), dtype=np.float64)
    for bootstrap_id in range(1, B_CAL + 1):
        rng = np.random.default_rng(seed32('calibration_bootstrap', round_id, bootstrap_id))
        selected = rng.choice(eval_families, size=25, replace=True)
        indices = np.concatenate([family_indices[str(value)] for value in selected])
        metrics = _point_metrics(probability_all[indices], data, indices)
        bootstrap[bootstrap_id - 1] = [metrics['brier'], metrics['ece10'], metrics['nll'], metrics['bss'], metrics['auc_reg']]
    point['ece_u95'] = float(np.quantile(bootstrap[:, 1], 0.975))
    point['bss_l95'] = float(np.quantile(bootstrap[:, 3], 0.025))
    point['auc_l95'] = float(np.quantile(bootstrap[:, 4], 0.025))
    point['cov_H'] = float(data['intervals']['H']['coverage90'])
    point['cov_Q'] = float(data['intervals']['Q']['coverage90'])
    point['nis_H'] = float(data['intervals']['H']['nis90'])
    point['nis_Q'] = float(data['intervals']['Q']['nis90'])
    return (point, bootstrap)

def _passes(metrics: dict[str, float]) -> tuple[bool, bool]:
    core = bool(metrics['brier'] <= 0.18 and metrics['ece10'] <= 0.07 and (metrics['nll'] <= 0.6) and (metrics['bss'] >= 0.0) and (metrics['auc_reg'] >= 0.68))
    all_pass = bool(core and metrics['ece_u95'] <= 0.1 and (metrics['bss_l95'] >= -0.02) and (metrics['auc_l95'] >= 0.55) and (0.85 <= metrics['cov_H'] <= 0.99) and (0.85 <= metrics['cov_Q'] <= 0.99) and (metrics['nis_H'] <= 0.85) and (metrics['nis_Q'] <= 0.85))
    return (core, all_pass)

def _violations(metrics: dict[str, float]) -> tuple[int, float, dict[str, float]]:
    gaps = {'brier': max(metrics['brier'] - 0.18, 0.0), 'ece10': max(metrics['ece10'] - 0.07, 0.0), 'nll': max(metrics['nll'] - 0.6, 0.0), 'bss': max(-metrics['bss'], 0.0), 'auc_reg': max(0.68 - metrics['auc_reg'], 0.0), 'ece_u95': max(metrics['ece_u95'] - 0.1, 0.0), 'bss_l95': max(-0.02 - metrics['bss_l95'], 0.0), 'auc_l95': max(0.55 - metrics['auc_l95'], 0.0), 'cov_H': max(0.85 - metrics['cov_H'], 0.0, metrics['cov_H'] - 0.99), 'cov_Q': max(0.85 - metrics['cov_Q'], 0.0, metrics['cov_Q'] - 0.99), 'nis_H': max(metrics['nis_H'] - 0.85, 0.0), 'nis_Q': max(metrics['nis_Q'] - 0.85, 0.0)}
    violation_sum = gaps['brier'] / 0.02 + gaps['ece10'] / 0.02 + gaps['nll'] / 0.05 + gaps['bss'] / 0.05 + gaps['auc_reg'] / 0.05 + gaps['ece_u95'] / 0.02 + gaps['bss_l95'] / 0.05 + gaps['auc_l95'] / 0.05 + gaps['cov_H'] / 0.02 + gaps['cov_Q'] / 0.02 + gaps['nis_H'] / 0.1 + gaps['nis_Q'] / 0.1
    return (int(sum((value > 0.0 for value in gaps.values()))), float(violation_sum), gaps)

def _improvement_vectors(previous: dict[str, Any], current: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, bool, bool]:
    previous_cov = max(abs(previous['cov_H'] - 0.9), abs(previous['cov_Q'] - 0.9))
    current_cov = max(abs(current['cov_H'] - 0.9), abs(current['cov_Q'] - 0.9))
    previous_nis = max(previous['nis_H'], previous['nis_Q'])
    current_nis = max(current['nis_H'], current['nis_Q'])
    improvement = np.asarray((previous['brier'] - current['brier'], previous['ece10'] - current['ece10'], previous['nll'] - current['nll'], current['auc_reg'] - previous['auc_reg'], current['bss'] - previous['bss'], previous_cov - current_cov, previous_nis - current_nis), dtype=np.float64)
    worsening = -improvement
    return (improvement, worsening, bool(np.any(improvement >= TAU)), bool(np.any(worsening > TAU)))

def _fit_round(round_id: int, ridge: float, data: dict[str, Any]) -> dict[str, Any]:
    identity_theta = np.asarray((0.0, 1.0, 1.0), dtype=np.float64)
    if round_id == 0:
        return {'success': True, 'fit_status': 'IDENTITY', 'lambda_mix': 0.0, 'theta': identity_theta, 'cv_brier': float(np.mean((data['p0'][data['fit_mask']] - data['label'][data['fit_mask']]) ** 2)), 'cv_grid_brier': [float(np.mean((data['p0'][data['fit_mask']] - data['label'][data['fit_mask']]) ** 2))] * len(LAMBDA_GRID), 'optimizer_iterations': 0, 'optimizer_gradient_max_abs': 0.0, 'optimizer_message': 'identity map', 'fold_success_count': 5}
    fit_order = list(data['fit_order'])
    oof_h = np.full(len(data['p0']), np.nan, dtype=np.float64)
    fold_results: list[dict[str, Any]] = []
    for fold_id in range(5):
        holdout_families = {family_name for position, family_name in enumerate(fit_order) if position % 5 == fold_id}
        holdout = data['fit_mask'] & np.isin(data['family'], list(holdout_families))
        train = data['fit_mask'] & ~holdout
        if int(holdout.sum()) != 50 or int(train.sum()) != 200:
            raise AssertionError('Family-CV fold row count mismatch')
        fit = _fit_beta_calibrator(data['p0'][train], data['label'][train], ridge)
        fold_results.append(fit)
        if fit['success']:
            oof_h[holdout] = _apply_map(data['p0'][holdout], fit['theta'], 1.0)
    full_fit = _fit_beta_calibrator(data['p0'][data['fit_mask']], data['label'][data['fit_mask']], ridge)
    if not all((result['success'] for result in fold_results)) or not full_fit['success']:
        return {'success': False, 'fit_status': 'NUMERIC_FAIL_IDENTITY', 'lambda_mix': 0.0, 'theta': identity_theta, 'cv_brier': float(np.mean((data['p0'][data['fit_mask']] - data['label'][data['fit_mask']]) ** 2)), 'cv_grid_brier': [math.nan] * len(LAMBDA_GRID), 'optimizer_iterations': int(full_fit['iterations']), 'optimizer_gradient_max_abs': float(full_fit['gradient_max_abs']), 'optimizer_message': str(full_fit['message']), 'fold_success_count': int(sum((result['success'] for result in fold_results)))}
    fit_indices = np.flatnonzero(data['fit_mask'])
    cv_values = []
    for lambda_mix in LAMBDA_GRID:
        probability = (1.0 - lambda_mix) * data['p0'][fit_indices] + lambda_mix * oof_h[fit_indices]
        cv_values.append(float(np.mean((probability - data['label'][fit_indices]) ** 2)))
    minimum = min(cv_values)
    eligible = [float(lambda_mix) for lambda_mix, value in zip(LAMBDA_GRID, cv_values) if abs(value - minimum) <= 1e-08]
    lambda_mix = min(eligible)
    return {'success': True, 'fit_status': 'FIT_OK', 'lambda_mix': float(lambda_mix), 'theta': np.asarray(full_fit['theta'], dtype=np.float64), 'cv_brier': float(minimum), 'cv_grid_brier': cv_values, 'optimizer_iterations': int(full_fit['iterations']), 'optimizer_gradient_max_abs': float(full_fit['gradient_max_abs']), 'optimizer_message': str(full_fit['message']), 'fold_success_count': 5}

def _select_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (int(row['violation_count']), float(row['violation_sum']), float(row['brier']), float(row['ece10']), float(row['nll']), -float(row['bss']), -float(row['auc_reg']), int(row['round_id']))

def _refit_final_calibrator(data: dict[str, Any], selected: dict[str, Any]) -> dict[str, Any]:
    if int(selected['round_id']) == 0 or selected['fit_status'] != 'FIT_OK':
        return {'success': True, 'theta': np.asarray((0.0, 1.0, 1.0), dtype=np.float64), 'lambda_mix': 0.0, 'fit_status': 'IDENTITY', 'iterations': 0, 'gradient_max_abs': 0.0, 'message': 'identity map'}
    ridge = float(selected['ridge'])
    fit = _fit_beta_calibrator(data['p0'], data['label'], ridge)
    if not fit['success']:
        return {'success': False, 'theta': np.asarray((0.0, 1.0, 1.0), dtype=np.float64), 'lambda_mix': 0.0, 'fit_status': 'FINAL_REFIT_FAIL_IDENTITY', 'iterations': fit['iterations'], 'gradient_max_abs': fit['gradient_max_abs'], 'message': fit['message']}
    return {'success': True, 'theta': fit['theta'], 'lambda_mix': float(selected['lambda_mix']), 'fit_status': 'FINAL_FIT_OK', 'iterations': fit['iterations'], 'gradient_max_abs': fit['gradient_max_abs'], 'message': fit['message']}

def _bootstrap_final_calibrators(data: dict[str, Any], selected: dict[str, Any], final_calibrator: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    theta = np.empty((B_RANK, 3), dtype=np.float64)
    fallback = np.zeros(B_RANK, dtype=np.int8)
    rows: list[dict[str, Any]] = []
    full_theta = np.asarray(final_calibrator['theta'], dtype=np.float64)
    if int(selected['round_id']) == 0 or float(final_calibrator['lambda_mix']) == 0.0:
        theta[:] = full_theta
        for bootstrap_id in range(1, B_RANK + 1):
            rows.append({'bootstrap_id': bootstrap_id, 'alpha': float(full_theta[0]), 'beta': float(full_theta[1]), 'gamma': float(full_theta[2]), 'fit_success': 1, 'bootstrap_fit_fallback': 0, 'iterations': 0})
        return (theta, fallback, pd.DataFrame(rows))
    ridge = float(selected['ridge'])
    family_indices = {family_name: np.flatnonzero(data['family'] == family_name) for family_name in data['all_family_order']}
    family_order = np.asarray(data['all_family_order'])
    for bootstrap_id in range(1, B_RANK + 1):
        rng = np.random.default_rng(seed32('rank_calibrator', bootstrap_id))
        selected_families = rng.choice(family_order, size=50, replace=True)
        indices = np.concatenate([family_indices[str(value)] for value in selected_families])
        fit = _fit_beta_calibrator(data['p0'][indices], data['label'][indices], ridge)
        if fit['success']:
            theta[bootstrap_id - 1] = fit['theta']
        else:
            theta[bootstrap_id - 1] = full_theta
            fallback[bootstrap_id - 1] = 1
        rows.append({'bootstrap_id': bootstrap_id, 'alpha': float(theta[bootstrap_id - 1, 0]), 'beta': float(theta[bootstrap_id - 1, 1]), 'gamma': float(theta[bootstrap_id - 1, 2]), 'fit_success': int(fit['success']), 'bootstrap_fit_fallback': int(fallback[bootstrap_id - 1]), 'iterations': int(fit['iterations'])})
        if bootstrap_id % 250 == 0:
            print(json.dumps({'rank_calibrator_bootstraps': bootstrap_id, 'fallbacks': int(fallback[:bootstrap_id].sum())}), flush=True)
    return (theta, fallback, pd.DataFrame(rows))

def _candidate_bootstraps(candidate: dict[str, Any], weights_result: dict[str, Any], calibrator_theta: np.ndarray, lambda_mix: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    COMMON_INDEX = weights_result['common_index']
    theta_common = np.empty((B_RANK, N_CANDIDATES, len(COMMON_INDEX)), dtype=np.float64)
    for bootstrap_id in range(1, B_RANK + 1):
        rng = np.random.default_rng(seed32('rank_bootstrap', bootstrap_id))
        theta_all = rng.beta(candidate['alpha'], candidate['beta'])
        theta_common[bootstrap_id - 1] = theta_all[:, COMMON_INDEX]
    weight_bootstrap = weights_result['weight_bootstrap'][:, COMMON_INDEX]
    p0_bootstrap = np.einsum('bcm,bm->bc', theta_common, weight_bootstrap, optimize=True)
    probability_bootstrap = _apply_bootstrap_maps(p0_bootstrap, calibrator_theta, lambda_mix)
    delta_bootstrap = np.sqrt(np.sum(weight_bootstrap[:, None, :] * (theta_common - p0_bootstrap[:, :, None]) ** 2, axis=2))
    return (probability_bootstrap, delta_bootstrap, theta_common)

def _score_components(probability: np.ndarray, probability_lower: np.ndarray, probability_upper: np.ndarray, delta: np.ndarray, q_clip: np.ndarray, g_cal: float) -> dict[str, np.ndarray]:
    g_path = 1.0
    width = probability_upper - probability_lower
    half_width = width / 2.0
    confidence = np.clip(g_cal * q_clip * np.clip(1.0 - width / 0.6, 0.0, 1.0) * np.clip(1.0 - delta / 0.3, 0.0, 1.0), 0.0, 1.0)
    score = np.clip(100.0 * (0.75 * probability + 0.25 * probability_lower) - 20.0 * half_width - 10.0 * delta - 5.0 * (1.0 - g_cal) - 5.0 * (1.0 - g_path), 0.0, 100.0)
    return {'W': width, 'h': half_width, 'probability_confidence': confidence, 'S': score}

def _rank_bootstraps(probability_bootstrap: np.ndarray, delta_bootstrap: np.ndarray, probability_lower: np.ndarray, score_components: dict[str, np.ndarray], candidate_ids: np.ndarray, g_cal: float) -> np.ndarray:
    g_path = 1.0
    rank_bootstrap = np.empty((B_RANK, N_CANDIDATES), dtype=np.int16)
    for bootstrap_position in range(B_RANK):
        score_b = np.clip(100.0 * (0.75 * probability_bootstrap[bootstrap_position] + 0.25 * probability_lower) - 20.0 * score_components['h'] - 10.0 * delta_bootstrap[bootstrap_position] - 5.0 * (1.0 - g_cal) - 5.0 * (1.0 - g_path), 0.0, 100.0)
        rank_bootstrap[bootstrap_position] = deterministic_rank(score_b, probability_lower, probability_bootstrap[bootstrap_position], delta_bootstrap[bootstrap_position], score_components['probability_confidence'], candidate_ids).astype(np.int16)
    return rank_bootstrap

def _loo_ranks(candidate: dict[str, Any], weights_result: dict[str, Any], final_calibrator: dict[str, Any], bootstrap_calibrator_theta: np.ndarray, theta_common: np.ndarray, q_clip: np.ndarray, g_cal: float) -> tuple[np.ndarray, list[dict[str, Any]]]:
    COMMON_INDEX = weights_result['common_index']
    COMMON_MODELS = weights_result['common_models']
    point_weights = weights_result['weights'][COMMON_INDEX]
    bootstrap_weights = weights_result['weight_bootstrap'][:, COMMON_INDEX]
    loo_ranks = np.empty((len(COMMON_INDEX), N_CANDIDATES), dtype=np.int32)
    summaries: list[dict[str, Any]] = []
    for omitted_position, omitted_model in enumerate(COMMON_MODELS):
        retained = np.asarray([index for index in range(len(COMMON_INDEX)) if index != omitted_position], dtype=np.int64)
        point_retained = point_weights[retained] / point_weights[retained].sum()
        p0_loo = candidate['p_model'][:, COMMON_INDEX[retained]] @ point_retained
        p_loo = _apply_map(p0_loo, final_calibrator['theta'], final_calibrator['lambda_mix'])
        delta_loo = np.sqrt(np.sum(point_retained * (candidate['p_model'][:, COMMON_INDEX[retained]] - p0_loo[:, None]) ** 2, axis=1))
        bootstrap_retained = bootstrap_weights[:, retained]
        bootstrap_retained = bootstrap_retained / bootstrap_retained.sum(axis=1, keepdims=True)
        p0_loo_boot = np.einsum('bcm,bm->bc', theta_common[:, :, retained], bootstrap_retained, optimize=True)
        p_loo_boot = _apply_bootstrap_maps(p0_loo_boot, bootstrap_calibrator_theta, final_calibrator['lambda_mix'])
        p_l = np.quantile(p_loo_boot, 0.025, axis=0)
        p_u = np.quantile(p_loo_boot, 0.975, axis=0)
        components = _score_components(p_loo, p_l, p_u, delta_loo, q_clip, g_cal)
        loo_ranks[omitted_position] = deterministic_rank(components['S'], p_l, p_loo, delta_loo, components['probability_confidence'], candidate['candidate_id'])
        summaries.append({'omitted_model': omitted_model, 'rank_1_candidate': str(candidate['candidate_id'][np.argmin(loo_ranks[omitted_position])]), 'probability_min': float(p_loo.min()), 'probability_max': float(p_loo.max())})
    return (loo_ranks, summaries)
