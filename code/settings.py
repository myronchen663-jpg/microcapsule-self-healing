from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
CONFIG = json.loads((PACKAGE / 'code/generator_config.json').read_text())
NUMERIC_FEATURES = ('capsule_content_wt_pct', 'capsule_d50_um', 'heal_temperature_C', 'heal_time_h', 'initial_crack_opening_um')
CATEGORICAL_FEATURES = ('healing_chemistry_family', 'interface_treatment_family')
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
MODEL_NAMES = ('elastic_net', 'random_forest', 'catboost', 'mixed_gp', 'bayesian_multilevel')
MODELS = tuple(sorted(MODEL_NAMES))
MODEL_INDEX = {model: i for i, model in enumerate(MODELS)}
ENDPOINTS = ('H', 'Q')
ENDPOINT_SOURCE = {'H': 'eta_k_pct', 'Q': 'strength_penalty_pct'}
SUPPORT = {'H': (-10.0, 140.0), 'Q': (-5.0, 40.0)}
THRESHOLD = {'H': 60.0, 'Q': 15.0}
PROFILE = SimpleNamespace(**CONFIG['model_profile'])
GLOBAL_SEED = CONFIG['sampling']['seed']
DRAWS = CONFIG['sampling']['predictive_draws']
B_WEIGHT = CONFIG['sampling']['weight_bootstraps']
B_CAL = CONFIG['sampling']['calibration_bootstraps']
B_RANK = CONFIG['sampling']['rank_bootstraps']
N_CANDIDATES = CONFIG['sampling']['candidate_rows']
EPS_CAL = 1e-6
EPS_D = 0.5 / (DRAWS + 1.0)

def read_data(name):
    import pandas as pd
    return pd.read_csv(PACKAGE / 'data' / name, float_precision='round_trip', keep_default_na=False)
