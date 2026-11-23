from __future__ import annotations
import hashlib
from typing import Any, Iterable
import numpy as np
import pandas as pd
from settings import GLOBAL_SEED
def seed32(label: str, *keys: object) -> int:
    payload = '|'.join([str(GLOBAL_SEED), label, *map(str, keys)])
    value = int(hashlib.sha256(payload.encode('utf-8')).hexdigest()[:8], 16)
    return 1 + value % (2 ** 32 - 2)

def weighted_empirical_quantiles(values: np.ndarray, model_weights: np.ndarray, quantiles: Iterable[float]) -> np.ndarray:
    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 3:
        raise ValueError('values must have shape (item, model, draw)')
    n_item, n_model, n_draw = data.shape
    weights = np.asarray(model_weights, dtype=np.float64)
    if weights.shape != (n_model,):
        raise ValueError('model weight shape mismatch')
    atom_weights = np.repeat(weights / float(n_draw), n_draw)
    q_values = tuple((float(q) for q in quantiles))
    output = np.empty((n_item, len(q_values)), dtype=np.float64)
    for index in range(n_item):
        flattened = data[index].reshape(-1)
        order = np.argsort(flattened, kind='mergesort')
        sorted_values = flattened[order]
        cumulative = np.cumsum(atom_weights[order])
        for q_index, q in enumerate(q_values):
            location = int(np.searchsorted(cumulative, q, side='left'))
            output[index, q_index] = sorted_values[min(location, len(sorted_values) - 1)]
    return output

def deterministic_rank(score: np.ndarray, p_l: np.ndarray, probability: np.ndarray, delta: np.ndarray, confidence: np.ndarray, candidate_ids: np.ndarray) -> np.ndarray:
    order = np.lexsort((candidate_ids.astype(str), -np.asarray(confidence, dtype=np.float64), np.asarray(delta, dtype=np.float64), -np.asarray(probability, dtype=np.float64), -np.asarray(p_l, dtype=np.float64), -np.asarray(score, dtype=np.float64)))
    ranks = np.empty(len(order), dtype=np.int32)
    ranks[order] = np.arange(1, len(order) + 1, dtype=np.int32)
    return ranks
