"""Small CPU-tested candidate objectives. No generation, provider or training driver.
DPO=sum-response-logp then pair mean; winnerSFT=global chosen-token mean.
GRPO-style=population-std group advantage, clipped ratio, k3 reference KL,
sequence-token mean then all-sequence mean; no-mixed pool blocks the update.
"""
import copy, hashlib, json, random, math
import torch
import torch.nn.functional as F

def need(ok,msg):
    if not ok:raise ValueError(msg)

def query_logps(logits,ids,attention,prompts,span_fn,*,temperature=1.,legal_masks=None):
    need(logits.ndim==3 and logits.shape[0]==len(ids)==len(attention)==len(prompts),'batch alignment')
    need(type(temperature) in (int,float) and temperature>0 and torch.isfinite(torch.tensor(temperature)),'positive finite temperature')
    result=[]
    for b,(row,mask,prompt) in enumerate(zip(ids,attention,prompts)):
        span=span_fn(row,mask,query_prompt_ids=prompt)
        need(len(row)==logits.shape[1] and logits.shape[-1]==16,'complete sixteen-vocab rows')
        pos=torch.tensor(span['prediction_positions'],device=logits.device)
        targets=torch.tensor(span['target_ids'],device=logits.device)
        z=logits[b,pos,:].float()/temperature
        need(bool(torch.isfinite(z).all()),'finite response logits')
        if legal_masks is not None:
            legal=legal_masks[b]
            need(legal.dtype==torch.bool and legal.shape==z.shape and bool(legal.any(-1).all()),'exact nonempty legal mask')
            need(bool(legal.gather(-1,targets[:,None]).all()),'selected token must be legal')
            z=z.masked_fill(~legal,-torch.inf)
        lp=F.log_softmax(z,dim=-1).gather(-1,targets[:,None]).squeeze(-1)
        need(lp.numel()>0 and bool(torch.isfinite(lp).all()),'finite nonempty query logprobs')
        result.append(lp)
    return result

def _vectors(v):
    need(type(v) is list and len(v)>0 and all(torch.is_tensor(x) and x.ndim==1 and x.numel()>0 and bool(torch.isfinite(x).all()) for x in v),'nonempty finite response vectors')

def _denominator(local_count,global_count):
    value=local_count if global_count is None else global_count
    need(type(value)is int and value>=local_count>0,'exact positive global denominator, no local-mean shard shortcut')
    return value

def dpo(chosen,rejected,ref_chosen,ref_rejected,beta=.1,*,global_pairs=None):
    for v in (chosen,rejected,ref_chosen,ref_rejected):_vectors(v)
    need(len(chosen)==len(rejected)==len(ref_chosen)==len(ref_rejected),'equal pair count')
    need(type(beta) in (int,float) and beta>0 and torch.isfinite(torch.tensor(beta)),'positive finite beta')
    for live,ref in ((chosen,ref_chosen),(rejected,ref_rejected)):
        need(all(x.shape==r.shape and not r.requires_grad for x,r in zip(live,ref)),'frozen exact reference length')
    margin=torch.stack([(c.float().sum()-rc.float().sum())-(r.float().sum()-rr.float().sum()) for c,r,rc,rr in zip(chosen,rejected,ref_chosen,ref_rejected)])
    return -F.logsigmoid(beta*margin).sum()/_denominator(len(chosen),global_pairs)

def winner_nll(chosen,*,global_tokens=None):
    _vectors(chosen)
    return -torch.stack([x.float().sum()for x in chosen]).sum()/_denominator(sum(x.numel()for x in chosen),global_tokens)

def grpo(live,old,reference,rewards,*,group_size=4,clip=.2,kl_beta=.01,std_epsilon=1e-8,global_sequences=None,global_mixed_groups=None):
    for v in (live,old,reference):_vectors(v)
    need(type(clip) in (int,float) and 0<clip<1 and type(kl_beta) in (int,float) and kl_beta>=0 and type(std_epsilon) in (int,float) and std_epsilon>0 and all(math.isfinite(x) for x in (clip,kl_beta,std_epsilon)), 'finite GRPO proposal parameters')
    n=len(live);need(type(group_size)is int and group_size==4 and n%group_size==0 and len(old)==len(reference)==n,'complete G4 groups')
    need(rewards.ndim==1 and rewards.numel()==n and not rewards.requires_grad and bool(((rewards==0)|(rewards==1)).all()),'fixed verified binary outcomes')
    need(all(l.shape==o.shape==r.shape and not o.requires_grad and not r.requires_grad for l,o,r in zip(live,old,reference)),'frozen exact old/ref vectors')
    grouped=rewards.float().reshape(-1,group_size);std=grouped.std(dim=1,unbiased=False);mixed=std>0
    meta={'groups':int(grouped.shape[0]),'mixed_groups':int(mixed.sum()),'all_zero_groups':int((grouped.sum(1)==0).sum()),'all_one_groups':int((grouped.sum(1)==group_size).sum()),'optimizer_commit_allowed':bool(mixed.any())}
    if global_mixed_groups is not None:
        need(type(global_mixed_groups)is int and global_mixed_groups>=meta['mixed_groups'],'global mixed-group count')
        meta['optimizer_commit_allowed']=global_mixed_groups>0
    if not meta['optimizer_commit_allowed']:return None,meta
    adv=((grouped-grouped.mean(1,keepdim=True))/(std[:,None]+std_epsilon)).reshape(-1).detach()
    losses=[]
    for i,(pi,mu,ref) in enumerate(zip(live,old,reference)):
        pi=pi.float();ratio=(pi-mu.float()).exp();d=ref.float()-pi;k3=d.exp()-d-1
        need(bool(torch.isfinite(ratio).all()) and bool(torch.isfinite(k3).all()),'nonfinite ratio/KL fails closed')
        surrogate=torch.minimum(ratio*adv[i],ratio.clamp(1-clip,1+clip)*adv[i])
        losses.append((-surrogate+kl_beta*k3).mean())
    return torch.stack(losses).sum()/_denominator(n,global_sequences),meta

def cpu_snapshot(model,optimizer):
    need(all(p.device.type=='cpu'for p in model.parameters()),'CPU-only reset probe;TPU RNG not claimed')
    import numpy as np
    return {'model':copy.deepcopy(model.state_dict()),'optimizer':copy.deepcopy(optimizer.state_dict()),'torch_rng':torch.get_rng_state().clone(),'python_rng':random.getstate(),'numpy_rng':copy.deepcopy(np.random.get_state())}

def cpu_restore(model,optimizer,snapshot):
    import numpy as np
    model.load_state_dict(snapshot['model'],strict=True);optimizer.load_state_dict(snapshot['optimizer']);optimizer.zero_grad(set_to_none=True)
    torch.set_rng_state(snapshot['torch_rng']);random.setstate(snapshot['python_rng']);np.random.set_state(snapshot['numpy_rng'])
    need(all(torch.equal(v,snapshot['model'][k])for k,v in model.state_dict().items()),'model reset exact')
    return True
