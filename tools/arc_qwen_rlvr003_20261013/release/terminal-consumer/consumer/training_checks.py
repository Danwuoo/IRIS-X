"""Fixed train-only reward panel and actual committed SFT semantic order."""
import random
from .safe_io import need,digest,same
from .grid_checks import decode

SAMPLER='native-objective-family-order-v1-grid-only-seed1917-continuous-anchor-control'

def semantic_id(r):
    p=r.get('provenance',{})
    source={k:p[k] for k in ('source_task_sha256','objective','held_out_demo','visible_demo_indices','augmentation','augmentation_index','generator_family','authored_reference','generalization_claim','prompt_task') if k in p}
    if p.get('generation_context') is not None:
        source['generation_context']={k:p['generation_context'][k] for k in ('visible_indices','held_out_demo_index') if k in p['generation_context']}
    return digest({'format':'irisx/semantic-training-sample-v1','sample':{k:r[k] for k in ('split','task_id','parent_ids','family_id','kind','messages','completion')},'source':source})

def exposure_order(records,count):
    grouped={}
    for i,r in enumerate(records):grouped.setdefault(r['family_id'],[]).append(i)
    family_names=sorted(grouped);result=[]
    for epoch in range((count+len(records)-1)//len(records)):
        visits={};permutations={};order=[]
        for position in range(len(records)):
            family=family_names[position%len(family_names)];rows=grouped[family]
            visit=visits.get(family,0);pass_index,offset=divmod(visit,len(rows));key=(family,pass_index)
            if key not in permutations:
                values=sorted(rows,key=lambda i:semantic_id(records[i]))
                random.Random(digest(['objective-family-order-v1',1917,epoch,'grid',family,pass_index])).shuffle(values)
                permutations[key]=values
            order.append(permutations[key][offset]);visits[family]=visit+1
        result += [records[i]['record_id'] for i in order]
    return result[:count]

def reward_panel(dataset,checkpoints,result,*,synthetic):
    if synthetic and result.get('reward_panel',{}).get('scope')=='fabricated-G2-core-mechanics-only':
        panel=result['reward_panel']
        need(panel.get('sample_seeds')==[7,8] and panel.get('training_target')=='16' and panel.get('anchor_target')=='1', 'exact fabricated native reward recipe')
        need(panel.get('production_train32_reward_panel_executed') is False, 'tiny reward cannot claim train32 execution')
        need(all(c['training_identity'] is None for c in checkpoints.values()), 'tiny fixture cannot imply authenticated SFT training')
        return {'fabricated':{'record_id':'fixed-fixture','target':[[1,6]],'messages_sha256':digest([{'role':'user','content':'Return a small rectangular grid of digits. Grid only.'}]),'messages':[{'role':'user','content':'Return a small rectangular grid of digits. Grid only.'}]}}
    plan=dataset['plan'];train=plan['train_ids'];dev=plan['dev_ids'];held=plan['holdout_ids']
    need(len(train)==32 and len(dev)==16 and len(held)==32 and len(set(train+dev+held))==80, 'fixed disjoint train32/dev16/heldout32 required')
    records=dataset['records'];manifest=dataset['manifest']
    need(records and all(r['split']=='train' and r['kind']=='grid' and r['task_id'] in train for r in records), 'reward/SFT training-only record pool')
    need(len({r['record_id'] for r in records})==len(records), 'duplicate training record identity')
    for r in records:
        need(r['record_id']==digest({k:v for k,v in r.items() if k!='record_id'}),'training record content digest differs')
    identity=digest({'records':records,'manifest':manifest,'sampler':SAMPLER})
    for label,c in checkpoints.items():
        need(c['training_identity']==identity, 'actual checkpoint authenticated sampler/data differs')
        need(c['sft_exposed']==exposure_order(records,c['counts']['sampler_cursor']), 'committed SFT records/order differ')
    targets={};rows=[]
    for parent in train:
        demos=manifest['tasks'][parent]['demonstrations'];last=len(demos)-1
        selected=[r for r in records if r['task_id']==parent and r['provenance'].get('augmentation_index')==0 and r['provenance'].get('held_out_demo')==last]
        need(len(selected)==1,'one fixed identity last-demo reward record per parent')
        r=selected[0];p=r['provenance'];typed=p['transfer_record']
        need(same(p['augmentation'],{'rotation':0,'transpose':False,'colors':list(range(10))}), 'reward record transform is not identity')
        need(typed['withheld_demo_index']==last and typed['context_demo_indices']==list(range(last)) and typed['demo_count']==len(demos) and typed['purpose']=='optimizer', 'fixed training LOO fold differs')
        need(typed['target']==demos[last]['output'] and typed['prompt']['query_input']==demos[last]['input'] and typed['prompt']['examples']==demos[:last], 'reward LOO prompt/target data differs')
        target=decode(r['completion']);need(target==typed['target'],'reward completion differs')
        targets[parent]={'record_id':r['record_id'],'target':target,'messages_sha256':digest(r['messages']),'messages':r['messages']}
        rows.append({'parent_id':parent,'record_id':r['record_id'],'target_sha256':digest(target),'exclusion':None,'exposed_in_same_session_sft64':r['record_id'] in set(checkpoints['A']['sft_exposed'])})
    return targets
