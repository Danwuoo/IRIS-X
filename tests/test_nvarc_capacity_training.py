"""CPU mechanism and failure tests, not expanded-model performance evidence."""
import copy
import importlib.util
import time
import unittest
from unittest.mock import patch

_MISSING=[name for name in ('torch','transformers','peft','pydantic','tokenizers','safetensors') if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from transformers import Qwen3Config,Qwen3ForCausalLM
    from tools.nvarc_capacity_20261017.prototype import expand_identity_depth
    from tools.nvarc_capacity_20261017.training import DepthFixtureEngine
    from tools.nvarc_posttrain_20261017.engine import FatalUpdateError
    from tools.nvarc_posttrain_20261017 import experiment as ex
    from tools.arc2_goal_sprint_20261017.model import make_optimizer,state_digest,PhaseDeadline
    from tests.test_nvarc_posttrain_engine import tokenizer_fixture,example


def base(dtype=None):
    with torch.random.fork_rng():
        torch.manual_seed(17)
        config=Qwen3Config(vocab_size=16,hidden_size=32,intermediate_size=64,num_hidden_layers=2,
            num_attention_heads=2,num_key_value_heads=1,head_dim=16,attention_dropout=0.,
            tie_word_embeddings=False,bos_token_id=13,eos_token_id=15)
        config._attn_implementation='sdpa'
        return Qwen3ForCausalLM(config).to(dtype=dtype or torch.float32).eval()


def engine(dtype=None):
    model=base(dtype);receipt=expand_identity_depth(model,after_layers=(0,))
    return DepthFixtureEngine(model,tokenizer_fixture(),receipt,fixture_only=True,seed=9)


@unittest.skipIf(bool(_MISSING),'Optional CPU depth dependencies missing: '+', '.join(_MISSING))
class DepthTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_sft_updates_only_fp32_new_blocks_and_heads(self):
        e=engine(torch.bfloat16);before=e.snapshot();frozen=copy.deepcopy(e._frozen)
        optimizer=make_optimizer(e.model,1e-3)
        report=e.sft_step(example(),optimizer,deadline=time.time()+20)
        self.assertTrue(report['updated']);self.assertEqual(e.optimizer_steps,1)
        self.assertNotEqual(state_digest(before),state_digest(e.snapshot()))
        self.assertTrue(all(p.dtype==torch.float32 for p in e.parameters))
        self.assertTrue(all(torch.equal(dict(e.model.named_parameters())[n],p) for n,p in frozen.items()))
        self.assertFalse(e.contract['production_validated'])

    def test_dtype_matched_control_initial_parity(self):
        control=base(torch.bfloat16);expanded=copy.deepcopy(control)
        control.get_input_embeddings().float();control.get_output_embeddings().float()
        receipt=expand_identity_depth(expanded,after_layers=(0,))
        e=DepthFixtureEngine(expanded,tokenizer_fixture(),receipt,fixture_only=True)
        ids=torch.tensor([example()['prompt_ids']])
        with torch.no_grad(),torch.autocast('cpu',dtype=torch.bfloat16):
            left=control(ids,use_cache=False).logits;right=e.model(ids,use_cache=False).logits
        self.assertTrue(torch.equal(left,right))

    def test_generation_and_zero_signal_af3_use_actual_full_vocab(self):
        e=engine();before=e.snapshot();prompt=example()['prompt_ids']
        rows=e.generate(prompt,count=8,max_new_tokens=4,sample=True,deadline=time.time()+20)
        for index,row in enumerate(rows):row.update(group_id='fresh',sample_id=str(index),reward=0.)
        report=e.af3_update(rows,make_optimizer(e.model,1e-3),expected_groups=['fresh'],group_size=8,deadline=time.time()+20)
        self.assertFalse(report['updated']);self.assertEqual(e.optimizer_steps,0)
        self.assertEqual(state_digest(before),state_digest(e.snapshot()))
        self.assertEqual(len(rows),8);self.assertGreater(e.sampled_tokens,0)
        self.assertTrue(all(all(0<=x<16 for x in row['input_ids']) for row in rows))

    def test_real_upstream_ddis_mixed_token_verifier_updates(self):
        # Independent toy verifier is defined BEFORE sampling: one-token color<8.
        # It is not an ARC exact-grid reward and must never be reported as one.
        e=engine();rows=e.generate(example()['prompt_ids'],count=64,max_new_tokens=1,sample=True,deadline=time.time()+20)
        for index,row in enumerate(rows):
            row.update(group_id='toy-token-verifier',sample_id=str(index),reward=float(row['input_ids'][-1]<8))
        self.assertEqual({row['reward'] for row in rows},{0.,1.})
        before=state_digest(e.snapshot())
        report=e.af3_update(rows,make_optimizer(e.model,1e-3),expected_groups=['toy-token-verifier'],group_size=64,deadline=time.time()+20)
        self.assertTrue(report['updated']);self.assertEqual(e.optimizer_steps,1)
        self.assertNotEqual(before,state_digest(e.snapshot()))
        self.assertGreater(report['replayed'],0)

    def test_existing_demo_ttt_and_state_restoration(self):
        e=engine();before=e.snapshot();audit=[]
        cfg=dict(ttt_lr=1e-3,seed=17,context_tokens=128,generation_tokens=8,ttt_steps=2)
        task={'train':[{'input':[[1]],'output':[[2]]},{'input':[[3]],'output':[[4]]}]}
        report=ex.adapt_task(e,task,cfg,task_id='synthetic-train-only',steps=2,deadline=time.time()+20,
                            audit=lambda *a,**k:audit.append((a,k)))
        self.assertEqual(report['steps'],2);self.assertTrue(report['all_requested_complete'])
        e.restore(before);self.assertEqual(state_digest(before),state_digest(e.snapshot()))

    def test_existing_exact_hybrid_then_generated_dev_ttt_lifecycle(self):
        # All tasks here are literal synthetic fixtures, never a benchmark panel.
        e=engine(torch.bfloat16);audit=[]
        task={'train':[{'input':[[1]],'output':[[2]]},
                       {'input':[[3]],'output':[[4]]},
                       {'input':[[5]],'output':[[6]]}]}
        cfg=dict(arm='H',job_id='tiny-depth-mechanism',seed=17,learning_rate=1e-3,
                 ttt_lr=1e-3,context_tokens=128,generation_tokens=8,dev_parents=1,
                 hybrid_warmup_steps=2,rl_groups=1,group_size=8,rollout_microbatch=2)
        report=ex.train_arm(e,{'synthetic-train':task},cfg,deadline=time.time()+30,
                           audit=lambda *a,**k:audit.append((a,k)))
        self.assertTrue(report['completed_requested_work'])
        self.assertEqual(report['rollouts'],8)
        self.assertEqual(report['rl_groups_complete'],1)
        self.assertEqual(report['reward'],'exact-only')
        self.assertFalse(report['equal_compute_claimed'])
        # Do not assume a sampled reward; require honest separate update counts.
        self.assertEqual(report['committed_updates'],report['sft_updates']+
                         report['rl_updates']+report['positive_replay_updates'])
        selected=e.snapshot();steps=e.optimizer_steps
        result=ex.evaluate_panel(e,{'synthetic-dev':task},cfg,deadline=time.time()+30,
                                audit=lambda *a,**k:audit.append((a,k)),ttt_steps=2,views=2)
        self.assertTrue(result['complete']);self.assertEqual(result['queries'],1)
        self.assertEqual(e.optimizer_steps-steps,2)
        self.assertEqual(state_digest(selected),state_digest(e.snapshot()))
        self.assertTrue(all(torch.equal(dict(e.model.named_parameters())[n],p)
                            for n,p in e._frozen.items()))

    def test_restore_validates_every_tensor_before_mutation(self):
        e=engine();before=e.snapshot();bad=copy.deepcopy(before)
        first,last=list(bad)[0],list(bad)[-1]
        bad[first].add_(1.);bad[last].flatten()[0]=float('nan')
        with self.assertRaises(ValueError):e.restore(bad)
        self.assertEqual(state_digest(before),state_digest(e.snapshot()))

    def test_nonfinite_external_parameter_poisoned_before_snapshot(self):
        e=engine()
        with torch.no_grad():e.parameters[0].flatten()[0]=float('nan')
        with self.assertRaises(FatalUpdateError):e.snapshot()
        self.assertEqual(e.forward_calls,0)

    def test_completed_step_is_charged_when_post_step_deadline_expires(self):
        e=engine();before=e.snapshot()
        with patch('tools.nvarc_capacity_20261017.training.check_deadline',side_effect=PhaseDeadline('post-step')):
            with self.assertRaises(PhaseDeadline):
                e.sft_step(example(),make_optimizer(e.model,1e-3),deadline=time.time()+20)
        self.assertEqual(e.optimizer_attempts,1);self.assertEqual(e.optimizer_steps,1)
        self.assertEqual(e.forward_calls,1)
        self.assertNotEqual(state_digest(before),state_digest(e.snapshot()))

    def test_all_parameter_optimizer_is_rejected(self):
        e=engine();before=e.snapshot()
        with self.assertRaisesRegex(ValueError,'exact new blocks'):
            e.sft_step(example(),torch.optim.AdamW(e.model.parameters(),lr=1e-3),deadline=time.time()+20)
        self.assertEqual(state_digest(before),state_digest(e.snapshot()))
        self.assertEqual(e.optimizer_attempts,0)

    def test_failed_optimizer_restores_and_poisons(self):
        e=engine();optimizer=make_optimizer(e.model,1e-3);before=e.snapshot()
        def broken():
            with torch.no_grad():e.parameters[0].add_(1.)
            raise RuntimeError('injected partial update')
        with patch.object(optimizer,'step',side_effect=broken):
            with self.assertRaises(FatalUpdateError):e.sft_step(example(),optimizer,deadline=time.time()+20)
        from tools.arc2_goal_sprint_20261017.model import adapter_state
        self.assertEqual(state_digest(before),state_digest(adapter_state(e.model)))
        self.assertEqual(e.optimizer_attempts,1);self.assertEqual(e.optimizer_steps,0)
        with self.assertRaises(FatalUpdateError):e.snapshot()

    def test_successful_optimizer_touching_frozen_tensor_is_rolled_back(self):
        e=engine();optimizer=make_optimizer(e.model,1e-3);original=optimizer.step
        before=e.snapshot();name=next(iter(e._frozen));frozen=e._frozen[name].clone()
        def broken(*a,**k):
            result=original(*a,**k)
            with torch.no_grad():dict(e.model.named_parameters())[name].add_(1.)
            return result
        with patch.object(optimizer,'step',side_effect=broken):
            with self.assertRaises(FatalUpdateError):e.sft_step(example(),optimizer,deadline=time.time()+20)
        from tools.arc2_goal_sprint_20261017.model import adapter_state
        self.assertEqual(state_digest(before),state_digest(adapter_state(e.model)))
        self.assertTrue(torch.equal(dict(e.model.named_parameters())[name],frozen));self.assertEqual(e.optimizer_steps,0)

    def test_wrong_receipt_pending_grad_or_production_mode_rejected(self):
        model=base();receipt=expand_identity_depth(model,after_layers=(0,));before=[p.requires_grad for p in model.parameters()]
        other=copy.deepcopy(receipt);other['local_instance_id']='wrong'
        with self.assertRaises(ValueError):DepthFixtureEngine(model,tokenizer_fixture(),other,fixture_only=True)
        self.assertEqual(before,[p.requires_grad for p in model.parameters()])
        next(model.parameters()).grad=torch.ones_like(next(model.parameters()))
        with self.assertRaises(ValueError):DepthFixtureEngine(model,tokenizer_fixture(),receipt,fixture_only=True)
        with self.assertRaises(ValueError):DepthFixtureEngine.load('unused')
        with self.assertRaises(ValueError):DepthFixtureEngine(base(),tokenizer_fixture(),{},fixture_only=False)

    def test_expired_sft_and_generation_do_not_start_work(self):
        e=engine();optimizer=make_optimizer(e.model,1e-3)
        with self.assertRaises(PhaseDeadline):e.sft_step(example(),optimizer,deadline=1.)
        with self.assertRaises(PhaseDeadline):e.generate(example()['prompt_ids'],max_new_tokens=2,deadline=1.)
        self.assertEqual(e.forward_calls,0);self.assertEqual(e.optimizer_steps,0)


    def test_nonfinite_admission_rejected_before_training_flags_change(self):
        for layer in (0,1):
            with self.subTest(layer=layer):
                model=base();receipt=expand_identity_depth(model,after_layers=(0,))
                flags=[p.requires_grad for p in model.parameters()]
                with torch.no_grad():model.model.layers[layer].mlp.gate_proj.weight.flatten()[0]=float('inf')
                with self.assertRaisesRegex(ValueError,'Finite inherited'):
                    DepthFixtureEngine(model,tokenizer_fixture(),receipt,fixture_only=True)
                self.assertEqual(flags,[p.requires_grad for p in model.parameters()])

    def test_tied_shared_storage_and_wrong_head_shape_rejected(self):
        for kind in ('tied','storage','shape'):
            with self.subTest(kind=kind):
                model=base();receipt=expand_identity_depth(model,after_layers=(0,))
                if kind=='tied':model.lm_head.weight=model.model.embed_tokens.weight
                elif kind=='storage':model.lm_head.weight=torch.nn.Parameter(model.model.embed_tokens.weight.data)
                else:model.lm_head=torch.nn.Linear(32,17,bias=False)
                with self.assertRaises(ValueError):
                    DepthFixtureEngine(model,tokenizer_fixture(),receipt,fixture_only=True)

    def test_changed_config_and_nonidentity_initialization_rejected(self):
        for kind in ('config','runtime_dropout','identity'):
            with self.subTest(kind=kind):
                model=base();receipt=expand_identity_depth(model,after_layers=(0,))
                if kind=='config':model.config.attention_dropout=.1
                elif kind=='runtime_dropout':model.model.layers[0].self_attn.attention_dropout=.1
                else:
                    with torch.no_grad():model.model.layers[1].mlp.down_proj.weight.add_(.1)
                flags=[p.requires_grad for p in model.parameters()]
                with self.assertRaises(ValueError):
                    DepthFixtureEngine(model,tokenizer_fixture(),receipt,fixture_only=True)
                self.assertEqual(flags,[p.requires_grad for p in model.parameters()])

    def test_live_config_frozen_ownership_and_storage_drift_poison(self):
        for kind in ('config','frozen','storage','inventory','buffer','tokenizer','dropout','flags'):
            with self.subTest(kind=kind):
                e=engine()
                if kind=='config':e.model.config.hidden_act='relu'
                elif kind=='frozen':e.model.model.norm.weight=torch.nn.Parameter(e.model.model.norm.weight.clone(),requires_grad=False)
                elif kind=='storage':e.model.lm_head.weight.data=e.model.model.embed_tokens.weight.data
                elif kind=='inventory':e.parameters.pop()
                elif kind=='buffer':
                    with torch.no_grad():next(e.model.buffers()).add_(1.)
                elif kind=='tokenizer':e.tokenizer.eos_token_id=13
                elif kind=='dropout':e.model.model.layers[0].self_attn.attention_dropout=.1
                else:e.model.model.norm.weight.requires_grad_(True)
                with self.assertRaises(FatalUpdateError):e.snapshot()
                self.assertTrue(e._fatal_update)
                self.assertEqual(e.forward_calls,0)

    def test_invalid_restore_preserves_pending_gradients(self):
        e=engine();before=e.snapshot();gradient=torch.ones_like(e.parameters[0]);e.parameters[0].grad=gradient
        for kind in ('inventory','dtype','shape','nonfinite','not_tensor'):
            with self.subTest(kind=kind):
                state=copy.deepcopy(before);name=next(iter(state))
                if kind=='inventory':state.pop(name)
                elif kind=='dtype':state[name]=state[name].bfloat16()
                elif kind=='shape':state[name]=state[name].flatten()
                elif kind=='nonfinite':state[name].flatten()[0]=float('nan')
                else:state[name]=None
                with self.assertRaises(ValueError):e.restore(state)
                self.assertIs(e.parameters[0].grad,gradient)
                self.assertTrue(torch.equal(gradient,torch.ones_like(gradient)))
                self.assertEqual(state_digest(before),state_digest(e.snapshot()))

    def test_partial_restore_rolls_back_and_poisons(self):
        from tools.arc2_goal_sprint_20261017.model import adapter_state
        e=engine();before=e.snapshot();target={n:v+.5 for n,v in before.items()}
        def partial(model,state):
            name=next(iter(state))
            with torch.no_grad():dict(model.named_parameters())[name].copy_(state[name])
            raise RuntimeError('injected second-copy failure')
        with patch('tools.nvarc_capacity_20261017.training.restore_state',side_effect=partial):
            with self.assertRaisesRegex(FatalUpdateError,'parameter bytes restored'):e.restore(target)
        self.assertEqual(state_digest(before),state_digest(adapter_state(e.model)))
        self.assertEqual(e.optimizer_attempts,0);self.assertEqual(e.optimizer_steps,0)
        with self.assertRaises(FatalUpdateError):e.snapshot()

    def test_restore_rollback_failure_is_explicit_and_poisoned(self):
        e=engine();state=e.snapshot()
        with patch('tools.nvarc_capacity_20261017.training.restore_state',side_effect=RuntimeError('copy')):
            with patch.object(e,'_rollback_bytes',side_effect=RuntimeError('rollback')):
                with self.assertRaisesRegex(FatalUpdateError,'rollback incomplete'):e.restore(state)
        self.assertTrue(e._fatal_update)

    def test_restore_is_detached_parameters_only_and_retains_physical_counters(self):
        e=engine();initial=e.snapshot();optimizer=make_optimizer(e.model,1e-3)
        e.sft_step(example(),optimizer,deadline=time.time()+20)
        rng=e.generator.get_state().clone();counts=(e.forward_calls,e.sampled_tokens,e.optimizer_attempts,e.optimizer_steps)
        e.parameters[0].grad=torch.ones_like(e.parameters[0]);e.restore(initial)
        self.assertTrue(all(p.grad is None for p in e.parameters))
        self.assertEqual(counts,(e.forward_calls,e.sampled_tokens,e.optimizer_attempts,e.optimizer_steps))
        self.assertTrue(torch.equal(rng,e.generator.get_state()))
        self.assertEqual(state_digest(initial),state_digest(e.snapshot()))
        initial[next(iter(initial))].add_(10.)
        self.assertNotEqual(state_digest(initial),state_digest(e.snapshot()))

    def test_nonfinite_optimizer_state_rolls_back_and_preserves_attempt(self):
        from tools.arc2_goal_sprint_20261017.model import adapter_state
        e=engine();before=e.snapshot();optimizer=make_optimizer(e.model,1e-3);original=optimizer.step
        def bad(*args,**kwargs):
            result=original(*args,**kwargs)
            next(iter(optimizer.state.values()))['exp_avg'].flatten()[0]=float('inf')
            return result
        with patch.object(optimizer,'step',side_effect=bad):
            with self.assertRaises(FatalUpdateError):e.sft_step(example(),optimizer,deadline=time.time()+20)
        self.assertEqual(state_digest(before),state_digest(adapter_state(e.model)))
        self.assertEqual(e.optimizer_attempts,1);self.assertEqual(e.optimizer_steps,0)
        self.assertTrue(e._fatal_update)

    def test_one_million_parameter_gate_runs_before_training_mutation(self):
        model=base();receipt=expand_identity_depth(model,after_layers=(0,));flags=[p.requires_grad for p in model.parameters()]
        with patch('tools.nvarc_capacity_20261017.training.count_parameters',return_value=1_000_001):
            with patch('tools.nvarc_capacity_20261017.training.train_only_new_depth') as scope:
                with self.assertRaisesRegex(ValueError,'bounded CPU tiny'):
                    DepthFixtureEngine(model,tokenizer_fixture(),receipt,fixture_only=True)
                scope.assert_not_called()
        self.assertEqual(flags,[p.requires_grad for p in model.parameters()])

    def test_expired_af3_rejects_before_upstream_work(self):
        e=engine();optimizer=make_optimizer(e.model,1e-3)
        with patch('tools.arc2_goal_sprint_20261017.model.compute_group_loss') as upstream:
            with self.assertRaises(PhaseDeadline):
                e.af3_update([],optimizer,expected_groups=[],group_size=8,deadline=1.)
            upstream.assert_not_called()
        self.assertEqual(e.forward_calls,0);self.assertEqual(e.optimizer_steps,0)
