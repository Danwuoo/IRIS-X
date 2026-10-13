"""Separately bounded C4096 native tokenizer/model and cache calibration.

Only constructors with historical fixed context guards are specialized. Actual
native generation, full-head likelihood, PEFT target checks and state operations
remain inherited. No global monkey-patching of historical modules is used.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import time
from pathlib import Path

from tools.arc_learning_agent_20261011.qwen14b_contract import NativePromptContract, canonical
from tools.arc_learning_agent_20261011.native_model import NativeGridConstraint, _canonical, _require
from tools.arc_qwen_probe_20261012.decoder import ProbeModel, cache_length, cache_metadata
from tools.arc_qwen_probe_20261012.cache_policy import choose, comparison
from tools.arc_qwen_probe_20261012.protocol import require, digest
from tools.arc_learning_agent_20261011.budget import atomic_json
from .model_profile import (MODEL_KEY, MODEL_ID, REVISION, PROFILE_ID, VOCAB_SIZE, EOS_IDS,
    CONTEXT_LIMIT, PROMPT_CAP, OUTPUT_CAP, LENGTH_LADDER, MATERIAL_ADDENDUM_SHA256,
    authenticate_small_assets, validate_model_config, load_pretrained, consume_load_evidence)

_CALIBRATIONS = {}  # successful owned calibrations only; never loaded from disk



class TransferPromptContract(NativePromptContract):
    """Historical native tokenizer/content proof, separately bound C4096 caps."""
    def __init__(self, tokenizer, *, vocab_size, eos_ids, context_limit=CONTEXT_LIMIT, output_cap=OUTPUT_CAP,
                 synthetic=False):
        require(type(synthetic) is bool, 'explicit boolean synthetic-tokenizer policy required')
        require(type(vocab_size) is int and vocab_size == VOCAB_SIZE, 'native full vocabulary size required')
        require(type(context_limit) is int and context_limit == CONTEXT_LIMIT and
                type(output_cap) is int and output_cap == OUTPUT_CAP, 'bounded prompt/output policy required')
        require(type(eos_ids) in (list, tuple) and eos_ids and
                all(type(i) is int and 0 <= i < vocab_size for i in eos_ids) and
                len(set(eos_ids)) == len(eos_ids), 'native EOS ID set required')
        self._native_vocab_getter = None
        if not synthetic:
            from transformers.tokenization_utils_tokenizers import TokenizersBackend
            getter = tokenizer.get_vocab
            require(getattr(getter, '__func__', None) is TokenizersBackend.get_vocab and
                    getattr(getter, '__self__', None) is tokenizer,
                    'exact owned native fast-tokenizer vocabulary getter required')
            self._native_vocab_getter = getter.__func__
        vocabulary = tokenizer.get_vocab()
        require(type(vocabulary) is dict and vocabulary and
                all(type(k) is str and type(v) is int and 0 <= v < vocab_size for k, v in vocabulary.items()),
                'native tokenizer IDs must agree with full source output head')
        require(type(tokenizer.eos_token_id) is int and tokenizer.eos_token_id in eos_ids and
                type(tokenizer.eos_token) is str and vocabulary.get(tokenizer.eos_token) == tokenizer.eos_token_id,
                'canonical EOS spelling/mapping required')
        self.tokenizer, self.vocab_size, self.eos_ids = tokenizer, vocab_size, tuple(eos_ids)
        self._synthetic_tokenizer = synthetic
        self.context_limit, self.output_cap = context_limit, output_cap
        self._pipeline_sha256 = self._tokenizer_pipeline_sha256()
        self._vocabulary_sha256 = hashlib.sha256(canonical(vocabulary)).hexdigest()
        if not synthetic:
            state = json.loads(tokenizer.backend_tokenizer.to_str())
            require(state['model']['type'] == 'BPE' and type(state['model']['vocab']) is dict and
                    type(state['added_tokens']) is list, 'reviewed native BPE vocabulary representation required')
            represented = dict(state['model']['vocab'])
            for token in state['added_tokens']:
                require(token['content'] not in represented or represented[token['content']] == token['id'],
                        'conflicting native backend vocabulary/added-token mapping')
                represented[token['content']] = token['id']
            require(represented == vocabulary, 'serialized native backend does not exactly represent get_vocab')
            self.vocabulary_derivation = {'verified': True, 'entries': len(represented),
                'policy': 'serialized-BPE-plus-added-tokens-equals-owned-inherited-get_vocab'}
        else:
            self.vocabulary_derivation = {'verified': False, 'policy': 'synthetic-full-map-check-at-each-boundary'}
        self._template_sha256 = hashlib.sha256(self._native_template().encode()).hexdigest()
        self._canonical_eos_id = tokenizer.eos_token_id
        self._canonical_eos_token = tokenizer.eos_token
        self._special_ids = tuple(sorted(tokenizer.all_special_ids))
        added = tokenizer.get_added_vocab() if hasattr(tokenizer, 'get_added_vocab') else {}
        control_ids = set(self._special_ids)
        control_ids.update(v for k, v in added.items() if k.startswith('<') and k.endswith('>'))
        self._control_ids = frozenset(control_ids)
        self._control_spellings = tuple(sorted(set(self._QWEN_FRAMING) |
            {k for k, v in vocabulary.items() if v in control_ids}))
        self._prepared_cache = {}  # at most8 immutable canonical byte records; never caller-owned lists
        self.prepared_cache_hits = 0
        self.contract_sha256 = hashlib.sha256(canonical({
            'format': 'irisx/qwen14b-c4096-prompt-contract-v1', 'vocabulary_sha256': self._vocabulary_sha256,
            'tokenizer_pipeline_sha256': self._pipeline_sha256, 'synthetic_tokenizer': synthetic,
            'vocabulary_derivation': self.vocabulary_derivation,
            'template_sha256': self._template_sha256, 'canonical_eos_id': self._canonical_eos_id,
            'generation_eos_ids': list(self.eos_ids), 'control_spellings': self._control_spellings,
            'full_vocabulary_size': vocab_size, 'context_limit': context_limit, 'output_cap': output_cap,
            'material_addendum_sha256': MATERIAL_ADDENDUM_SHA256, 'thinking': False, 'completion_policy': 'exact-native-completed-chat-no-content-normalization'
        })).hexdigest()


    def _assert_tokenizer_unchanged(self):
        require((self.context_limit, self.output_cap, self.vocab_size, self.eos_ids) ==
                (CONTEXT_LIMIT, OUTPUT_CAP, VOCAB_SIZE, tuple(EOS_IDS)),
                'successor live prompt contract bounds/identity changed')
        return super()._assert_tokenizer_unchanged()

    def prompt(self, messages):
        rendered, ids = super().prompt(messages)
        require(len(ids) <= PROMPT_CAP, 'prompt context exceeds successor3072 cap')
        return rendered, ids


class TransferModel(ProbeModel):
    def __init__(self, model, tokenizer, config=None):
        config = validate_model_config(config or {})
        _require(config.get('model_key') == MODEL_KEY, 'exact distinct Qwen14B key required')
        _require(type(config.get('tiny_cpu')) is bool, 'explicit tiny_cpu boolean required')
        if not config['tiny_cpu']:
            _loaded = consume_load_evidence(model, tokenizer, config)
        _require(config.get('precision', 'bf16-base-fp32-lora') == 'bf16-base-fp32-lora', 'Qwen14B BF16-base/FP32-LoRA only; no FP8 fallback')
        _require(type(config.get('tensor_parallel_size', 1)) is int and config.get('tensor_parallel_size', 1) == 1, 'Qwen14B tensor parallelism not admitted')
        _require(type(model).__name__ == 'Qwen3ForCausalLM', 'actual native Qwen3ForCausalLM required')
        if config['tiny_cpu']:
            _require(all(p.device.type == 'cpu' for p in model.parameters()), 'tiny Qwen3 fixture is CPU only')
            _require(sum(p.numel() for p in model.parameters()) <= 10_000_000, 'tiny Qwen3 fixture exceeds 10M parameters')
        self.config = config
        self.model, self.tokenizer = model, tokenizer
        self.tiny_cpu, self.closed = config['tiny_cpu'], False
        self._adapter_execution_mode, self._branch_context_active = 'trained', False
        self.context_limit = config['context_limit']
        self.prompt_cap = config['prompt_cap']
        self.output_cap = config['output_cap']
        for name, value, maximum in [('context_limit', self.context_limit, CONTEXT_LIMIT), ('prompt_cap', self.prompt_cap, PROMPT_CAP), ('output_cap', self.output_cap, OUTPUT_CAP)]:
            _require(type(value) is int and value == maximum, 'invalid Qwen14B ' + name)
        _require(self.prompt_cap < self.context_limit and self.output_cap < self.context_limit, 'prompt/output must leave context')
        self.vocab_size = model.get_output_embeddings().weight.shape[0]
        _require(self.vocab_size == VOCAB_SIZE and model.get_input_embeddings().weight.shape[0] == VOCAB_SIZE,
                 'Qwen14B retains all 151936 native input/output rows')
        _require(model.config.model_type == 'qwen3' and model.config.num_hidden_layers in ((1, 2) if self.tiny_cpu else (40,)), 'bounded native Qwen3 tiny topology required')
        import torch
        _require(all(p.dtype == torch.bfloat16 for p in model.parameters()), 'genuine BF16 random base required')
        self.prompt_contract = TransferPromptContract(tokenizer, vocab_size=self.vocab_size, eos_ids=EOS_IDS,
                                                    context_limit=self.context_limit, output_cap=self.output_cap)
        self._tokenizer_backend_sha256 = hashlib.sha256(tokenizer.backend_tokenizer.to_str().encode()).hexdigest()
        self.native_policy = self._current_policy()
        self.eos_ids = tuple(self.native_policy['generation_eos_ids'])
        self.constraint = NativeGridConstraint(tokenizer, self.eos_ids, tiny_cpu=self.tiny_cpu)
        initial = hashlib.sha256()
        for name, tensor in (sorted(model.named_parameters()) if self.tiny_cpu else []):
            initial.update(_canonical([name, str(tensor.dtype), list(tensor.shape)]))
            initial.update(tensor.detach().cpu().contiguous().view(-1).view(torch.uint8).numpy().tobytes())
        self.identity = {'format': 'irisx/qwen14b-native-interface-v1', 'model_key': MODEL_KEY,
                         'architecture': 'Qwen3ForCausalLM', 'reference_model_id': MODEL_ID, 'reference_revision': REVISION,
                         'profile_id': PROFILE_ID, 'material_addendum_sha256': MATERIAL_ADDENDUM_SHA256,
                         'context_limit': CONTEXT_LIMIT, 'prompt_cap': PROMPT_CAP, 'output_cap': OUTPUT_CAP, 'execution_mode': 'native-qwen3-tiny-random-cpu',
                         'random_test_weights': True, 'pretrained_weights_loaded': False, 'production_admitted': False,
                         'full_vocabulary_rows': self.vocab_size, 'actual_hidden_size': model.config.hidden_size,
                         'actual_layers': model.config.num_hidden_layers, 'base_precision': 'bfloat16',
                         'initial_neural_state_sha256': initial.hexdigest(), 'tokenizer_backend_sha256': self._tokenizer_backend_sha256, 'prompt_contract_sha256': self.prompt_contract.contract_sha256,
                         'small_asset_identity': deepcopy(config.get('small_asset_identity'))}
        self.hardware = {'status': 'cpu-fixture-only', 'g4_fit_measured': False, 'four_l4_tp_admitted': False, 'fp8_admitted': False}
        if not self.tiny_cpu:
            self.identity, self.hardware = deepcopy(_loaded)
            self.identity['tokenizer_backend_sha256'] = self._tokenizer_backend_sha256
            self.identity['prompt_contract_sha256'] = self.prompt_contract.contract_sha256
        self._calibration_receipt = None
        self.adapter_state_sha256 = None
        self._fingerprint_cache = None
        self.fingerprint_cache_hits = self.fingerprint_rehashes = 0

    @classmethod
    def from_config(cls, config):
        config = validate_model_config(config)
        _require(config.get('model_key') == MODEL_KEY, 'exact Qwen14B model key required')
        _require(type(config.get('tiny_cpu', False)) is bool, 'exact tiny_cpu boolean required')
        if not config.get('tiny_cpu', False):
            model, tokenizer = load_pretrained({**config, 'tiny_cpu': False})
            return cls(model, tokenizer, {**config, 'tiny_cpu': False})
        _require(config.get('tokenizer_path'), 'authenticated local Qwen14B tokenizer path required')
        assets = authenticate_small_assets(config['tokenizer_path'])
        hidden = config.get('tiny_hidden_size', 16)
        _require(type(hidden) is int and hidden in (8, 16), 'tiny hidden size must be 8 or 16')
        _require(type(config.get('seed', 0)) is int and 0 <= config.get('seed', 0) < 2**63, 'bounded integer fixture seed required')
        import torch
        from transformers import AutoTokenizer, Qwen3Config, Qwen3ForCausalLM
        tokenizer = AutoTokenizer.from_pretrained(config['tokenizer_path'], local_files_only=True, trust_remote_code=False, use_fast=True)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(config.get('seed', 0))
            model = Qwen3ForCausalLM(Qwen3Config(vocab_size=VOCAB_SIZE, hidden_size=hidden,
                intermediate_size=hidden * 2, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1,
                head_dim=hidden // 2, max_position_embeddings=CONTEXT_LIMIT, eos_token_id=151645,
                pad_token_id=151643, bos_token_id=151643, attention_dropout=0.0, tie_word_embeddings=False))
            model = model.to(device='cpu', dtype=torch.bfloat16)
        model.generation_config.eos_token_id = list(EOS_IDS)
        model.generation_config.pad_token_id = 151643
        return cls(model, tokenizer, {**config, 'small_asset_identity': assets})

    def generate(self, messages, *, kind, seed, max_new_tokens, deadline):
        # Instrument only this successor. The exact historical native loop and
        # its synchronization/cache/finite-head/reset checks remain unchanged.
        entered = time.monotonic()
        result = super().generate(messages, kind=kind, seed=seed,
                                  max_new_tokens=max_new_tokens, deadline=deadline)
        result['native_timing'] = {'clock': 'time.monotonic',
            'entered_monotonic': entered, 'returned_monotonic': time.monotonic(),
            'forward_completion_synchronized': True,
            'forward_trace_source': 'tools/arc_qwen_probe_20261012/decoder.py'}
        return result

    def _assert_tokenizer_backend(self):
        validate_model_config(self.config)
        require((self.context_limit, self.prompt_cap, self.output_cap) ==
                (CONTEXT_LIMIT, PROMPT_CAP, OUTPUT_CAP), 'successor live bounds changed')
        require(self.prompt_contract.context_limit == CONTEXT_LIMIT and
                self.prompt_contract.output_cap == OUTPUT_CAP and
                self.prompt_contract.contract_sha256 == self.identity['prompt_contract_sha256'],
                'successor prompt contract no longer matches model identity')
        require(self.identity['profile_id'] == PROFILE_ID and
                self.identity['material_addendum_sha256'] == MATERIAL_ADDENDUM_SHA256,
                'successor live identity changed')
        return super()._assert_tokenizer_backend()

    def lock_decoder_policy(self, policy):
        receipt = self._calibration_receipt
        require(receipt is not None and policy.get('calibration_sha256') == digest(receipt),
                'decoder freeze requires this owner exact4096 calibration')
        owned = _CALIBRATIONS.get(digest(receipt))
        require(owned is not None and owned['receipt'] == receipt and
                owned['native_identity'] == _calibration_model_identity(self.identity),
                'decoder freeze requires verified owned calibration evidence')
        require(self.tiny_cpu or receipt['full_context_measured'] is True,
                'pretrained decoder requires actual4096 GPU calibration')
        require(receipt['full_state_restoration_verified'] and
                (receipt['completed_lengths'] == list(LENGTH_LADDER) or
                 self.tiny_cpu and receipt.get('fixture_calibration_lengths') == [128,512] and receipt['completed_lengths'] == [128,512]), 'incomplete successor calibration')
        require(policy.get('selected_mode') == 'full_prefix' or
                (policy.get('selected_mode') == 'cached' and receipt['behavioral_cache_admitted']),
                'cached mode requires actual4096 behavioral parity')
        return super().lock_decoder_policy(policy)

CACHE_POLICY={
 'format':'irisx/qwen14b-c4096-cache-behavior-policy-v1',
 'length_ladder':list(LENGTH_LADDER), 'states':['base','updated','restored'],
 'kinds':['grid','program'], 'steps':4, 'minimum_steps_per_kind':2, 'stress_fixture_not_arc_prompt':True, 'atol':0.01,'rtol':0.01,
 'head_rows':151936,'max_grid_allowed_tokens':128,'top_k':8,'max_failure_examples':16,
 'prefix':'exact prepared rung input_ids minus final three tokens',
 'trajectory':'prefill full reference chooses initial token; both paths then consume the same reference-selected history',
 'grid_choice':'native grid DFA allowed_tokens from generated reference suffix, including EOS',
 'program_choice':'unconstrained full-native-head greedy argmax',
 'reference_repeat':'bitwise identical full-prefix logits at every compared step',
 'admission':'finite complete head, exact cache/position/mask invariants, deterministic repeat-full and every chosen token identical including the exact-rung unconstrained argmax',
 'numeric_rule':'original torch.allclose(.01,.01) retained unchanged and separately disclosed',
 'mismatch':'behavior mismatch denies cache only; fatal invalid/late/nonfinite/reference-repeat/reset denies all science',
 'claim':'bounded empirical greedy fidelity on synthetic128/512/2048/4096 controls; no ARC-semantic or universal equivalence claim',
}


def token_cache_panel(model,ledger,token_ids,event,deadline,path):
    import torch
    from transformers import __version__ as transformers_version
    import peft
    require(len(token_ids) in CACHE_POLICY['length_ladder'],'exact rung required')
    raw=model.model;device=next(raw.parameters()).device;old_training=raw.training;raw.eval()
    start=time.monotonic();before=dict(ledger.used)
    receipt={'format':'irisx/qwen14b-cache-panel-v1','event':event,'length':len(token_ids),
        'policy':deepcopy(CACHE_POLICY),'policy_sha256':digest(CACHE_POLICY),'status':'running','fatal_error':None,
        'strict_numerical_allclose':False,'behavioral_cache_admitted':False,'forwards':[],'panels':[],'numerical_rung':{'status':'not_attempted','metrics':None},
        'environment':{'torch':str(torch.__version__),'transformers':transformers_version,'peft':peft.__version__,
            'device':str(device),'attention_implementation':getattr(raw.config,'_attn_implementation',None),
            'deterministic_algorithms':bool(torch.are_deterministic_algorithms_enabled()),
            'tf32':bool(torch.backends.cuda.matmul.allow_tf32),'training_before':bool(old_training)}}
    def persist():
        receipt['elapsed_seconds']=time.monotonic()-start
        receipt['physical_usage']={k:ledger.used[k]-before[k] for k in ledger.used}
        atomic_json(path,receipt)
    def forward(ids,history,past,suffix,use_cache):
        eid=event+'-'+suffix;cache_before=cache_length(past,raw.config,device) if past is not None else 0
        position_start=len(history)-len(ids)
        row={'event_id':eid,'input_ids':list(ids),'history_sha256':digest(history),'input_ids_sha256':digest(ids),
             'input_tokens':len(ids),'history_tokens':len(history),'attention_mask_tokens':len(history),
             'attention_mask_all_ones':True,'position_ids':list(range(position_start,len(history))),
             'cache_position':list(range(position_start,len(history))), 'cache_before':cache_before,
             'use_cache':use_cache,'past_supplied':past is not None,'work_deadline_monotonic':deadline,'deadline_monotonic':min(deadline,time.monotonic()+120),'cache_after':None,'status':'not_dispatched',
             'logit_shape':None,'nonfinite_logits':None,'finite_full_head':False,'late':False,'elapsed_seconds':0.0}
        receipt['forwards'].append(row);persist();began=time.monotonic();row['started_monotonic']=began;row['deadline_monotonic']=min(deadline,began+120)
        try:
            require(began<row['deadline_monotonic'],'cache forward deadline before dispatch')
            require(ids==history[-len(ids):] and (not use_cache or cache_before==position_start),'input/cache-position invariant failed')
            ledger.reserve(eid,{'scoring_forwards':1,'input_tokens':len(ids)})
            row['status']='dispatched';persist()
            atomic_json(ledger.path.parent/'active-call.json',{'event_id':eid,'status':'active','deadline_monotonic':row['deadline_monotonic'],'work_deadline_monotonic':deadline})
            positions=torch.tensor(row['position_ids'],device=device,dtype=torch.long)
            row['native_started_monotonic']=time.monotonic()
            out=raw(input_ids=torch.tensor([ids],device=device),attention_mask=torch.ones((1,len(history)),device=device,dtype=torch.long),
                    past_key_values=past,position_ids=positions.unsqueeze(0),cache_position=positions,
                    use_cache=use_cache,logits_to_keep=1)
            # Materialize first. Timing/deadline decisions must include queued CUDA work.
            values=out.logits.detach().float().cpu().clone()
            if device.type=='cuda':torch.cuda.synchronize(device)
            completed=time.monotonic()
            row.update(completed_monotonic=completed,elapsed_seconds=completed-began,late=completed>=row['deadline_monotonic'],
                       logit_shape=list(values.shape),nonfinite_logits=int((~torch.isfinite(values)).sum()))
            row['finite_full_head']=list(values.shape)==[1,1,151936] and row['nonfinite_logits']==0
            row['logits_sha256']=__import__('hashlib').sha256(values.numpy().tobytes()).hexdigest()
            row['cache_layers']=cache_metadata(out.past_key_values,raw.config) if use_cache and out.past_key_values is not None else []
            row['cache_after']=int(out.past_key_values.get_seq_length()) if use_cache and out.past_key_values is not None else None
            row['returned_cache']=out.past_key_values is not None
            ledger.complete(eid,{'scoring_forwards':1,'input_tokens':len(ids)})
            row['status']='complete';persist()
            if use_cache:cache_length(out.past_key_values,raw.config,device)
            require(row['finite_full_head'],'nonfinite/non-native full cache head')
            require(not row['late'],'late synchronized cache forward')
            require(not use_cache or row['cache_after']==len(history),'cache length did not grow exactly')
            require(use_cache or not row['returned_cache'],'full-prefix unexpectedly returned cache')
            return values[0,-1],out.past_key_values if use_cache else None
        except BaseException as exc:
            if eid in ledger.pending:ledger.unknown(eid,type(exc).__name__)
            row.update(status='failed',error=type(exc).__name__+': '+str(exc)[:512],elapsed_seconds=time.monotonic()-began)
            persist();raise
        finally:
            atomic_json(ledger.path.parent/'active-call.json',{'event_id':eid,'status':'closed','deadline_monotonic':row['deadline_monotonic'],'work_deadline_monotonic':deadline})
    persist()
    try:
        with torch.inference_mode():
            # Exact-rung all-logit diagnostic is always measured, independently of EOS.
            receipt['numerical_rung']={'status':'attempted_incomplete','metrics':None};persist()
            pre,past=forward(token_ids[:-1],token_ids[:-1],None,'numeric-prefill',True)
            numeric_ids=token_ids[:-1]+[choose(pre)]
            receipt['numerical_reference_token']=numeric_ids[-1]
            cached,_=forward(numeric_ids[-1:],numeric_ids,past,'numeric-cached',True)
            full,_=forward(numeric_ids,numeric_ids,None,'numeric-full',False)
            repeat,_=forward(numeric_ids,numeric_ids,None,'numeric-repeat',False)
            receipt['numerical_rung']={**comparison(cached,full),'status':'complete','completed_monotonic':time.monotonic(),'deadline_monotonic':deadline}
            receipt['numerical_reference_repeat_exact']=bool(torch.equal(full,repeat));persist()
            require(receipt['numerical_reference_repeat_exact'],'full-prefix reference repeat differs')
            require(time.monotonic()<deadline,'late numerical comparison')
            for kind in CACHE_POLICY['kinds']:
                sequence=list(token_ids[:-3]);suffix=[];past=None
                panel={'kind':kind,'prefix_sha256':digest(sequence),'prefix_tokens':len(sequence),
                       'planned_max_steps':4,'actual_steps':0,'terminated_on_eos':False,'steps':[]}
                receipt['panels'].append(panel)
                for step in range(CACHE_POLICY['steps']):
                    allowed=model.constraint.allowed_tokens(suffix) if kind=='grid' else None
                    cached,past=forward(sequence if past is None else sequence[-1:],sequence,past,kind+'-'+str(step)+'-cached',True)
                    full,_=forward(sequence,sequence,None,kind+'-'+str(step)+'-full',False)
                    repeat,_=forward(sequence,sequence,None,kind+'-'+str(step)+'-repeat',False)
                    result=comparison(cached,full,allowed)
                    row={'step':step,'history_tokens':len(sequence),'history_sha256':digest(sequence),
                         'reference_suffix_ids':list(suffix),'reference_repeat_exact':bool(torch.equal(full,repeat)),
                         'comparison':result,'comparison_completed_monotonic':time.monotonic(),'deadline_monotonic':deadline,'reference_selected_token':choose(full,allowed)}
                    panel['steps'].append(row);panel['actual_steps']=len(panel['steps']);persist()
                    require(row['reference_repeat_exact'],'full-prefix reference repeat differs')
                    require(time.monotonic()<deadline,'late behavioral comparison')
                    sequence.append(row['reference_selected_token']);suffix.append(row['reference_selected_token'])
                    if row['reference_selected_token'] in model.eos_ids:
                        panel['terminated_on_eos']=True;break
        comparisons=[receipt['numerical_rung']]+[s['comparison'] for p in receipt['panels'] for s in p['steps']]
        behavioral=[s['comparison'] for p in receipt['panels'] for s in p['steps']]
        receipt['strict_numerical_allclose']=all(c['strict_allclose'] for c in comparisons)
        receipt['coverage_sufficient']=all(p['actual_steps']>=2 for p in receipt['panels'])
        receipt['behavioral_cache_admitted']=receipt['coverage_sufficient'] and all(c['chosen_token_equal'] for c in comparisons)
        require(time.monotonic()<deadline,'late cache panel admission')
        receipt['status']='complete'
    except BaseException as exc:
        receipt['status']='fatal';receipt['fatal_error']=type(exc).__name__+': '+str(exc)[:512]
        raise
    finally:
        raw.train(old_training);persist()
    return receipt


def prepare_length_control(native, length):
    """Author-written valid identity program with comments; exact native length.

    Synthetic repeated prompt words/comment tokens are a memory stress fixture,
    not ARC data or a learnability benchmark. No truncation or token padding is
    hidden in a mask. Every target is native-template-derived text plus EOS.
    """
    require(type(length) is int and length in LENGTH_LADDER,'reviewed fixed length ladder only')
    completion_tokens = {128:16,512:64,2048:256,4096:1024}[length]
    prompt_tokens = length-completion_tokens
    tokenizer=native.tokenizer
    def program(n):
        return 'def transform(grid):\n    #'+' x'*n+'\n    return grid'
    minimum=program(0)
    n=completion_tokens-1-len(tokenizer.encode(minimum,add_special_tokens=False))
    completions=[program(i) for i in range(max(0,n-4),max(0,n)+5)]
    completion=next((v for v in completions if len(tokenizer.encode(v,add_special_tokens=False))+1==completion_tokens),None)
    require(completion is not None,'native completion cannot represent exact ladder target')
    def prompt_count(content):
        messages=[{'role':'user','content':content}]
        text=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        return len(tokenizer.encode(text,add_special_tokens=False))
    n=prompt_tokens-prompt_count('x')
    candidates=['x '*i+'x' for i in range(max(0,n-4),max(0,n)+5)]
    content=next((v for v in candidates if prompt_count(v)==prompt_tokens),None)
    require(content is not None,'native prompt cannot represent exact ladder target')
    row=native.prepare_completion([{'role':'user','content':content}],completion)
    native.validate_prepared(row)
    require(row['input_tokens']==length and row['prompt_tokens']==prompt_tokens and
            row['completion_tokens']==completion_tokens,'whole native ladder row identity differs')
    return row



def delta(before, after):
    require(all(after[k] >= v for k,v in before.items()), 'physical ledger regressed')
    return {k: after[k] - before.get(k, 0) for k in after}


def run_calibration(model,trainer,ledger,output,deadline,*,atol=0.01,rtol=0.01,fixture_lengths=None):
    import torch
    require(atol==.01 and rtol==.01,'unchanged diagnostic tolerance required')
    require(type(deadline) in (int, float) and __import__('math').isfinite(deadline) and deadline > time.monotonic(), 'finite future calibration deadline required')
    require(model.decoder_policy is None, 'calibration must precede decoder-policy lock')
    require(fixture_lengths is None or model.tiny_cpu is True and fixture_lengths == [128,512],
            'shortened calibration requires explicit tinyCPU128/512 fixture')
    lengths=list(LENGTH_LADDER) if fixture_lengths is None else list(fixture_lengths)
    deadline=min(deadline,time.monotonic()+1800)
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    initial=trainer.snapshot_training_state('before-memory-ladder');raw=trainer.trainer
    prompt=[{'role':'user','content':'Return the digit 1.'}];observations=[]
    cuda=next(model.model.parameters()).device.type=='cuda'
    try:
        for length in lengths:
            item={'length':length,'status':'running','states':{},'update':None,'full_state_reset_exact':False}
            path=root/('length-'+str(length)+'.json');atomic_json(path,item)
            before=dict(ledger.used);start=time.monotonic();event='ladder-'+str(length)
            try:
                require(time.monotonic()<deadline,'memory ladder deadline')
                trainer.restore_training_state(initial);row=prepare_length_control(model,length)
                if cuda:torch.cuda.reset_peak_memory_stats(0)
                item.update(prompt_tokens=row['prompt_tokens'],completion_tokens=row['completion_tokens'],prepared_sha256=row['prepared_sha256'])
                def observe(suffix):
                    state={'status':'running','cache_receipt_path':str(length)+'-'+suffix+'-cache.json'}
                    item['states'][suffix]=state;atomic_json(path,item)
                    cache=token_cache_panel(model,ledger,row['input_ids'],event+'-'+suffix,deadline,root/state['cache_receipt_path'])
                    state['cache']=cache;atomic_json(path,item)
                    generation=model.generate(prompt,kind='grid',seed=0,max_new_tokens=8,deadline=deadline)
                    state['generation']=generation;atomic_json(path,item)
                    score=model.score_completion(prompt,'1',deadline=deadline)
                    state['score']=score;atomic_json(path,item)
                    require(generation.get('dispatched') and generation.get('output_tokens',0)>0 and generation.get('finish_reason') in ('eos','length') and score.get('valid'),'memory ladder reference generation/scoring failed')
                    state['status']='complete';atomic_json(path,item)
                    return state
                with model.adapter_branch('base'):baseline=observe('base')
                try:
                    ledger.reserve(event,{'training_steps':1,'input_tokens':length})
                    t=time.monotonic()
                    atomic_json(ledger.path.parent/'active-call.json',{'event_id':event,'status':'active','deadline_monotonic':min(deadline,t+120),'work_deadline_monotonic':deadline})
                    try:
                        raw._make_optimizer();update=raw._step(row)
                    finally:
                        atomic_json(ledger.path.parent/'active-call.json',{'event_id':event,'status':'closed','deadline_monotonic':min(deadline,t+120),'work_deadline_monotonic':deadline})
                    if cuda:torch.cuda.synchronize(0)
                    completed=time.monotonic()
                    ledger.complete(event,{'training_steps':1,'input_tokens':length})
                    item['update']={**update,'started_monotonic':t,'completed_monotonic':completed,
                        'elapsed_seconds':completed-t,'deadline_monotonic':deadline,'late':completed>=deadline,'input_tokens':length,'event_id':event}
                    atomic_json(path,item)
                    atomic_json(ledger.path.parent/'active-call.json',{'event_id':event,'status':'closed','deadline_monotonic':min(deadline,t+120),'work_deadline_monotonic':deadline})
                    require(completed<min(deadline,t+120),'late memory update charged but rung inadmissible')
                    after=observe('updated')
                except BaseException as exc:
                    if event in ledger.pending:ledger.unknown(event,type(exc).__name__)
                    raise
                finally:
                    item['reset']=trainer.restore_training_state(initial);atomic_json(path,item)
                restored=observe('restored')
                require(baseline['generation']['output_token_ids']==restored['generation']['output_token_ids'] and baseline['score']['nll_sum']==restored['score']['nll_sum'],'exact memory-ladder reference behavior restoration failed')
                check=trainer.snapshot_training_state('ladder-reset-check')
                try:
                    item['initial_state_sha256']=initial['state_sha256'];item['restored_state_sha256']=check['state_sha256']
                    require(check['state_sha256']==initial['state_sha256'],'full ladder state differs')
                finally:trainer.release_training_state(check)
                require(time.monotonic()<deadline,'late full-state reset analysis')
                item.update(full_state_reset_exact=True,status='complete')
                if cuda:item.update(peak_allocated_bytes=int(torch.cuda.max_memory_allocated(0)),peak_reserved_bytes=int(torch.cuda.max_memory_reserved(0)))
            except BaseException as exc:
                item.update(status='fatal',error=type(exc).__name__+': '+str(exc)[:512]);raise
            finally:
                item.update(physical_usage=delta(before,ledger.used),elapsed_seconds=time.monotonic()-start)
                atomic_json(path,item)
            observations.append(item)
    finally:
        try:trainer.restore_training_state(initial)
        finally:trainer.release_training_state(initial)
    panels=[s['cache'] for r in observations for s in r['states'].values()]
    receipt={'format':'irisx/qwen14b-c4096-cache-ladder-v1','status':'complete','completed_lengths':[r['length'] for r in observations],
        'observations':observations,'full_context_measured':cuda and [r['length'] for r in observations]==list(LENGTH_LADDER),
        'strict_numerical_allclose':all(p['strict_numerical_allclose'] for p in panels),
        'behavioral_cache_admitted':all(p['behavioral_cache_admitted'] for p in panels),
        'cache_policy_sha256':digest(CACHE_POLICY),'cpu_fixture_only':not cuda,'public_admission':False,
        'material_addendum_sha256':MATERIAL_ADDENDUM_SHA256, 'full_state_restoration_verified':True,
        'fixture_calibration_lengths':fixture_lengths,
        'qualification':'explicit shortened CPU topology fixture; no4096 execution evidence' if fixture_lengths else 'actual recorded ladder lengths'}
    from tools.arc_qwen_probe_20261012.science_profiles import measurements
    receipt['measurements']=measurements(receipt)
    actual_native=getattr(model,'native',model)
    actual_native._calibration_receipt=deepcopy(receipt)
    _CALIBRATIONS[digest(receipt)] = {
        'receipt': deepcopy(receipt),
        'native_identity': _calibration_model_identity(actual_native.identity),
        'source_identity': trainer._source_identity()}
    require(len(_CALIBRATIONS) <= 8, 'bounded owned calibration registry exceeded')
    atomic_json(root/'calibration.json',receipt,exclusive=True)
    return receipt


def _calibration_model_identity(identity):
    return {k: deepcopy(v) for k, v in identity.items()
            if k not in ('decoder_policy', 'decoder_policy_sha256')}


def authorize_calibration_reload(new_model, receipt, source_model_identity):
    """Transfer this process's actual calibration to an identical fresh base.

    A JSON receipt and its self-computed hash cannot manufacture this evidence.
    Fresh checkpoint contents/state still require their independent loader proof.
    """
    key = digest(receipt)
    owned = _CALIBRATIONS.get(key)
    require(owned is not None and owned['receipt'] == receipt,
            'calibration reload requires successful same-owner in-memory evidence')
    require(_calibration_model_identity(source_model_identity) == owned['native_identity'],
            'calibration source model identity differs')
    native = getattr(new_model, 'native', new_model)
    require(native.decoder_policy is None and native._calibration_receipt is None,
            'calibration reload requires clean unlocked fresh base')
    require(_calibration_model_identity(native.identity) == owned['native_identity'],
            'fresh base/material/tokenizer/config differs from calibrated owner')
    from tools.arc_qwen_probe_20261012.protocol import file_sha
    root = Path(__file__).resolve().parents[2]
    require(all(file_sha(root / name) == sha for name, sha in owned['source_identity'].items()),
            'calibrated backend source changed before fresh reload')
    native._calibration_receipt = deepcopy(receipt)
    return {'calibration_sha256': key, 'same_owner_calibration_reused': True,
            'fresh_checkpoint_verified_by_this_function': False}
