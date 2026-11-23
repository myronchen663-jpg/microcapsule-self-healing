from __future__ import annotations
import csv
import json
import numpy as np
import pandas as pd
from settings import CONFIG, read_data


def compare_frame(name, actual, reference, key):
    if actual[key].duplicated().any() or reference[key].duplicated().any():
        raise ValueError('Comparison keys must be unique')
    if set(actual[key])!=set(reference[key]) or set(actual.columns)!=set(reference.columns):
        raise ValueError(f'Comparison schema or keys differ: {name}')
    actual=actual.set_index(key).loc[reference[key]].reset_index()
    rows=[]
    for column in reference.columns:
        a=actual[column];b=reference[column]
        if pd.api.types.is_numeric_dtype(b):
            av=a.to_numpy(dtype=np.float64);bv=b.to_numpy(dtype=np.float64)
            if not np.isfinite(av).all() or not np.isfinite(bv).all():raise ValueError('Nonfinite comparison value')
            difference=np.abs(av-bv)
            integer=pd.api.types.is_integer_dtype(b)
            tolerance=0.0
            rows.append({'table':name,'column':column,'rows':len(b),'kind':'integer' if integer else 'numeric','max_abs_difference':float(difference.max()),'mean_abs_difference':float(difference.mean()),'mismatch_count':int(np.count_nonzero(difference>tolerance)),'tolerance':tolerance,'bitwise_difference_count':int(np.count_nonzero(av.view(np.uint64)!=bv.view(np.uint64)))})
        else:
            rows.append({'table':name,'column':column,'rows':len(b),'kind':'text','max_abs_difference':None,'mean_abs_difference':None,'mismatch_count':int(np.count_nonzero(a.astype(str).to_numpy()!=b.astype(str).to_numpy())),'tolerance':0.0,'bitwise_difference_count':None})
    return rows


def compare_results(generated,generated_candidates,predictions,scores,parameters,output):
    rows=[]
    rows+=compare_frame('training_data',generated,read_data('training_data.csv'),'syn_row_id')
    rows+=compare_frame('candidates',generated_candidates,read_data('candidates.csv'),'candidate_id')
    rows+=compare_frame('predictions',predictions,read_data('reference_predictions.csv'),'candidate_id')
    rows+=compare_frame('scores',scores,read_data('reference_scores.csv'),'candidate_id')
    for name,value in parameters['weights'].items():
        diff=abs(value-CONFIG['reference_weights'][name])
        rows.append({'table':'weights','column':name,'rows':1,'kind':'numeric','max_abs_difference':diff,'mean_abs_difference':diff,'mismatch_count':int(diff!=0.0),'tolerance':0.0,'bitwise_difference_count':int(np.float64(value).view(np.uint64)!=np.float64(CONFIG['reference_weights'][name]).view(np.uint64))})
    for name,value in parameters['calibrator'].items():
        delta=np.abs(np.asarray(value,dtype=float)-np.asarray(CONFIG['reference_calibrator'][name],dtype=float))
        rows.append({'table':'calibrator','column':name,'rows':int(delta.size),'kind':'numeric','max_abs_difference':float(delta.max()),'mean_abs_difference':float(delta.mean()),'mismatch_count':int(np.count_nonzero(delta!=0.0)),'tolerance':0.0,'bitwise_difference_count':None})
    pd.DataFrame(rows).to_csv(output/'comparison.csv',index=False)
    report={'all_comparisons_within_tolerance':all(x['mismatch_count']==0 for x in rows),'columns':rows}
    (output/'comparison.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report
