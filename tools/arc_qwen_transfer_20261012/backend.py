"""C4096 successor factory; all historical source files remain unchanged."""
from pathlib import Path
import time
from tools.arc_learning_agent_20261011.training import Trainer
from tools.arc_learning_agent_20261011.qwen14b_backend import Qwen14BMeteredModel
from tools.arc_learning_agent_20261011.metering import MeteredTrainer, _call_window
from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_next_models import digest
from tools.arc_qwen_portfolio_20261012.backend import PortfolioTrainer
from tools.arc_qwen_probe_20261012.protocol import require, file_sha
from .model_profile import (MODEL_KEY, PROFILE_ID, CONTEXT_LIMIT, PROMPT_CAP, OUTPUT_CAP,
                            MATERIAL_ADDENDUM_SHA256, validate_model_config)
from .decoder import TransferModel
from .call_policy import generation_window, policy as generation_call_policy


class TransferTrainer(PortfolioTrainer):
    _checkpoint_schedule_required = True

    def _validate_config(self):
        # Preserve every generic optimizer/state guard, replacing precisely the
        # historical Qwen2048 upper bound with this explicit fixed successor.
        Trainer._validate_config(self)
        c = self.config
        require(c['model_key'] == MODEL_KEY and c['tiny_cpu'] is self.native.tiny_cpu,
                'distinct Qwen14B successor Trainer required')
        require(c['lora_rank'] == 8 and c['lora_alpha'] == 16, 'successor freezes rank8/alpha16')
        require(c['max_sequence_tokens'] == self.native.context_limit == CONTEXT_LIMIT and
                self.native.prompt_cap == PROMPT_CAP and self.native.output_cap == OUTPUT_CAP,
                'fixed successor sequence/prompt/output bounds required')
        require(self.native.identity.get('profile_id') == PROFILE_ID and
                self.native.identity.get('material_addendum_sha256') == MATERIAL_ADDENDUM_SHA256,
                'successor material/model identity required')
        require(type(c.get('batch_size', 1)) is int and c.get('batch_size', 1) == 1,
                'Qwen14B successor batch1 only')
        if not self.native.tiny_cpu:
            require(c['gradient_checkpointing'] is True, 'pretrained successor requires checkpointed activations')
        require(c.get('precision', 'bf16-base-fp32-lora') == 'bf16-base-fp32-lora',
                'Qwen14B FP8 not admitted')

    def _source_identity(self):
        result = super()._source_identity()
        root = Path(__file__).resolve().parents[2]
        result.update({p.relative_to(root).as_posix(): file_sha(p)
                       for p in sorted(Path(__file__).parent.glob('*.py'))})
        return result

    def _prepared(self, record):
        if 'transfer_record' in record.get('provenance', {}):
            from .data import prepare_record
            return self.native.validate_prepared(prepare_record(self.native, record))
        return super()._prepared(record)

    def adapt_task(self, task_id, demos, *, max_steps, deadline):
        # This new builder supports a single remaining outer-LOO demonstration;
        # only its exact demo-derived, validated records enter inherited train.
        from .data import build_task_records, validate_task_records
        if self._task_id is None:
            self.begin_task(task_id)
        require(self._task_id == task_id, 'another task is active')
        try:
            records = build_task_records(task_id, demos,
                augmentations=self.config['task_augmentations'], seed=self._task_seed)
            validate_task_records(records, task_id)
            require(records, 'no validated task-local demonstrations')
            self._task_records_digest = digest(records)
            result = self.train(records, max_steps=max_steps, deadline=deadline)
            result['task_id'] = task_id
            return result
        except BaseException:
            self.end_task()
            raise


class TransferMeteredModel(Qwen14BMeteredModel):
    def generate(self, messages, *, kind, seed, max_new_tokens, deadline):
        started = time.monotonic()
        require(type(max_new_tokens) is int and 0 < max_new_tokens <= self.native.output_cap,
                'Qwen14B bounded output cap required')
        window = generation_window(deadline, now=started)
        deadline, hard = window['work_deadline_monotonic'], window['deadline_monotonic']
        event = self._identity('qwen14b-generation')
        reserve = sum(self.native.prompt_cap + i for i in range(max_new_tokens))
        self.ledger.reserve(event, {'generation_calls': 1, 'input_tokens': reserve, 'output_tokens': max_new_tokens})
        active = self.ledger.path.parent / 'active-call.json'
        try:
            atomic_json(active, {**window, 'event_id': event, 'status': 'active'})
            entered = time.monotonic()
            result = self.native.generate(messages, kind=kind, seed=seed, max_new_tokens=max_new_tokens, deadline=deadline)
            returned = time.monotonic()
            dispatched = result.get('dispatched')
            require(type(dispatched) is bool, 'native dispatch receipt required')
            if returned >= deadline:
                result.update(valid=False, fatal_error=True, finish_reason='deadline',
                              error='native generation returned after soft work deadline')
            actual = {'generation_calls': int(dispatched), 'input_tokens': result['forward_input_tokens'],
                      'output_tokens': result['output_tokens'] if dispatched else 0}
            self.ledger.complete(event, actual, status='complete' if result['valid'] else 'failed' if dispatched else 'excluded')
        except BaseException as exc:
            if event in self.ledger.pending:
                self.ledger.unknown(event, type(exc).__name__)
            raise
        finally:
            atomic_json(active, {**window, 'event_id': event, 'status': 'closed'})
        completed = time.monotonic()
        if completed >= hard:
            result.update(valid=False, fatal_error=True, finish_reason='deadline',
                          error='generation wrapper completed after hard call deadline')
        return {**result, 'physical_event_id': event,
                'generation_call_policy': generation_call_policy(), 'call_window': window,
                'wrapper_timing': {'clock': 'time.monotonic', 'started_monotonic': started,
                    'native_entered_monotonic': entered, 'native_returned_monotonic': returned,
                    'completed_monotonic': completed, 'ledger_head_sha256': self.ledger._previous}}


    def score_completion(self, messages, completion, *, deadline):
        deadline, hard = _call_window(deadline)
        event = self._identity('qwen14b-c4096-likelihood')
        self.ledger.reserve(event, {'scoring_forwards': 1, 'input_tokens': CONTEXT_LIMIT})
        active = self.ledger.path.parent / 'active-call.json'
        atomic_json(active, {'event_id': event, 'status': 'active',
                            'deadline_monotonic': hard, 'work_deadline_monotonic': deadline})
        try:
            result = self.native.score_completion(messages, completion, deadline=deadline)
            dispatched = result.get('dispatched', result.get('model_forward_started'))
            require(type(dispatched) is bool, 'dispatch receipt required')
            actual = {'scoring_forwards': int(dispatched),
                      'input_tokens': result['input_tokens'] if dispatched else 0}
            self.ledger.complete(event, actual, status='complete' if result['valid'] else
                                 ('failed' if dispatched else 'excluded'))
        except BaseException as exc:
            if event in self.ledger.pending:
                self.ledger.unknown(event, type(exc).__name__)
            raise
        finally:
            atomic_json(active, {'event_id': event, 'status': 'closed',
                                'deadline_monotonic': hard, 'work_deadline_monotonic': deadline})
        return {**result, 'physical_event_id': event}


def create_backend(model_config, trainer_config, *, ledger):
    config = validate_model_config(model_config)
    native = TransferModel.from_config(config)
    try:
        model = TransferMeteredModel(native, ledger)
        trainer = TransferTrainer(model, trainer_config)
        return model, MeteredTrainer(trainer, ledger, max_sequence_tokens=CONTEXT_LIMIT)
    except BaseException:
        native.close()
        raise
