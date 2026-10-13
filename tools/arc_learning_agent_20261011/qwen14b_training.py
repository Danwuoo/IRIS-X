"""Real PEFT Qwen3 LoRA using unchanged complete-state Trainer/checkpoints."""
from __future__ import annotations
import dataclasses
import hashlib
from pathlib import Path
from .training import Trainer
from .budget import digest
from .qwen14b_profiles import MODEL_KEY, VOCAB_SIZE, require


def qwen_lora_targets(model, torch):
    require(model.config.model_type == 'qwen3', 'native Qwen3 projection discovery required')
    expected = {f'model.layers.{i}.{group}.{name}' for i in range(model.config.num_hidden_layers)
                for group, names in (('self_attn', ('q_proj', 'k_proj', 'v_proj', 'o_proj')),
                                     ('mlp', ('gate_proj', 'up_proj', 'down_proj'))) for name in names}
    observed = {name for name, module in model.named_modules()
                if name.rsplit('.', 1)[-1] in {'q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'}
                and isinstance(module.get_base_layer() if callable(getattr(module, 'get_base_layer', None)) else module, torch.nn.Linear)}
    require(observed == expected, 'Qwen3 seven-projection full-layer discovery differs')
    cfg = model.config
    h, hd = cfg.hidden_size, cfg.head_dim
    shapes = {'q_proj': (cfg.num_attention_heads * hd, h), 'k_proj': (cfg.num_key_value_heads * hd, h),
              'v_proj': (cfg.num_key_value_heads * hd, h), 'o_proj': (h, cfg.num_attention_heads * hd),
              'gate_proj': (cfg.intermediate_size, h), 'up_proj': (cfg.intermediate_size, h),
              'down_proj': (h, cfg.intermediate_size)}
    for name in expected:
        module = model.get_submodule(name)
        require(tuple(module.weight.shape) == shapes[name.rsplit('.', 1)[-1]] and module.bias is None,
                'Qwen3 native projection shape/bias differs: ' + name)
    return sorted(expected)


def _canonicalize_qwen_peft_targets(model, targets):
    """Undo PEFT's long-list minimization only after exact live-name matching.

    PEFT 0.21 minimizes >=20 full paths into suffix selectors during injection.
    Canonicalize once at construction, before identity capture; all later recipe
    guards still require the exact full-path set and reject config drift.
    """
    from peft import LoraConfig, PeftModelForCausalLM
    require(type(model) is PeftModelForCausalLM and set(model.peft_config) == {'default'},
            'exact single default native PEFT adapter required')
    actual = model.peft_config['default']
    require(type(actual) is LoraConfig, 'exact native LoraConfig required')
    selectors = actual.target_modules
    require(type(selectors) is set and selectors and
            all(type(selector) is str and selector for selector in selectors),
            'Qwen14B PEFT target selectors must be a nonempty string set; regex forbidden')
    names = {name for name, _ in model.get_base_model().named_modules()}
    matches = {selector: {name for name in names if name == selector or name.endswith('.' + selector)}
               for selector in selectors}
    require(all(matches.values()) and set().union(*matches.values()) == set(targets),
            'Qwen14B PEFT target selector inventory differs')
    actual.target_modules = set(targets)


def validate_qwen_peft_recipe(model, torch, *, expected_disabled=False):
    """Validate the realized adapter, not just LoraConfig's scalar defaults.

    PEFT rank/alpha patterns and scale_layer() can change behavior without
    changing checkpoint parameter names. Both constructor and operation-boundary
    checks bind the exact native PEFT recipe; scoped base disabling is the sole
    admitted runtime execution variation.
    """
    from peft import LoraConfig, PeftModelForCausalLM, TaskType
    from peft.tuners.lora.layer import Linear as LoraLinear
    require(type(model) is PeftModelForCausalLM and set(model.peft_config)=={'default'},
            'exact single default native PEFT adapter required')
    base=model.get_base_model();targets=qwen_lora_targets(base,torch)
    actual=model.peft_config['default']
    require(type(actual) is LoraConfig,'exact native LoraConfig required')
    expected=LoraConfig(task_type=TaskType.CAUSAL_LM,r=8,lora_alpha=16,lora_dropout=0.0,
                        target_modules=targets,bias='none')
    expected.base_model_name_or_path=base.__dict__.get('name_or_path',None) or None
    for field in dataclasses.fields(expected):
        require(getattr(actual,field.name)==getattr(expected,field.name),
                'Qwen14B PEFT recipe field differs: '+field.name)
    require(getattr(actual,'_custom_modules',None) is None,'custom PEFT module mapping forbidden')
    observed={name for name,module in base.named_modules() if hasattr(module,'lora_A')}
    require(observed==set(targets),'realized PEFT layer inventory differs')
    inventory={}
    for name in targets:
        module=base.get_submodule(name)
        require(type(module) is LoraLinear and type(module.get_base_layer()) is torch.nn.Linear,
                'exact native PEFT Linear required: '+name)
        require(module.active_adapters==['default'] and module.disable_adapters is expected_disabled and
                not module.merged_adapters and module.fan_in_fan_out is False and
                module.ephemeral_gpu_offload is False and module.cast_input_dtype_enabled is True,
                'PEFT active/merged/runtime recipe differs: '+name)
        for field in ('r','lora_alpha','scaling','lora_A','lora_B','lora_dropout','lora_bias','use_dora','use_rslora'):
            require(set(getattr(module,field))=={'default'},'PEFT per-target adapter keys differ: '+name+'/'+field)
        require(module.r['default']==8 and module.lora_alpha['default']==16 and
                type(module.scaling['default']) in (int,float) and module.scaling['default']==2.0,
                'PEFT realized rank/alpha/scaling differs: '+name)
        require(module.lora_bias['default'] is False and module.use_dora['default'] is False and
                module.use_rslora['default'] is False and type(module.lora_dropout['default']) is torch.nn.Identity and
                not module.lora_variant and not module.lora_embedding_A and not module.lora_embedding_B and
                not module.lora_magnitude_vector,'PEFT variant/dropout recipe differs: '+name)
        a,b=module.lora_A['default'],module.lora_B['default'];out_features,in_features=module.get_base_layer().weight.shape
        require(type(a) is torch.nn.Linear and type(b) is torch.nn.Linear and a.bias is None and b.bias is None and
                tuple(a.weight.shape)==(8,in_features) and tuple(b.weight.shape)==(out_features,8) and
                a.weight.dtype==b.weight.dtype==torch.float32,
                'PEFT realized A/B shape/bias/precision differs: '+name)
        require(a.weight.requires_grad is not expected_disabled and b.weight.requires_grad is not expected_disabled,
                'PEFT realized A/B trainability differs: '+name)
        require(module.get_base_layer().weight.dtype==torch.bfloat16 and not module.get_base_layer().weight.requires_grad,
                'PEFT frozen BF16 base differs: '+name)
        inventory[name]={'rank':8,'alpha':16,'scaling':2.0,'a_shape':list(a.weight.shape),'b_shape':list(b.weight.shape),
                         'adapter_dtype':'torch.float32','base_dtype':'torch.bfloat16','dropout':0.0,'bias':False}
    def normalized(value):
        if isinstance(value,dict):return {k:normalized(v) for k,v in value.items()}
        if isinstance(value,set):return sorted(normalized(v) for v in value)
        if isinstance(value,(tuple,list)):return [normalized(v) for v in value]
        return value
    return {'format':'irisx/qwen14b-exact-realized-peft-recipe-v1','adapter_name':'default',
            'config_sha256':digest(normalized(dataclasses.asdict(actual))),'targets':inventory,
            'scoped_base_disable_allowed':True}


class Qwen14BTrainer(Trainer):
    def __init__(self, native_model, config=None):
        import torch
        require(native_model.identity.get('model_key') == MODEL_KEY and
                (native_model.tiny_cpu is True or native_model.identity.get('probe_pretrained_admitted') is True),
                'CPU-only Qwen14B backend identity required')
        require(native_model.vocab_size == VOCAB_SIZE, 'all 151936 head rows required')
        config = {'model_key': MODEL_KEY, 'tiny_cpu': native_model.tiny_cpu, 'lora_rank': 8, 'lora_alpha': 16,
                  'max_sequence_tokens': native_model.context_limit, 'gradient_checkpointing': not native_model.tiny_cpu,
                  'task_augmentations': 1, **dict(config or {})}
        require(config['model_key'] == MODEL_KEY and config['tiny_cpu'] is native_model.tiny_cpu and
                config['lora_rank'] == 8 and config['lora_alpha'] == 16, 'Qwen14B probe freezes rank8/alpha16 and explicit mode')
        if not getattr(native_model.model, 'peft_config', None):
            self.target_names = qwen_lora_targets(native_model.model, torch)
            from peft import get_peft_model, LoraConfig, TaskType
            devices = [] if native_model.tiny_cpu else [0]
            with torch.random.fork_rng(devices=devices):
                torch.manual_seed(config.get('seed', 0))
                native_model.model = get_peft_model(native_model.model, LoraConfig(
                    task_type=TaskType.CAUSAL_LM, r=8, lora_alpha=16, lora_dropout=0.0,
                    target_modules=self.target_names, bias='none'))
        else:
            self.target_names = qwen_lora_targets(native_model.model.get_base_model(), torch)
        _canonicalize_qwen_peft_targets(native_model.model, self.target_names)
        self._adapter_recipe_identity=validate_qwen_peft_recipe(native_model.model,torch)
        super().__init__(native_model, config)
        require(set(next(iter(self.model.peft_config.values())).target_modules) == set(self.target_names),
                'real PEFT target discovery mismatch')
        require(all(p.dtype == torch.float32 for p in self.parameters.values()), 'real PEFT LoRA must be FP32')
        require(all(p.dtype == torch.bfloat16 for p in self.model.parameters() if not p.requires_grad),
                'frozen native base must remain genuine BF16')
        # MeteredModel forwards reads but only selected assignments; attach the
        # guard to the actual native object so generation/scoring also check it.
        actual_native=getattr(native_model,'native',native_model)
        actual_native._adapter_recipe_guard=self._assert_adapter_recipe

    def _assert_adapter_recipe(self):
        observed=validate_qwen_peft_recipe(self.model,self.torch,
                    expected_disabled=self.native._adapter_execution_mode=='base')
        require(observed==self._adapter_recipe_identity,'Qwen14B realized adapter identity changed')
        live={name:id(value) for name,value in self.model.named_parameters() if 'lora_' in name}
        require(live=={name:id(value) for name,value in self.parameters.items()},
                'Qwen14B live LoRA parameters differ from Trainer/optimizer bindings')
        return observed

    def _model_identity(self):
        identity=super()._model_identity()
        identity['qwen14b_exact_peft_recipe']=self._assert_adapter_recipe()
        return identity

    def fingerprint(self):
        self._assert_adapter_recipe()
        return super().fingerprint()

    def _identity(self, records):
        self._assert_adapter_recipe()
        return super()._identity(records)

    def snapshot(self, label):
        self._assert_adapter_recipe()
        return super().snapshot(label)

    def snapshot_training_state(self, label):
        self._assert_adapter_recipe()
        return super().snapshot_training_state(label)

    def restore(self, snapshot):
        self._assert_adapter_recipe()
        return super().restore(snapshot)

    def restore_training_state(self, snapshot):
        self._assert_adapter_recipe()
        return super().restore_training_state(snapshot)

    def save_checkpoint(self, checkpoint_dir):
        self._assert_adapter_recipe()
        return super().save_checkpoint(checkpoint_dir)

    def export_adapter(self, output_dir):
        self._assert_adapter_recipe()
        return super().export_adapter(output_dir)

    def load_checkpoint(self, checkpoint, *, identity, records_count):
        self._assert_adapter_recipe()
        require(identity.get('model')==self._base_identity and identity.get('source')==self._source_identity(),
                'Qwen14B checkpoint live model/source/realized recipe identity differs')
        return super().load_checkpoint(checkpoint,identity=identity,records_count=records_count)

    def _validate_config(self):
        super()._validate_config()
        c = self.config
        require(c['model_key'] == MODEL_KEY and c['tiny_cpu'] is self.native.tiny_cpu, 'distinct Qwen14B CPU Trainer required')
        require(c['lora_rank'] == 8 and c['lora_alpha'] == 16, 'Qwen14B probe freezes rank8/alpha16')
        require(c['max_sequence_tokens'] <= self.native.context_limit <= 2048, 'Qwen14B probe context capped at 2048')
        require(type(c.get('batch_size', 1)) is int and c.get('batch_size', 1) == 1, 'Qwen14B probe batch1 only')
        if not self.native.tiny_cpu:
            require(c['gradient_checkpointing'] is True, 'pretrained capability probe requires checkpointed activations')
        require(c.get('precision', 'bf16-base-fp32-lora') == 'bf16-base-fp32-lora', 'Qwen14B FP8 not admitted')

    def _source_identity(self):
        result = super()._source_identity()
        root = Path(__file__).parents[2]
        for name in ('qwen14b_model.py', 'qwen14b_training.py', 'qwen14b_contract.py',
                     'qwen14b_profiles.py', 'qwen14b_backend.py', 'qwen14b_admission.py', 'qwen14b_probe.py'):
            path = Path(__file__).with_name(name)
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def _prepared(self, record):
        row = self.native.prepare_completion(record['messages'], record['completion'])
        return self.native.validate_prepared(row)

    def _step(self, row):
        self.native.validate_prepared(row)
        return super()._step(row)

    def _accumulate(self, row):
        self.native.validate_prepared(row)
        return super()._accumulate(row)
