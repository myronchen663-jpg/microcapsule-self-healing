from __future__ import annotations
import importlib.util
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Hyperparameter, Kernel
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from settings import CATEGORICAL_FEATURES, MODEL_NAMES, NUMERIC_FEATURES

class ModelNotEligibleError(RuntimeError):
    pass

class BaseSurrogate(ABC):
    model_name = 'base'
    family_name = 'Base surrogate'

    def __init__(self, *, numeric_features: Iterable[str]=NUMERIC_FEATURES, categorical_features: Iterable[str]=CATEGORICAL_FEATURES, params: dict[str, Any] | None=None, random_seed: int=0) -> None:
        self.numeric_features = tuple(numeric_features)
        self.categorical_features = tuple(categorical_features)
        self.params = dict(params or {})
        self.random_seed = int(random_seed)
        self.is_fitted_ = False
        self.training_metadata_: dict[str, Any] = {}

    @classmethod
    def dependency_reason(cls) -> str | None:
        return None

    def eligibility_reason(self, y: np.ndarray | None=None) -> str | None:
        dependency = self.dependency_reason()
        if dependency:
            return f'DEPENDENCY_UNAVAILABLE:{dependency}'
        if y is not None and len(y) < 8:
            return f'TOO_FEW_TRAINING_ROWS:{len(y)}'
        if y is not None and (not np.isfinite(np.asarray(y, dtype=float)).all()):
            return 'NONFINITE_TARGET'
        return None

    def _assert_eligible(self, y: np.ndarray) -> None:
        reason = self.eligibility_reason(y)
        if reason:
            raise ModelNotEligibleError(reason)

    def _record_training_metadata(self, X: pd.DataFrame, y: np.ndarray, groups: np.ndarray) -> None:
        self.training_metadata_ = {'n_rows': int(len(y))}

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: np.ndarray, *, groups: np.ndarray) -> 'BaseSurrogate':
        raise NotImplementedError

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def predict_distribution(self, X: pd.DataFrame, *, n_draws: int=200, random_seed: int | None=None) -> np.ndarray:
        raise NotImplementedError

    def predict_interval(self, X: pd.DataFrame, *, level: float=0.9, n_draws: int=200, random_seed: int | None=None) -> tuple[np.ndarray, np.ndarray]:
        draws = self.predict_distribution(X, n_draws=n_draws, random_seed=random_seed)
        alpha = (1.0 - level) / 2.0
        return (np.quantile(draws, alpha, axis=0), np.quantile(draws, 1.0 - alpha, axis=0))

class _SklearnPreprocessor:

    def __init__(self, numeric: Iterable[str], categorical: Iterable[str]) -> None:
        self.numeric = tuple(numeric)
        self.categorical = tuple(categorical)

    def fit(self, X: pd.DataFrame) -> '_SklearnPreprocessor':
        transformers: list[tuple[str, Any, list[str]]] = []
        if self.numeric:
            transformers.append(('numeric', Pipeline([('imputer', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), list(self.numeric)))
        if self.categorical:
            transformers.append(('categorical', Pipeline([('imputer', SimpleImputer(strategy='most_frequent')), ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), list(self.categorical)))
        self.transformer_ = ColumnTransformer(transformers, sparse_threshold=0.0)
        self.transformer_.fit(X)
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.transformer_.transform(X), dtype=float)

    def fit_transform(self, X: pd.DataFrame) -> np.ndarray:
        self.fit(X)
        return self.transform(X)

class _NativeCatPreprocessor:

    def __init__(self, numeric: Iterable[str], categorical: Iterable[str]) -> None:
        self.numeric = tuple(numeric)
        self.categorical = tuple(categorical)

    def fit(self, X: pd.DataFrame) -> '_NativeCatPreprocessor':
        self.medians_ = {name: float(pd.to_numeric(X[name], errors='coerce').median()) for name in self.numeric}
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        output = pd.DataFrame(index=X.index)
        for name in self.numeric:
            output[name] = pd.to_numeric(X[name], errors='coerce').fillna(self.medians_[name])
        for name in self.categorical:
            output[name] = X[name].fillna('UNKNOWN').astype(str)
        return output.reset_index(drop=True)

    @property
    def categorical_indices(self) -> list[int]:
        return list(range(len(self.numeric), len(self.numeric) + len(self.categorical)))

@dataclass
class _FittedPair:
    preprocessor: Any
    estimator: Any

def _group_bootstrap_indices(groups: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    values = np.asarray(groups).astype(str)
    unique = np.array(sorted(set(values)))
    if len(unique) < 2:
        return np.arange(len(values))
    sampled = rng.choice(unique, size=len(unique), replace=True)
    return np.concatenate([np.flatnonzero(values == group) for group in sampled])

def _robust_residual_scale(y: np.ndarray, prediction: np.ndarray) -> float:
    residual = np.asarray(y, dtype=float) - np.asarray(prediction, dtype=float)
    return float(max(np.median(np.abs(residual - np.median(residual))) * 1.4826, 1e-06))

class ElasticNetSurrogate(BaseSurrogate):
    model_name = 'elastic_net'
    family_name = 'Elastic-net'

    def _fit_pair(self, X: pd.DataFrame, y: np.ndarray, seed: int) -> _FittedPair:
        preprocessor = _SklearnPreprocessor(self.numeric_features, self.categorical_features)
        matrix = preprocessor.fit_transform(X)
        estimator = ElasticNet(alpha=float(self.params.get('alpha', 0.025)), l1_ratio=float(self.params.get('l1_ratio', 0.35)), max_iter=int(self.params.get('max_iter', 10000)), random_state=seed)
        estimator.fit(matrix, y)
        return _FittedPair(preprocessor, estimator)

    @staticmethod
    def _pair_predict(pair: _FittedPair, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(pair.estimator.predict(pair.preprocessor.transform(X)), dtype=float)

    def fit(self, X: pd.DataFrame, y: np.ndarray, *, groups: np.ndarray) -> 'ElasticNetSurrogate':
        y = np.asarray(y, dtype=float)
        self._assert_eligible(y)
        self.base_pair_ = self._fit_pair(X, y, self.random_seed)
        self.residual_scale_ = _robust_residual_scale(y, self._pair_predict(self.base_pair_, X))
        self.bootstrap_pairs_: list[_FittedPair] = []
        rng = np.random.default_rng(self.random_seed + 101)
        for index in range(int(self.params.get('bootstrap_models', 5))):
            selected = _group_bootstrap_indices(groups, rng)
            self.bootstrap_pairs_.append(self._fit_pair(X.iloc[selected].reset_index(drop=True), y[selected], self.random_seed + 1000 + index))
        self._record_training_metadata(X, y, groups)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError('Model is not fitted')
        return self._pair_predict(self.base_pair_, X)

    def predict_distribution(self, X: pd.DataFrame, *, n_draws: int=200, random_seed: int | None=None) -> np.ndarray:
        rng = np.random.default_rng(self.random_seed if random_seed is None else random_seed)
        pairs = self.bootstrap_pairs_ or [self.base_pair_]
        predictions = np.vstack([self._pair_predict(pair, X) for pair in pairs])
        selected = predictions[rng.integers(0, len(predictions), size=n_draws)]
        return selected + rng.normal(0.0, self.residual_scale_, size=selected.shape)

class RandomForestSurrogate(BaseSurrogate):
    model_name = 'random_forest'
    family_name = 'Random Forest'

    def _fit_pair(self, X: pd.DataFrame, y: np.ndarray, seed: int, trees: int) -> _FittedPair:
        preprocessor = _SklearnPreprocessor(self.numeric_features, self.categorical_features)
        matrix = preprocessor.fit_transform(X)
        estimator = RandomForestRegressor(n_estimators=trees, max_depth=self.params.get('max_depth', 8), min_samples_leaf=int(self.params.get('min_samples_leaf', 2)), max_features=self.params.get('max_features', 0.8), bootstrap=True, n_jobs=1, random_state=seed)
        estimator.fit(matrix, y)
        return _FittedPair(preprocessor, estimator)

    @staticmethod
    def _pair_predict(pair: _FittedPair, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(pair.estimator.predict(pair.preprocessor.transform(X)), dtype=float)

    def fit(self, X: pd.DataFrame, y: np.ndarray, *, groups: np.ndarray) -> 'RandomForestSurrogate':
        y = np.asarray(y, dtype=float)
        self._assert_eligible(y)
        trees = int(self.params.get('n_estimators', 180))
        self.base_pair_ = self._fit_pair(X, y, self.random_seed, trees)
        self.residual_scale_ = _robust_residual_scale(y, self._pair_predict(self.base_pair_, X))
        self.bootstrap_pairs_: list[_FittedPair] = []
        rng = np.random.default_rng(self.random_seed + 211)
        for index in range(int(self.params.get('bootstrap_models', 3))):
            selected = _group_bootstrap_indices(groups, rng)
            self.bootstrap_pairs_.append(self._fit_pair(X.iloc[selected].reset_index(drop=True), y[selected], self.random_seed + 2000 + index, max(40, trees // 2)))
        self._record_training_metadata(X, y, groups)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError('Model is not fitted')
        return self._pair_predict(self.base_pair_, X)

    def predict_distribution(self, X: pd.DataFrame, *, n_draws: int=200, random_seed: int | None=None) -> np.ndarray:
        rng = np.random.default_rng(self.random_seed if random_seed is None else random_seed)
        pairs = [self.base_pair_] + self.bootstrap_pairs_
        predictions = np.vstack([self._pair_predict(pair, X) for pair in pairs])
        selected = predictions[rng.integers(0, len(predictions), size=n_draws)]
        return selected + rng.normal(0.0, 0.35 * self.residual_scale_, size=selected.shape)

class CatBoostSurrogate(BaseSurrogate):
    model_name = 'catboost'
    family_name = 'CatBoost'

    @classmethod
    def dependency_reason(cls) -> str | None:
        return None if importlib.util.find_spec('catboost') else 'catboost:not_installed'

    def _fit_pair(self, X: pd.DataFrame, y: np.ndarray, seed: int) -> _FittedPair:
        from catboost import CatBoostRegressor
        preprocessor = _NativeCatPreprocessor(self.numeric_features, self.categorical_features).fit(X)
        native = preprocessor.transform(X)
        estimator = CatBoostRegressor(iterations=int(self.params.get('iterations', 220)), depth=int(self.params.get('depth', 4)), learning_rate=float(self.params.get('learning_rate', 0.055)), l2_leaf_reg=float(self.params.get('l2_leaf_reg', 6.0)), loss_function='RMSE', random_seed=seed, thread_count=1, verbose=False, allow_writing_files=False)
        estimator.fit(native, y, cat_features=preprocessor.categorical_indices, verbose=False)
        return _FittedPair(preprocessor, estimator)

    @staticmethod
    def _pair_predict(pair: _FittedPair, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(pair.estimator.predict(pair.preprocessor.transform(X)), dtype=float)

    def fit(self, X: pd.DataFrame, y: np.ndarray, *, groups: np.ndarray) -> 'CatBoostSurrogate':
        y = np.asarray(y, dtype=float)
        self._assert_eligible(y)
        self.pairs_ = [self._fit_pair(X, y, self.random_seed + index) for index in range(int(self.params.get('ensemble_size', 2)))]
        self.residual_scale_ = _robust_residual_scale(y, self._pair_predict(self.pairs_[0], X))
        self._record_training_metadata(X, y, groups)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError('Model is not fitted')
        return np.mean([self._pair_predict(pair, X) for pair in self.pairs_], axis=0)

    def predict_distribution(self, X: pd.DataFrame, *, n_draws: int=200, random_seed: int | None=None) -> np.ndarray:
        rng = np.random.default_rng(self.random_seed if random_seed is None else random_seed)
        predictions = np.vstack([self._pair_predict(pair, X) for pair in self.pairs_])
        selected = predictions[rng.integers(0, len(predictions), size=n_draws)]
        return selected + rng.normal(0.0, 0.45 * self.residual_scale_, size=selected.shape)

class _MixedEncoder:

    def __init__(self, numeric: Iterable[str], categorical: Iterable[str]) -> None:
        self.numeric = tuple(numeric)
        self.categorical = tuple(categorical)

    def fit(self, X: pd.DataFrame) -> '_MixedEncoder':
        self.num_imputer_ = SimpleImputer(strategy='median')
        self.num_scaler_ = StandardScaler()
        if self.numeric:
            numeric = self.num_imputer_.fit_transform(X.loc[:, list(self.numeric)])
            self.num_scaler_.fit(numeric)
        self.category_maps_ = {name: {value: index for index, value in enumerate(sorted(set(X[name].fillna('UNKNOWN').astype(str))))} for name in self.categorical}
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        parts: list[np.ndarray] = []
        if self.numeric:
            numeric = self.num_imputer_.transform(X.loc[:, list(self.numeric)])
            parts.append(self.num_scaler_.transform(numeric))
        if self.categorical:
            categorical = np.column_stack([X[name].fillna('UNKNOWN').astype(str).map(lambda item: self.category_maps_[name].get(item, -1)).to_numpy(dtype=float) for name in self.categorical])
            parts.append(categorical)
        return np.column_stack(parts) if parts else np.empty((len(X), 0), dtype=float)

    @property
    def numeric_dimension(self) -> int:
        return len(self.numeric)

    @property
    def categorical_dimension(self) -> int:
        return len(self.categorical)

class MixedMaternHammingKernel(Kernel):

    def __init__(self, numeric_dims: int, categorical_dims: int, length_scale: float=1.3, categorical_rho: float=0.65, variance: float=1.0, length_scale_bounds: tuple[float, float] | str='fixed', categorical_rho_bounds: tuple[float, float] | str='fixed', variance_bounds: tuple[float, float] | str='fixed') -> None:
        self.numeric_dims = numeric_dims
        self.categorical_dims = categorical_dims
        self.length_scale = length_scale
        self.categorical_rho = categorical_rho
        self.variance = variance
        self.length_scale_bounds = length_scale_bounds
        self.categorical_rho_bounds = categorical_rho_bounds
        self.variance_bounds = variance_bounds

    @property
    def hyperparameter_length_scale(self) -> Hyperparameter:
        return Hyperparameter('length_scale', 'numeric', self.length_scale_bounds)

    @property
    def hyperparameter_categorical_rho(self) -> Hyperparameter:
        return Hyperparameter('categorical_rho', 'numeric', self.categorical_rho_bounds)

    @property
    def hyperparameter_variance(self) -> Hyperparameter:
        return Hyperparameter('variance', 'numeric', self.variance_bounds)

    def __call__(self, X: np.ndarray, Y: np.ndarray | None=None, eval_gradient: bool=False) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        X = np.atleast_2d(np.asarray(X, dtype=float))
        y_is_none = Y is None
        Y = X if Y is None else np.atleast_2d(np.asarray(Y, dtype=float))
        if eval_gradient and (not y_is_none):
            raise ValueError('Gradient is only available for Y=None')
        if self.numeric_dims:
            delta = (X[:, None, :self.numeric_dims] - Y[None, :, :self.numeric_dims]) / float(self.length_scale)
            radius = np.sqrt(np.sum(delta ** 2, axis=2))
        else:
            radius = np.zeros((len(X), len(Y)), dtype=float)
        root3 = np.sqrt(3.0)
        numeric_kernel = (1.0 + root3 * radius) * np.exp(-root3 * radius)
        if self.categorical_dims:
            start = self.numeric_dims
            mismatches = np.sum(X[:, None, start:] != Y[None, :, start:], axis=2)
            categorical_kernel = float(self.categorical_rho) ** mismatches
        else:
            categorical_kernel = np.ones_like(radius)
        kernel = float(self.variance) * numeric_kernel * categorical_kernel
        if not eval_gradient:
            return kernel
        return (kernel, np.empty(kernel.shape + (0,), dtype=float))

    def diag(self, X: np.ndarray) -> np.ndarray:
        return np.full(len(np.atleast_2d(X)), float(self.variance), dtype=float)

    def is_stationary(self) -> bool:
        return True

class MixedGPSurrogate(BaseSurrogate):
    model_name = 'mixed_gp'
    family_name = 'Mixed-variable Gaussian Process'

    def eligibility_reason(self, y: np.ndarray | None=None) -> str | None:
        reason = super().eligibility_reason(y)
        if reason:
            return reason
        maximum = int(self.params.get('maximum_training_rows', 600))
        if y is not None and len(y) > maximum:
            return f'GP_ROW_LIMIT:{len(y)}>{maximum}'
        return None

    def fit(self, X: pd.DataFrame, y: np.ndarray, *, groups: np.ndarray) -> 'MixedGPSurrogate':
        y = np.asarray(y, dtype=float)
        self._assert_eligible(y)
        self.encoder_ = _MixedEncoder(self.numeric_features, self.categorical_features).fit(X)
        matrix = self.encoder_.transform(X)
        kernel = MixedMaternHammingKernel(self.encoder_.numeric_dimension, self.encoder_.categorical_dimension, length_scale=float(self.params.get('length_scale', 1.3)), categorical_rho=float(self.params.get('categorical_rho', 0.65)), variance=float(self.params.get('variance', 1.0)))
        noise = float(self.params.get('noise', 0.08))
        self.estimator_ = GaussianProcessRegressor(kernel=kernel, alpha=noise ** 2, optimizer=None, normalize_y=True, random_state=self.random_seed)
        self.estimator_.fit(matrix, y)
        self._record_training_metadata(X, y, groups)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError('Model is not fitted')
        return np.asarray(self.estimator_.predict(self.encoder_.transform(X)), dtype=float)

    def predict_distribution(self, X: pd.DataFrame, *, n_draws: int=200, random_seed: int | None=None) -> np.ndarray:
        matrix = self.encoder_.transform(X)
        mean, std = self.estimator_.predict(matrix, return_std=True)
        rng = np.random.default_rng(self.random_seed if random_seed is None else random_seed)
        return rng.normal(np.asarray(mean)[None, :], np.maximum(np.asarray(std), 1e-08)[None, :], size=(n_draws, len(mean)))

class BayesianMultilevelSurrogate(BaseSurrogate):
    model_name = 'bayesian_multilevel'
    family_name = 'Bayesian multilevel regression (ADVI)'

    @classmethod
    def dependency_reason(cls) -> str | None:
        return None if importlib.util.find_spec('pymc') else 'pymc:not_installed'

    @staticmethod
    def _posterior_array(idata: Any, name: str) -> np.ndarray:
        array = np.asarray(idata.posterior[name])
        return array.reshape((-1,) + array.shape[2:])

    def fit(self, X: pd.DataFrame, y: np.ndarray, *, groups: np.ndarray) -> 'BayesianMultilevelSurrogate':
        y = np.asarray(y, dtype=float)
        self._assert_eligible(y)
        groups = np.asarray(groups).astype(str)
        self.preprocessor_ = _SklearnPreprocessor(self.numeric_features, self.categorical_features).fit(X)
        matrix = self.preprocessor_.transform(X)
        self.target_mean_ = float(np.mean(y))
        self.target_scale_ = float(max(np.std(y, ddof=1), 1.0))
        scaled_y = (y - self.target_mean_) / self.target_scale_
        unique_groups = sorted(set(groups))
        group_map = {group: index for index, group in enumerate(unique_groups)}
        group_index = np.array([group_map[group] for group in groups], dtype=int)
        import pymc as pm
        with pm.Model() as model:
            alpha = pm.Normal('alpha', mu=0.0, sigma=1.0)
            beta = pm.Normal('beta', mu=0.0, sigma=0.7, shape=matrix.shape[1])
            tau_family = pm.HalfNormal('tau_family', sigma=0.6)
            family_effect = pm.Normal('family_effect', mu=0.0, sigma=tau_family, shape=len(unique_groups))
            sigma = pm.HalfNormal('sigma', sigma=1.0)
            mu = alpha + pm.math.dot(matrix, beta) + family_effect[group_index]
            pm.StudentT('observation', nu=5.0, mu=mu, sigma=sigma, observed=scaled_y)
            approximation = pm.fit(n=int(self.params.get('advi_steps', 1200)), method='advi', random_seed=self.random_seed, progressbar=False)
            idata = approximation.sample(draws=int(self.params.get('posterior_draws', 240)), random_seed=self.random_seed, return_inferencedata=True)
        self.posterior_ = {'alpha': self._posterior_array(idata, 'alpha'), 'beta': self._posterior_array(idata, 'beta'), 'sigma': self._posterior_array(idata, 'sigma')}
        self._record_training_metadata(X, y, groups)
        self.training_metadata_['inference_method'] = 'ADVI_APPROXIMATE'
        self.training_metadata_['posterior_draws'] = int(len(self.posterior_['alpha']))
        self.is_fitted_ = True
        return self

    def _linear_draws(self, X: pd.DataFrame, indices: np.ndarray) -> np.ndarray:
        matrix = self.preprocessor_.transform(X)
        return self.posterior_['alpha'][indices][:, None] + self.posterior_['beta'][indices] @ matrix.T

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError('Model is not fitted')
        indices = np.arange(len(self.posterior_['alpha']))
        scaled = np.mean(self._linear_draws(X, indices), axis=0)
        return self.target_mean_ + self.target_scale_ * scaled

    def predict_distribution(self, X: pd.DataFrame, *, n_draws: int=200, random_seed: int | None=None) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError('Model is not fitted')
        rng = np.random.default_rng(self.random_seed if random_seed is None else random_seed)
        indices = rng.integers(0, len(self.posterior_['alpha']), size=n_draws)
        linear = self._linear_draws(X, indices)
        sigma = np.maximum(self.posterior_['sigma'][indices], 1e-06)[:, None]
        scaled = linear + rng.standard_t(5.0, size=linear.shape) * sigma
        return self.target_mean_ + self.target_scale_ * scaled

def model_params(profile: Any) -> dict[str, dict[str, Any]]:
    return {'elastic_net': {'bootstrap_models': profile.bootstrap_models}, 'random_forest': {'n_estimators': profile.rf_trees, 'bootstrap_models': max(2, profile.bootstrap_models - 1)}, 'catboost': {'iterations': profile.catboost_iterations, 'ensemble_size': profile.catboost_ensemble}, 'mixed_gp': {'maximum_training_rows': profile.gp_max_rows}, 'bayesian_multilevel': {'advi_steps': profile.advi_steps, 'posterior_draws': profile.posterior_draws}}

def make_model(name: str, *, profile: Any, random_seed: int, numeric_features: Iterable[str]=NUMERIC_FEATURES, categorical_features: Iterable[str]=CATEGORICAL_FEATURES) -> BaseSurrogate:
    classes: dict[str, type[BaseSurrogate]] = {'elastic_net': ElasticNetSurrogate, 'random_forest': RandomForestSurrogate, 'catboost': CatBoostSurrogate, 'mixed_gp': MixedGPSurrogate, 'bayesian_multilevel': BayesianMultilevelSurrogate}
    if name not in MODEL_NAMES:
        raise KeyError(f'Unknown model family: {name}')
    return classes[name](numeric_features=numeric_features, categorical_features=categorical_features, params=model_params(profile)[name], random_seed=random_seed)
