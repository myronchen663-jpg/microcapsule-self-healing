from __future__ import annotations
import numpy as np
import pandas as pd
from settings import *
from numerics import weighted_empirical_quantiles, deterministic_rank
from generate import calibration_orders
from ensemble import compute_weights, _dense_test_arrays, _base_grade
import calibrate as cal


def calibration_inputs(frame, raw, weights, common_index):
    COMMON_INDEX = common_index
    family = frame['syn_scenario_family_id'].astype(str).to_numpy()
    row_id = frame['syn_row_id'].astype(str).to_numpy()
    observed = frame.loc[:,list(ENDPOINT_SOURCE.values())].to_numpy(dtype=np.float64)
    label = ((observed[:,0]>=THRESHOLD['H']) & (observed[:,1]<=THRESHOLD['Q'])).astype(np.float64)
    hit = ((raw[:,:,0,:]>=THRESHOLD['H']) & (raw[:,:,1,:]<=THRESHOLD['Q'])).sum(axis=2)
    p_model = (hit+0.5)/(DRAWS+1.0)
    p0 = p_model[:, COMMON_INDEX] @ weights[COMMON_INDEX]
    fit_order, eval_order = calibration_orders(family)
    fit_mask = np.isin(family,fit_order)
    eval_mask = np.isin(family,eval_order)
    pi_fit = float((label[fit_mask].sum()+0.5)/251.0)
    reference_brier = float(np.mean((pi_fit-label[eval_mask])**2))
    intervals = {}
    for i,endpoint in enumerate(ENDPOINTS):
        post = np.clip(raw[:,COMMON_INDEX,i,:],*SUPPORT[endpoint])
        quantiles = weighted_empirical_quantiles(post,weights[COMMON_INDEX],(0.05,0.95))
        lower, upper = quantiles[eval_mask,0], quantiles[eval_mask,1]
        truth = observed[eval_mask,i]
        covered = (lower<=truth) & (truth<=upper)
        interval_score = upper-lower+20.0*(lower-truth)*(truth<lower)+20.0*(truth-upper)*(truth>upper)
        intervals[endpoint] = {'coverage90':float(covered.mean()),'nis90':float(interval_score.sum()/(250.0*(SUPPORT[endpoint][1]-SUPPORT[endpoint][0])))}
    return {'family':family,'row_id':row_id,'observed':observed,'label':label,'p_model':p_model,'p0':p0,'fit_mask':fit_mask,'eval_mask':eval_mask,'fit_order':fit_order,'eval_order':eval_order,'all_family_order':fit_order+eval_order,'pi_fit':pi_fit,'reference_brier':reference_brier,'intervals':intervals}


def calibration_rounds(data):
    rows=[]
    selected_id=None
    for round_id,ridge in enumerate(cal.RIDGES):
        fit=cal._fit_round(round_id,ridge,data)
        probability=cal._apply_map(data['p0'],fit['theta'],fit['lambda_mix'])
        point,bootstrap=cal._bootstrap_round_metrics(round_id,probability,data)
        core,all_pass=cal._passes(point)
        count,total,gaps=cal._violations(point)
        row={'round_id':round_id,'ridge':cal._ridge_label(ridge),'lambda_mix':fit['lambda_mix'],'fit_status':fit['fit_status'],**point,'core_pass':int(core),'all_pass':int(all_pass),'violation_count':count,'violation_sum':total,'failure_gaps':gaps,'improve_flag':0,'theta':fit['theta']}
        if rows:
            improvement,worsening,improved,worsened=cal._improvement_vectors(rows[-1],row)
            row['improve_flag']=int(improved)
        strict_stop=round_id>=2 and all_pass and row['improve_flag']==0 and rows[-1]['improve_flag']==0
        rows.append(row)
        print(f'Calibration round {round_id}: Brier={point["brier"]:.12g}',flush=True)
        if strict_stop:
            selected_id=round_id
            break
    selected=min(rows,key=cal._select_key) if selected_id is None else rows[selected_id]
    return selected,rows


def candidate_components(ids,raw,weights,common_index):
    COMMON_INDEX = common_index
    hit=((raw[:,:,0,:]>=THRESHOLD['H']) & (raw[:,:,1,:]<=THRESHOLD['Q'])).sum(axis=2)
    alpha=hit+0.5
    p_model=alpha/(DRAWS+1.0)
    p0=p_model[:, COMMON_INDEX] @ weights[COMMON_INDEX]
    delta=np.sqrt(np.sum(weights[COMMON_INDEX]*(p_model[:,COMMON_INDEX]-p0[:,None])**2,axis=1))
    p_healing=((raw[:,:,0,:]>=THRESHOLD['H']).sum(axis=2)+0.5)/(DRAWS+1.0)
    p_penalty=((raw[:,:,1,:]<=THRESHOLD['Q']).sum(axis=2)+0.5)/(DRAWS+1.0)
    delta_ind=np.abs(p0-np.sum(weights[COMMON_INDEX]*p_healing[:,COMMON_INDEX]*p_penalty[:,COMMON_INDEX],axis=1))
    clip_rates=[];boundary=[]
    for i,e in enumerate(ENDPOINTS):
        lo,hi=SUPPORT[e]
        clip_rates.append(np.mean(np.abs(raw[:,:,i,:]-np.clip(raw[:,:,i,:],lo,hi))>1e-12,axis=2))
        boundary.append(np.mean((raw[:,:,i,:]<=lo+1e-9)|(raw[:,:,i,:]>=hi-1e-9),axis=2))
    clip_max=np.max(np.stack(clip_rates,axis=2)[:,COMMON_INDEX,:],axis=(1,2))
    boundary_max=np.max(np.stack(boundary,axis=2)[:,COMMON_INDEX,:],axis=(1,2))
    q_clip=np.clip(1.0-np.maximum(np.maximum(clip_max-0.30,0.0)/0.70,np.maximum(boundary_max-0.60,0.0)/0.40),0.0,1.0)
    return {'candidate_id':np.asarray(ids).astype(str),'hit_joint':hit,'alpha':alpha,'beta':DRAWS-hit+0.5,'p_model':p_model,'p0':p0,'delta':delta,'delta_ind':delta_ind,'clip_rate_max':clip_max,'boundary_mass_max':boundary_max,'Q_clip':q_clip}


def score_candidates(test,calibration,raw,cal_raw,ids,metrics,output):
    print('Computing ensemble weights',flush=True)
    eligibility = metrics.pivot(index='model', columns='endpoint', values='eligible').reindex(index=MODELS, columns=list(ENDPOINT_SOURCE.values()))
    if eligibility.isna().any().any():
        raise ValueError('Incomplete model eligibility grid')
    common_models = tuple(eligibility.index[eligibility.all(axis=1)])
    if len(common_models) != 4:
        raise ValueError(f'Ensemble weighting requires exactly four eligible models; got {len(common_models)}: {list(common_models)}')
    weights_result=compute_weights(_dense_test_arrays(test, common_models))
    common_index=weights_result['common_index']
    weights=weights_result['weights']
    data=calibration_inputs(calibration,cal_raw,weights,common_index)
    np.save(output/'calibration_p0.npy',data['p0'],allow_pickle=False)
    selected,rounds=calibration_rounds(data)
    final=cal._refit_final_calibrator(data,selected)
    if not final['success']:g_cal=0.50
    elif selected['all_pass']:g_cal=1.0
    elif selected['core_pass']:g_cal=0.85
    else:g_cal=0.65
    theta,fallback,bootstrap_frame=cal._bootstrap_final_calibrators(data,selected,final)
    candidate=candidate_components(ids,raw,weights,common_index)
    pb,db,theta_common=cal._candidate_bootstraps(candidate,weights_result,theta,final['lambda_mix'])
    probability=cal._apply_map(candidate['p0'],final['theta'],final['lambda_mix'])
    pl=np.quantile(pb,0.025,axis=0)
    pu=np.quantile(pb,0.975,axis=0)
    components=cal._score_components(probability,pl,pu,candidate['delta'],candidate['Q_clip'],g_cal)
    rank=deterministic_rank(components['S'],pl,probability,candidate['delta'],components['probability_confidence'],candidate['candidate_id'])
    grade=_base_grade(components['S'],probability,pl,components['W'])
    rb=cal._rank_bootstraps(pb,db,pl,components,candidate['candidate_id'],g_cal)
    loo,summaries=cal._loo_ranks(candidate,weights_result,final,theta,theta_common,candidate['Q_clip'],g_cal)
    pi20=np.mean(rb<=20,axis=0)
    rank_q90=np.quantile(rb.astype(np.float64),0.90,axis=0)
    loo_max=loo.max(axis=0)
    frame=pd.DataFrame({'candidate_id':candidate['candidate_id'],'P_cal':probability,'P_L':pl,'P_U':pu,'S':components['S'],'grade':grade,'rank':rank,'percentile':100.0*(N_CANDIDATES-rank)/(N_CANDIDATES-1.0),'pi20':pi20,'rank_q90':rank_q90,'loo_rank_max':loo_max,'stable_flag':((pi20>=0.50)&(rank_q90<=80)&(loo_max<=100)).astype(np.int8),'eligible_flag':(np.isin(grade,['A','B'])&(pl>=0.40)).astype(np.int8),'p0':candidate['p0'],'P':probability,**{k:candidate[k] for k in ['delta','delta_ind','clip_rate_max','boundary_mass_max','Q_clip']},'W':components['W'],'h':components['h'],'G_cal':g_cal,'G_path':1.0,'probability_confidence':components['probability_confidence'],'base_grade':grade,'calibration_round':selected['round_id'],'calibration_ridge':float(selected['ridge']),'calibration_lambda_mix':final['lambda_mix'],'process_factor':0.0})
    for i,m in enumerate(MODELS):
        frame[f'k_joint__{m}']=candidate['hit_joint'][:,i]
        frame[f'p_model__{m}']=candidate['p_model'][:,i]
    np.save(output/'weight_bootstrap.npy',weights_result['weight_bootstrap'],allow_pickle=False)
    np.save(output/'probability_bootstrap.npy',pb,allow_pickle=False)
    np.save(output/'rank_bootstrap.npy',rb,allow_pickle=False)
    np.save(output/'loo_ranks.npy',loo,allow_pickle=False)
    bootstrap_frame.to_csv(output/'calibrator_bootstrap.csv',index=False)
    parameters={'eligible_models':list(common_models),'weights':dict(zip(MODELS,weights)),'calibrator':{'theta':final['theta'],'ridge':float(selected['ridge']),'lambda_mix':final['lambda_mix'],'round':selected['round_id']},'G_cal':g_cal,'bootstrap_fit_fallback_count':int(fallback.sum()),'rounds':rounds,'effective_model_count':weights_result['n_eff'],'equal_blend':weights_result['eta_star']}
    return frame,parameters
