"""One train-only fixed record per parent; targets never enter actor arguments."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from .common import need, digest, canonical
from . import ROOT
from pathlib import Path
from tools.arc_learning_agent_20261011.data import validate_records
from tools.arc_learning_agent_20261011.grid_codec import decode_grid, GridContractError
from tools.arc_qwen_transfer_20261012.data import (_native_record,load_inventory,freeze_panels,
    _fixture,PUBLIC_EXCLUSIONS_SHA256)
from tools.arc_qwen_transfer_20261012.protocol import checked_json
from tools.arc_qwen_transfer_20261012 import arc_adaptation as aa

@dataclass(frozen=True)
class Prompt:
    parent_id:str
    record_id:str
    messages_json:bytes
    target_sha256:str
    exclusion:str|None
    def messages(self):
        import json
        return json.loads(self.messages_json)

class RewardPanel:
    def __init__(self,dataset,*,sft_exposed_record_ids=(),training_root=None):
        need(dataset.get('original_test_fields_retained') is False and dataset.get('public_answers_read') is False,
             'demonstration-only dataset required')
        plan,manifest=dataset['plan'],dataset['manifest']
        self.fixture_only=dataset.get('cpu_fixture_only') is True
        inventory=load_inventory()
        if self.fixture_only:
            exclusions={'format':'irisx/public120-transfer-exclusions-v1','source':{'solver_manifest_sha256':'0'*64,'challenges_sha256':'0'*64},
                'public_parent_ids':['f%07x'%i for i in range(120)],'ancestor_ids':[],'aliases':[],'known_variant_groups':[]}
            original_tasks=_fixture(inventory)
        else:
            exclusions=checked_json(ROOT/'baseline/panel-freeze/public120-exclusions.json',PUBLIC_EXCLUSIONS_SHA256)
            need(training_root is not None,'production reward panel requires pinned original source bytes')
        partition,expected_plan=freeze_panels(inventory,exclusions)
        need(plan==expected_plan,'frozen plan/partition/order/hash changed')
        train,dev,held=(plan[k] for k in ('train_ids','dev_ids','holdout_ids'))
        need(len(train)==32 and len(dev)==16 and len(held)==32 and
             len(set(train+dev+held))==80,'frozen disjoint train32/dev16/heldout32')
        validate_records([],manifest,())
        need(set(train)=={k for k,v in manifest['tasks'].items() if v['split']=='train'},'training partition differs')
        self.fixture_only=dataset.get('cpu_fixture_only') is True
        self.prompts=[];self._targets={};self._owned={};self.rows=[]
        self.manifest_sha256=manifest['manifest_sha256']; self.plan_sha256=plan['plan_sha256']
        for parent in train:
            selected=None; error=None
            try:
                source=(aa.project_demonstrations(original_tasks[parent],inventory,parent) if self.fixture_only else
                    aa.project_source_bytes((Path(training_root)/(parent+'.json')).read_bytes(),inventory,parent))
                from dataclasses import asdict
                need(manifest['tasks'][parent]['demonstrations']==json_lists([asdict(e) for e in source.demos]),
                     'manifest source demonstrations differ from independently authenticated original')
                last=len(source.demos)-1
                matches=[r for r in dataset['records'] if r.get('task_id')==parent and
                    r.get('provenance',{}).get('augmentation_index')==0 and
                    r.get('provenance',{}).get('held_out_demo')==last]
                need(len(matches)==1,'one unique fixed identity last-demo record required')
                selected=matches[0];validate_records([selected],manifest,())
                p=selected['provenance'];a=p['transfer_record']
                need(p['augmentation']=={'rotation':0,'transpose':False,'colors':list(range(10))},'identity palette/D4 required')
                typed=aa.SupervisedRecord(aa.Lineage(**a['lineage']),
                    aa.Prompt(tuple(aa.Example(**e) for e in a['prompt']['examples']),a['prompt']['query_input']),
                    a['target'],a['withheld_demo_index'],tuple(a['context_demo_indices']),a['demo_count'],
                    aa.Transform(**a['transform']),a['purpose'],a['partition_sha256'])
                aa.validate_record(typed,source)
                need(typed.purpose=='optimizer' and typed.sha256==p['transfer_record_sha256'] and
                     typed.partition_sha256==plan['partition_sha256'],'typed optimizer lineage/partition differs')
                need(typed.demo_count==last+1 and typed.withheld_demo_index==last and
                     tuple(typed.context_demo_indices)==tuple(range(last)),'fixed last-demo fold differs')
                need(_native_record(typed,parent,selected['family_id'],p['source_task_sha256'])==selected,
                     'native prompt/target not exact typed projection')
                need(typed.lineage.parent_id==parent if hasattr(typed.lineage,'parent_id') else
                     a['lineage'].get('task_id')==parent,'typed parent differs')
                target=decode_grid(selected['completion'])
                self._targets[parent]=deepcopy(target)
            except (ValueError,KeyError,TypeError,AttributeError) as exc:
                error=type(exc).__name__+': '+str(exc)
            rid=selected.get('record_id','missing') if selected else 'missing'
            target_sha=digest(self._targets[parent]) if parent in self._targets else 'excluded'
            messages=selected['messages'] if error is None else []
            prompt=Prompt(parent,rid,canonical(messages),target_sha,error)
            self.prompts.append(prompt);self._owned[parent]=prompt
            self.rows.append({'parent_id':parent,'record_id':rid,'target_sha256':target_sha,
                'exclusion':error,'exposed_in_same_session_sft256':rid in set(sft_exposed_record_ids)})
        self.prompts=tuple(self.prompts);self._parent_ids=tuple(p.parent_id for p in self.prompts)
        self.panel_sha256=digest({'rows':self.rows,'manifest':self.manifest_sha256,'plan':self.plan_sha256,
            'selection':'identity0-last-original-demo','fixture_only':self.fixture_only})
    def admit_prompt(self,prompt):
        need(type(prompt) is Prompt and self._owned.get(prompt.parent_id)==prompt,'unknown/mutated reward prompt')
        need(prompt.exclusion is None,'excluded fixed parent: '+str(prompt.exclusion))
        return prompt.messages()
    def batch_prompts(self,batch_index):
        need(type(batch_index) is int and 0<=batch_index<4,'fixed batch index')
        need(len(self.prompts)==32 and tuple(p.parent_id for p in self.prompts)==self._parent_ids and
             len(set(self._parent_ids))==32,
             'complete fixed parent panel required')
        prompts=self.prompts[batch_index*8:(batch_index+1)*8]
        need(all(self._owned.get(p.parent_id)==p for p in self.prompts),'fixed prompt panel changed')
        return prompts
    def seed(self,batch_index,parent,sample):
        from owned_runtime.policy import POLICY_SHA256,load_policy
        load_policy() # Authenticate exact design bytes before using their experiment identity.
        need(parent in {p.parent_id for p in self.batch_prompts(batch_index)} and
             type(sample) is int and 0<=sample<8,'fixed batch/parent/sample index')
        return int(digest(['rl-fixed-batch-sampling-v1',POLICY_SHA256,self.plan_sha256,batch_index,parent,sample])[:15],16)
    def reward(self,prompt,trajectory):
        self.admit_prompt(prompt)
        need(trajectory['parent_id']==prompt.parent_id and trajectory['record_id']==prompt.record_id,
             'reward/actor record mismatch')
        need(trajectory['messages_sha256']==digest(prompt.messages()),'reward prompt differs from actor')
        if trajectory['infrastructure_excluded']:
            return {'reward':None,'eligible':False,'valid_grid':False,'reason':trajectory['finish_reason']}
        try:
            grid=decode_grid(trajectory['format_text']) if trajectory['finish_reason']=='eos' else None
        except GridContractError:
            grid=None
        return {'reward':int(grid is not None and grid==self._targets[prompt.parent_id]),
                'eligible':True,'valid_grid':grid is not None,'reason':'exact-training-LOO-equality',
                'target_sha256':prompt.target_sha256,'fixture_only':self.fixture_only}


def json_lists(x):
    import json
    return json.loads(json.dumps(x))
