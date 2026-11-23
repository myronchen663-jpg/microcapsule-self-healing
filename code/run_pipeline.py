from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time

sys.dont_write_bytecode=True


def main():
    parser=argparse.ArgumentParser(description='Generate, train, score, and compare microcapsule simulations.')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    package=Path(__file__).resolve().parents[1]
    if output==package or package in output.parents:
        raise ValueError('Choose an output directory outside the training package')
    output.mkdir(parents=True,exist_ok=False)
    runtime=output/'runtime'
    runtime.mkdir()
    for key,subdir in [('TMPDIR','tmp'),('XDG_CACHE_HOME','cache'),('MPLCONFIGDIR','matplotlib'),('NUMBA_CACHE_DIR','numba')]:
        directory=runtime/subdir;directory.mkdir();os.environ[key]=str(directory)
    os.environ['PYTENSOR_FLAGS']='base_compiledir='+str(runtime/'pytensor')
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']:
        os.environ[key]='1'
    started=time.monotonic()
    import numpy as np
    import pandas as pd
    from settings import read_data
    from generate import generate_training, generate_candidates, assign_split
    from train import train_models
    from score import score_candidates
    from compare import compare_frame,compare_results
    frame=read_data('training_data.csv')
    generated=generate_training(read_data('literature_anchor.csv'))
    generation_comparison=compare_frame('training_data',generated,frame,'syn_row_id')
    (output/'generation_comparison.json').write_text(json.dumps(generation_comparison,indent=2)+'\n')
    if any(x['mismatch_count'] for x in generation_comparison):
        raise ValueError('Generated data differs beyond the comparison tolerance')
    if not np.array_equal(assign_split(frame).to_numpy(),frame['split'].to_numpy()):
        raise ValueError('Stored partition differs from the seeded family split')
    generated.to_csv(output/'generated_training_data.csv',index=False)
    candidates=read_data('candidates.csv')
    generated_candidates=generate_candidates()
    candidate_comparison=compare_frame('candidates',generated_candidates,candidates,'candidate_id')
    (output/'candidate_generation_comparison.json').write_text(json.dumps(candidate_comparison,indent=2)+'\n')
    if any(x['mismatch_count'] or x['bitwise_difference_count'] for x in candidate_comparison):
        raise ValueError('Generated candidates differ from stored candidates')
    generated_candidates.to_csv(output/'generated_candidates.csv',index=False)
    predictions,test,raw,cal_raw,calibration,metrics=train_models(frame,candidates)
    predictions.to_csv(output/'predictions.csv',index=False)
    test.to_csv(output/'test_predictions.csv',index=False)
    metrics.to_csv(output/'model_metrics.csv',index=False)
    np.savez(output/'draws.npz',candidate=raw,calibration=cal_raw)
    # Weighting uses the decimal serialization followed by the default parser.
    # Input data and comparisons use round-trip parsing.
    test_for_weights=pd.read_csv(output/'test_predictions.csv')
    scores,parameters=score_candidates(test_for_weights,calibration,raw,cal_raw,candidates['candidate_id'],metrics,output)
    scores=scores.loc[:,read_data('reference_scores.csv').columns]
    scores.to_csv(output/'scores.csv',index=False)
    def convert(value):
        if isinstance(value,np.ndarray):return value.tolist()
        if isinstance(value,np.generic):return value.item()
        raise TypeError(type(value).__name__)
    (output/'parameters.json').write_text(json.dumps(parameters,default=convert,indent=2)+'\n')
    report=compare_results(generated,generated_candidates,predictions,scores,parameters,output)
    environment={'python':platform.python_version(),'system':platform.system(),'machine':platform.machine(),'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'seconds':time.monotonic()-started,'training_source':'training_data.csv','generated_numeric_bitwise_difference_count':sum(x['bitwise_difference_count'] or 0 for x in generation_comparison)}
    (output/'environment.json').write_text(json.dumps(environment,indent=2)+'\n')
    print(json.dumps({'completed':True,'comparisons_within_tolerance':report['all_comparisons_within_tolerance'],'seconds':environment['seconds']}),flush=True)


if __name__=='__main__':
    main()
