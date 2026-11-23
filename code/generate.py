from __future__ import annotations
from typing import Any, Mapping
import numpy as np
import pandas as pd
from scipy.stats import qmc
from settings import CONFIG, MODEL_FEATURES
def _logistic(value: float | np.ndarray) -> float | np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -35.0, 35.0)))

def _outcome_means(row: Mapping[str, Any], *, config: dict[str, Any], anchor_eta_median: float, family_eta_offset: float, family_penalty_offset: float) -> tuple[float, float, float, float]:
    mechanism = config['mechanism']
    chemistry = config['chemistries'][str(row['healing_chemistry_family'])]
    interface = config['interfaces'][str(row['interface_treatment_family'])]
    content = float(row['capsule_content_wt_pct'])
    d50 = float(row['capsule_d50_um'])
    temperature = float(row['heal_temperature_C'])
    time_h = float(row['heal_time_h'])
    crack = float(row['initial_crack_opening_um'])
    availability = 1.0 - np.exp(-content / float(mechanism['content_half_saturation_wt_pct']))
    ratio = d50 / max(crack, 1e-06)
    bridging = np.exp(-0.5 * (np.log(max(ratio, 1e-06) / float(mechanism['ideal_d50_to_crack_ratio'])) / float(mechanism['log_ratio_width'])) ** 2)
    thermal_term = (temperature - float(chemistry['activation_temperature_C'])) / float(mechanism['activation_temperature_width_C']) + np.log(max(time_h, 0.1) / float(chemistry['activation_time_h'])) / float(mechanism['activation_log_time_width'])
    activation = float(_logistic(thermal_term))
    overload = max(0.0, content - float(mechanism['content_overload_start_wt_pct'])) * float(mechanism['content_overload_slope_pct_per_wt_pct'])
    anchor_shift = float(mechanism['anchor_intercept_weight']) * (anchor_eta_median - float(mechanism['anchor_reference_eta_pct']))
    eta_mean = float(mechanism['eta_intercept_pct']) + float(mechanism['eta_scale_pct']) * availability * bridging * activation + float(chemistry['eta_offset_pct']) + float(interface['eta_effect_pct']) + anchor_shift + family_eta_offset - overload
    eta_sd = float(mechanism['eta_noise_floor_pct']) + float(mechanism['eta_noise_fraction']) * abs(eta_mean)
    penalty_mean = float(mechanism['penalty_content_slope']) * content + float(mechanism['penalty_size_slope_per_100um']) * d50 / 100.0 + float(chemistry['penalty_offset_pct']) + float(interface['penalty_effect_pct']) + family_penalty_offset
    penalty_sd = float(mechanism['penalty_noise_sd_pct'])
    return (eta_mean, eta_sd, penalty_mean, penalty_sd)

def _sample_family_centre(rng: np.random.Generator, config: dict[str, Any]) -> dict[str, Any]:
    pairs = [tuple(item) for item in config['allowed_chemistry_interface_pairs']]
    raw_weights = np.array([float(config['chemistries'][chemistry]['probability']) for chemistry, _ in pairs])
    weights = raw_weights / raw_weights.sum()
    chemistry, interface = pairs[int(rng.choice(len(pairs), p=weights))]
    space = config['design_space']
    return {'capsule_content_wt_pct': rng.uniform(*space['capsule_content_wt_pct']), 'capsule_d50_um': np.exp(rng.uniform(np.log(space['capsule_d50_um'][0]), np.log(space['capsule_d50_um'][1]))), 'heal_temperature_C': rng.uniform(*space['heal_temperature_C']), 'heal_time_h': np.exp(rng.uniform(np.log(space['heal_time_h'][0]), np.log(space['heal_time_h'][1]))), 'initial_crack_opening_um': np.exp(rng.uniform(np.log(space['initial_crack_opening_um'][0]), np.log(space['initial_crack_opening_um'][1]))), 'healing_chemistry_family': chemistry, 'interface_treatment_family': interface}

def _jitter_centre(centre: Mapping[str, Any], rng: np.random.Generator, config: dict[str, Any]) -> dict[str, Any]:
    space = config['design_space']
    row = dict(centre)
    for name in ('capsule_content_wt_pct', 'heal_temperature_C'):
        lower, upper = map(float, space[name])
        row[name] = float(np.clip(float(centre[name]) + rng.normal(0.0, 0.07 * (upper - lower)), lower, upper))
    for name in ('capsule_d50_um', 'heal_time_h', 'initial_crack_opening_um'):
        lower, upper = map(float, space[name])
        row[name] = float(np.clip(float(centre[name]) * np.exp(rng.normal(0.0, 0.16)), lower, upper))
    return row


def calibration_orders(families):
    families = np.array(sorted(set(families)))
    rng = np.random.default_rng(CONFIG['sampling']['calibration_split_seed'])
    order = rng.permutation(len(families))
    n_fit = len(families)//2
    return families[order[:n_fit]].tolist(), families[order[n_fit:]].tolist()


def assign_split(frame):
    families = np.array(sorted(set(frame['syn_scenario_family_id'].astype(str))))
    rng = np.random.default_rng(CONFIG['sampling']['family_split_seed'])
    shuffled = families.copy()
    rng.shuffle(shuffled)
    n_test = max(2,int(round(0.20*len(shuffled))))
    n_cal = max(2,int(round(0.20*len(shuffled))))
    test = shuffled[:n_test]
    calibration = shuffled[n_test:n_test+n_cal]
    fit, evaluation = calibration_orders(calibration)
    roles = {f:'train' for f in families}
    roles.update({f:'test' for f in test})
    roles.update({f:'calibration_fit' for f in fit})
    roles.update({f:'calibration_eval' for f in evaluation})
    return frame['syn_scenario_family_id'].map(roles)


def generate_training(anchor):
    values = anchor['eta_k_pct'].to_numpy(dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('Literature anchor requires nonempty finite measurements')
    anchor_eta = float(np.median(values))
    config = CONFIG
    sampling = config['sampling']
    rng = np.random.default_rng(sampling['seed'])
    mechanism = config['mechanism']
    eta_bounds = config['plausibility']['eta_k_pct']
    penalty_bounds = config['plausibility']['strength_penalty_pct']
    rows = []
    for family_index in range(sampling['n_families']):
        family_id = f'SYN_FAMILY_{family_index+1:04d}'
        centre = _sample_family_centre(rng,config)
        family_eta_offset = rng.normal(0.0,float(mechanism['family_eta_sd_pct']))
        family_penalty_offset = rng.normal(0.0,float(mechanism['penalty_family_sd_pct']))
        for row_index in range(sampling['rows_per_family']):
            row = _jitter_centre(centre,rng,config)
            eta_mean,eta_sd,penalty_mean,penalty_sd = _outcome_means(row,config=config,anchor_eta_median=anchor_eta,family_eta_offset=float(family_eta_offset),family_penalty_offset=float(family_penalty_offset))
            eta = float(np.clip(rng.normal(eta_mean,eta_sd),*eta_bounds))
            penalty = float(np.clip(rng.normal(penalty_mean,penalty_sd),*penalty_bounds))
            row.update({'syn_row_id':f'SYN::{family_index+1:04d}::{row_index+1:03d}',
                'syn_scenario_family_id':family_id,'evidence_label':'SYN','data_origin':'SYNTHETIC_PRIMARY',
                'eta_k_pct':eta,'eta_k_mean_pct':float(np.clip(eta_mean,*eta_bounds)),
                'eta_k_aleatoric_sd_pct':eta_sd,'strength_penalty_pct':penalty,
                'strength_penalty_mean_pct':float(np.clip(penalty_mean,*penalty_bounds)),
                'strength_penalty_aleatoric_sd_pct':penalty_sd})
            rows.append(row)
    frame = pd.DataFrame(rows)
    frame = frame.loc[:,list(MODEL_FEATURES)+[x for x in frame.columns if x not in MODEL_FEATURES]]
    frame['split'] = assign_split(frame)
    return frame


def generate_candidates():
    pairs = CONFIG['allowed_chemistry_interface_pairs']
    n_candidates = CONFIG['sampling']['candidate_rows']
    random_seed = CONFIG['sampling']['candidate_grid_seed']
    if n_candidates < len(pairs):
        raise ValueError('Candidate count must cover every chemistry/interface pair')
    allocations = np.full(len(pairs), n_candidates // len(pairs), dtype=int)
    allocations[:n_candidates % len(pairs)] += 1
    numeric = list(CONFIG['design_space'])
    frames = []
    for pair_index, ((chemistry, interface), count) in enumerate(zip(pairs, allocations)):
        sampler = qmc.LatinHypercube(d=len(numeric), seed=random_seed + pair_index)
        unit = sampler.random(int(count))
        values = np.empty_like(unit)
        for column_index, name in enumerate(numeric):
            lower, upper = map(float, CONFIG['design_space'][name])
            if name in {'capsule_d50_um', 'heal_time_h', 'initial_crack_opening_um'}:
                values[:, column_index] = np.exp(np.log(lower) + unit[:, column_index] * (np.log(upper) - np.log(lower)))
            else:
                values[:, column_index] = lower + unit[:, column_index] * (upper - lower)
        frame = pd.DataFrame(values, columns=numeric)
        frame['healing_chemistry_family'] = chemistry
        frame['interface_treatment_family'] = interface
        frames.append(frame)
    output = pd.concat(frames, ignore_index=True).iloc[:n_candidates].copy()
    output.insert(0, 'candidate_id', [f'CANDIDATE_{index + 1:05d}' for index in range(len(output))])
    return output
