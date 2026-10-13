"""One-thread offline genuine native A1/G2 and four fixed cases×2×3 paired predictions.

Run under an external240-second timeout. No pretrained weights, GPU, provider,
network, official task labels, or production admission are used or inferred.
"""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                  OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false')
import sys, time, json
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch
from rl_session.runtime import Session
from tools.arc_qwen_transfer_20261012.decoder import TransferModel
from tools.arc_qwen_transfer_20261012.backend import TransferTrainer
from tools.arc_qwen_transfer_20261012.model_profile import MODEL_KEY, PROFILE_ID, MATERIAL_ADDENDUM_SHA256
from experiment_flow import ExperimentPlan, FixtureShape, Forecast, SourceFreeze, run_local_experiment
from experiment_flow.contracts import canonical, write_json, require
from experiment_flow.native import AuthenticatedBaselineDataset, NativeTinyRewardPanel, NativeSessionAdapter


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    # Artificial old origin is explicit fixture input, preserving the unchanged
    # absolute clock chain while leaving a bounded240-second local test window.
    origin = started - 42000. + 230.
    gate = canonical({'maximum_absolute_gap': .20, 'minimum_unclipped_fraction': 1.,
                      'maximum_replay_seconds': 30., 'maximum_peak_bytes': 2**30,
                      'fixture_only': True, 'maximum_p95_gap': .05})
    plan = ExperimentPlan(SourceFreeze.capture(ROOT),
                          Forecast('f'*64, 'controlled-fixture', 1., 18., 1., 1., 120., 0., 5., 5.),
                          origin, gate, shape=FixtureShape(dev_cases=2, holdout_cases=2,
                                                           max_control_updates=16), output_cap=1)
    config = {'model_key': MODEL_KEY, 'profile_id': PROFILE_ID,
              'material_addendum_sha256': MATERIAL_ADDENDUM_SHA256,
              'tiny_cpu': True, 'tokenizer_path': str(ROOT / 'baseline/materials/qwen14b/hf-overlay'),
              'tiny_hidden_size': 8, 'seed': 17, 'precision': 'bf16-base-fp32-lora',
              'do_sample': False, 'temperature': 1., 'top_p': 1.}
    dataset = AuthenticatedBaselineDataset.build_tiny(output / 'authenticated-fixture-data')
    panel = NativeTinyRewardPanel(dataset)
    native = TransferModel.from_config(config)
    trainer = TransferTrainer(native, {'seed': 17, 'learning_rate': 2e-4,
                                      'gradient_checkpointing': True, 'lora_rank': 8, 'lora_alpha': 16,
                                      'schedule_steps': 0, 'warmup_steps': 0})
    session = Session(native, trainer, global_deadline=plan.deadline, fixture=True)
    adapter = NativeSessionAdapter(session)
    result = run_local_experiment(adapter, dataset, panel, plan, output / 'experiment')
    counts = {'actual_prediction_receipts': len(list((output / 'experiment').glob('*/*/[0-9][0-9][0-9]-[01].json'))),
              'actual_durable_checkpoints': len(list((output / 'experiment/checkpoints').glob('*/adapter/adapter_model.safetensors'))),
              'actual_B_updates': result.get('arms', {}).get('B', {}).get('updates', {}).get('rl_updates'),
              'actual_C_updates': result.get('arms', {}).get('C', {}).get('updates', {}).get('control_updates')}
    proof = {'status': result['status'], **counts, 'scope': 'genuine-tiny-native-mechanics-only',
             'elapsed_seconds': time.monotonic() - started, 'external_timeout_seconds': 240,
             'source_sha256': plan.sources.sha256, 'fixture_global_origin': origin,
             'fixture_forecasts_are_not_v25_measurements': True,
             'anchor': 'fabricated SFT1', 'reward': 'fabricated fixed G2 seeds7/8 target16',
             'paired_cases': 'first2dev+first2holdout authenticated synthetic fixture, fixed before outcomes',
             'evaluation_cap': 1, 'expected_predictions': 24, 'gpu_used': False,
             'pretrained_weights_loaded': False, 'PUBLIC_score': None,
             'production_admitted': False, 'error': result.get('error'),
             'time_matching': result.get('time_matching'), 'model_closure': result.get('model_closure')}
    write_json(output / 'native-proof.json', proof)
    print(json.dumps(proof, indent=2), flush=True)
    require(result['status'] == 'local-comparison-complete-PUBLIC-integration-pending', 'native full flow incomplete')
    require(counts['actual_prediction_receipts'] == 24 and counts['actual_durable_checkpoints'] == 4,
            'all genuine paired prediction and base/A/B/C checkpoint artifacts')
    require(dataset.opened_scopes == ['dev', 'holdout'], 'actual dev-before-holdout labels')

if __name__ == '__main__':
    main()
