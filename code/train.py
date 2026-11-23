from __future__ import annotations
import time
import numpy as np
import pandas as pd
from scipy import stats
from threadpoolctl import threadpool_limits
from settings import *
from models import make_model
from intervals import IntervalCalibrator, distribution_scale, _family_split_and_subsample


def _gp_family_subset(train: pd.DataFrame, *, maximum_rows: int, random_seed: int) -> pd.DataFrame:
    if len(train) <= maximum_rows:
        return train
    rng = np.random.default_rng(random_seed)
    families = np.array(sorted(set(train['syn_scenario_family_id'].astype(str))))
    rng.shuffle(families)
    pieces: list[pd.DataFrame] = []
    rows = 0
    for family in families:
        part = train.loc[train['syn_scenario_family_id'].astype(str).eq(family)]
        if rows + len(part) > maximum_rows and pieces:
            break
        pieces.append(part)
        rows += len(part)
    return pd.concat(pieces, ignore_index=True)

def _family_coverage_t_interval(covered: np.ndarray, groups: np.ndarray) -> tuple[float, float, float, int]:
    labels = np.asarray(groups).astype(str)
    families = sorted(set(labels.tolist()))
    means = np.array([float(np.mean(covered[labels == family])) for family in families], dtype=float)
    n = len(means)
    centre = float(np.mean(means))
    if n < 2:
        return (centre, float('nan'), float('nan'), n)
    sd = float(np.std(means, ddof=1))
    half = float(stats.t.ppf(0.975, n - 1)) * sd / float(np.sqrt(n))
    return (centre, centre - half, centre + half, n)

def train_models(frame, candidates):
    train = frame.loc[frame['split'].eq('train')].reset_index(drop=True)
    calibration = frame.loc[frame['split'].isin(['calibration_fit', 'calibration_eval'])].reset_index(drop=True)
    test = frame.loc[frame['split'].eq('test')].reset_index(drop=True)
    X_train = train.loc[:, list(MODEL_FEATURES)]
    X_cal = calibration.loc[:, list(MODEL_FEATURES)]
    X_test = test.loc[:, list(MODEL_FEATURES)]
    X_candidate = candidates.loc[:, list(MODEL_FEATURES)]
    groups = train['syn_scenario_family_id'].astype(str).to_numpy()
    cal_groups = calibration['syn_scenario_family_id'].astype(str).to_numpy()
    subsample, fit_mask, eval_mask = _family_split_and_subsample(cal_groups, CONFIG['sampling']['calibration_split_seed'])
    raw = np.empty((len(candidates), len(MODELS), 2, DRAWS), dtype=np.float64)
    cal_raw = np.empty((len(calibration), len(MODELS), 2, DRAWS), dtype=np.float64)
    predictions = {'candidate_id': candidates['candidate_id'].to_numpy()}
    test_parts = []
    metrics = []
    for endpoint_position, endpoint_key in enumerate(ENDPOINTS):
        endpoint = ENDPOINT_SOURCE[endpoint_key]
        support = SUPPORT[endpoint_key]
        y_train = train[endpoint].to_numpy(dtype=float)
        y_cal = calibration[endpoint].to_numpy(dtype=float)
        for model_name in MODEL_NAMES:
            print(f'Training {model_name}: {endpoint}', flush=True)
            model_position = MODEL_INDEX[model_name]
            seed = CONFIG['model_seeds'][endpoint][model_name]
            model = make_model(model_name, profile=PROFILE, random_seed=seed)
            started = time.monotonic()
            with threadpool_limits(limits=1):
                fit_train = _gp_family_subset(train, maximum_rows=PROFILE.gp_max_rows, random_seed=seed) if model_name == 'mixed_gp' else train
                if model_name == 'mixed_gp':
                    model.fit(fit_train.loc[:, list(MODEL_FEATURES)], fit_train[endpoint].to_numpy(dtype=float), groups=fit_train['syn_scenario_family_id'].astype(str).to_numpy())
                else:
                    model.fit(X_train, y_train, groups=groups)
                cal_draws = model.predict_distribution(X_cal, n_draws=DRAWS, random_seed=seed+11)
                cal_prediction = cal_draws.mean(axis=0)
                cal_scale = distribution_scale(cal_draws)
                calibrator = IntervalCalibrator(level=0.90).fit(y_cal[subsample], cal_prediction[subsample], cal_scale[subsample])
                test_draws = model.predict_distribution(X_test, n_draws=DRAWS, random_seed=seed+17)
                test_prediction = test_draws.mean(axis=0)
                test_scale = distribution_scale(test_draws)
                lower, upper = calibrator.interval(test_prediction, test_scale)
                raw_widths = upper - lower
                structural_ok = bool(np.isfinite(np.clip(lower, *support)).all() and np.isfinite(np.clip(upper, *support)).all() and np.isfinite(raw_widths).all() and np.all(raw_widths > 0.0))
                test_parts.append(pd.DataFrame({
                    'syn_row_id':test['syn_row_id'], 'syn_scenario_family_id':test['syn_scenario_family_id'],
                    'endpoint':endpoint, 'model_name':model_name, 'observed_syn':test[endpoint],
                    'prediction':np.clip(test_prediction,*support), 'lower90':np.clip(lower,*support),
                    'upper90':np.clip(upper,*support), 'predictive_sd':test_scale,
                }))
                draws = model.predict_distribution(X_candidate, n_draws=DRAWS, random_seed=CONFIG['candidate_draw_seeds'][model_name][endpoint])
                centre = draws.mean(axis=0)
                lower, upper = calibrator.interval(centre, distribution_scale(draws))
                endpoint_label = 'eta' if endpoint_key=='H' else 'penalty'
                for label, values in [('prediction',centre),('lower90',lower),('upper90',upper)]:
                    predictions[f'{model_name}__{endpoint_label}_{label}'] = np.clip(values,*support)
                raw[:,model_position,endpoint_position,:] = draws.T
                cal_raw[:,model_position,endpoint_position,:] = cal_draws.T
                eval_lower, eval_upper = calibrator.interval(cal_prediction[eval_mask],cal_scale[eval_mask])
                covered = (y_cal[eval_mask]>=np.clip(eval_lower,*support)) & (y_cal[eval_mask]<=np.clip(eval_upper,*support))
                coverage, lower_coverage, upper_coverage, family_count = _family_coverage_t_interval(covered.astype(float), cal_groups[eval_mask])
                metrics.append({'model':model_name,'endpoint':endpoint,'fit_rows':len(fit_train),'conformal_quantile':calibrator.quantile_,'calibration_coverage':coverage,'calibration_coverage_lower':lower_coverage,'calibration_family_count':family_count,'structural_ok':structural_ok,'calibration_coverage_upper':upper_coverage,'eligible':bool(structural_ok and np.isfinite(upper_coverage) and upper_coverage>=0.90),'seconds':time.monotonic()-started})
    return pd.DataFrame(predictions), pd.concat(test_parts,ignore_index=True), raw, cal_raw, calibration, pd.DataFrame(metrics)
