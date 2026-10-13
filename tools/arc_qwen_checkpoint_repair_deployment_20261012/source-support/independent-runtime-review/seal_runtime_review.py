"""Seal narrow source audit only after independent evidence gates succeed."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;SOURCE=ROOT/'final-source-freeze-002'
BASELINE=ROOT.parent/'portfolio63-transfer-repair-20261012/final-source-freeze-002'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
canonical=lambda v:(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def get(path):return json.loads((HERE/path).read_text())
native=get('native-replay/receipt.json');final=get('native-final-fixture/receipt.json')
metadata=get('metadata-e2e-final/receipt.json');legacy=get('legacy-native-receipt.json');bridge=get('final-guard-delta-review.json')
if not all(r['status']=='passed' for r in (native,final,metadata,legacy,bridge)):raise RuntimeError('required real evidence incomplete')
if native['physical']['charged']['training_steps']!=272:raise RuntimeError('actual production-label native steps differ')
if final['physical']['charged']['training_steps']!=18:raise RuntimeError('actual final-source fixture steps differ')
for name,count in [('contracts-source002-normal.log',20),('contracts-source002-optimized.log',20),
                   ('baseline-source002-normal.log',41),('baseline-source002-optimized.log',41),
                   ('native-adversaries.log',15),('legacy-native.log',1)]:
    log=(HERE/name).read_text()
    if f'Ran {count} test' not in log or not log.rstrip().endswith('OK'):raise RuntimeError('test log not terminal passing: '+name)
files={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
inner={n:h for n,h in sorted(files.items()) if Path(n).suffix in ('.py','.json','.jinja')}
identity=hashlib.sha256(canonical(inner)).hexdigest()
if identity!='d485de95b68e0147e0d122143d25e983b7c60800259fdf8e44315b4537818b86':raise RuntimeError('final source mutated')
old={p.relative_to(BASELINE).as_posix():sha(p) for p in BASELINE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
changes=[{'path':n,'before_sha256':old.get(n),'after_sha256':files.get(n)} for n in sorted(set(old)|set(files)) if old.get(n)!=files.get(n)]
freeze=json.loads((ROOT/'evidence/AUTHOR-SOURCE-FREEZE-002.json').read_text())
if changes!=freeze['changed_files'] or inner!=freeze['source_identity']:raise RuntimeError('author receipt mismatch')
evidence_names=['original-failure-verification.json','contracts-source002-normal.log','contracts-source002-optimized.log',
 'baseline-source002-normal.log','baseline-source002-optimized.log','native-replay/receipt.json','native-replay.log',
 'native-adversaries.log','native-adversaries-receipt.json','legacy-native-receipt.json','legacy-native.log',
 'native-final-fixture/receipt.json','native-final-fixture.log','metadata-e2e-final/receipt.json','metadata-e2e-final.log',
 'final-guard-delta-review.json','capacity-independent.json','replay-harness-provenance.json']
artifacts={name:{'sha256':sha(HERE/name),'bytes':(HERE/name).stat().st_size} for name in evidence_names}
report={'format':'irisx/independent-transfer-checkpoint-runtime-review-v1','approved':True,'known_blockers':[],
 'review_date_utc':'2026-10-12','review_scope':'Narrow local checkpoint compatibility source audit; not provider publication, execution, GPU admission, or scientific efficacy approval.',
 'source_root':str(SOURCE),'source_identity_sha256':identity,'source_identity':inner,
 'runtime_source_identity':{n:h for n,h in sorted(files.items()) if n.startswith('tools/arc_qwen_transfer_20261012/') or n=='tools/arc_qwen_portfolio_20261012/checkpoints.py'},
 'changed_files':changes,'author_source_freeze':{'path':'evidence/AUTHOR-SOURCE-FREEZE-002.json','sha256':sha(ROOT/'evidence/AUTHOR-SOURCE-FREEZE-002.json')},
 'native_actual_64_256_evidence':{'source_identity_sha256':'949bc2535b19f6e7f0bc8794e80a3ffdc3f1306cadad7f00dc0023252f71738f',
   'actual_global_updates':[0,64,256],'actual_task_updates':[0,8,16],'total_charged_training_steps':272,
   'same_backend_resume_exact_state':True,'fresh_backend_resume_exact_state':True,'standalone_inference_exact_tokens_and_nll':True,
   'physical_ledger_monotone':True,'live_parameter_bindings_retained':True,'selected_global_reset_verified':True,
   'evidence_path':'native-replay/receipt.json','independently_replayed':True},
 'final_source_negative_guard_bridge':{'exactly_one_negative_only_guard':True,'evidence_path':'final-guard-delta-review.json',
   'old_native_evidence_not_relabeled':True,'actual_final_inspector_accepts_source001_0_64_256_receipts':True,
   'final_inspector_rejects_removed_transfer_schedule':True},
 'final_source_native_targeted_test':{'source_identity_sha256':identity,'schedule':'explicit fixture0/1/2 plus task0/8/16',
   'actual_global_updates':[0,1,2],'actual_task_updates':[0,8,16],'total_charged_training_steps':18,
   'same_and_fresh_resume_and_standalone_inference_exact_parity':True,'evidence_path':'native-final-fixture/receipt.json'},
 'final_source_state_machine_e2e':{'source_identity_sha256':identity,'explicit_test_backend':True,
   'global_save_updates':[0,64,256],'global_reload_order':[64,256,64,0,64],
   'train_dev_holdout_parents':[32,16,32],'main_selected':'sft64','public_selected':'base','public_synthetic_input_slots':167,
   'public_synthetic_generation_calls':334,'ttt_parents':16,'representative_ttt16_persist_reload_reset':True,
   'evidence_path':'metadata-e2e-final/receipt.json','neural_training_claim':False,'public_gold_read':False},
 'verification':{'final_source_boundary_tests_normal':20,'final_source_boundary_tests_optimized':20,
   'final_source_timing_accounting_regressions_normal':41,'final_source_timing_accounting_regressions_optimized':41,
   'source001_real_native_resealed_payload_and_binding_adversaries':15,
   'source001_plain_portfolio_native_regression':'actual0/8/16 save/resume/standalone-inference;16 actual updates',
   'tested_rejections':['unknown/omitted/wrong-scope schedule','bool/float schedule aliases','null/missing/out-of-schedule update',
    'wrong branch','wrong records/provenance/config/source','Adam step/moment/scheduled LR','scheduler epoch',
    'malformed RNG/scaler','sampler order/run counter','missing inference update','wrong receipt hash'],
   'legacy_compatibility':'Existing plain PortfolioTrainer API and same-repaired-source artifact format preserve legacy0/8/16 plus tiny<=16. Historical source-bound bytes are intentionally not silently migrated.'},
 'capacity':get('capacity-independent.json'),
 'preserved_scientific_contracts':['32/16/32 fixed parents','global64/256 and task0/8/16','180/175 generation hard/work limits',
   '43200/42300/42000 clocks','512MiB evidence cap; existing separate544MiB collection envelope remains outside this source delta',
   '2GiB checkpoint store,768MiB checkpoint,32MiB shard,8MiB metadata,2 branches,3 versions each,4GiB reserve',
   'learning rates,rank8/alpha16,BF16 base/FP32 LoRA,context4096,prompt3072,output1024','selectors,public scorers,targets,and data loaders unchanged'],
 'corrected_review_findings':['Missing/null transfer update acceptance','Task/global payload scope and tiny fixture binding',
   'PUBLIC checkpoint branch mismatch','bool/float descriptor aliases','TransferTrainer implicit legacy fallback',
   'inspect-only omission of stored transfer schedule at base0'],
 'limitations':['Native tests use a tiny8-hidden random CPU Qwen3 model with genuine151936-vocabulary head and real PEFT; no pretrained14B/GPU/full4096 execution was performed.',
   'Actual native64/256 evidence is explicitly source001; source002 is linked only by the verified three-line negative guard delta and separately tested at native fixture1/2 plus task8/16.',
   'Production-label orchestration E2E uses a declared test backend for model work, serialization, calibration, timing, and synthetic PUBLIC inputs; it is not native scientific evidence.',
   'CUDA RNG/AMP scaler/device-specific restores are structurally guarded but were not exercised on GPU.',
   'Capacity is analytical from pinned production tensor shapes and existing hard limits, not measured production checkpoint allocation.',
   'No network, provider mutation/launch, public-gold read, or real public-effectiveness result occurred in this review.',
   'Owned archive-envelope/validator acceptance and final release assembly are separately reviewed by their assigned owners; this approval covers runtime source only.'],
 'evidence_artifacts':artifacts}
(HERE/'RUNTIME-SOURCE-APPROVAL.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
summary='''# Independent checkpoint repair review\n\nApproved narrowly for the exact source identity `{identity}`. No known runtime-source blockers remain. This does not authorize provider publication/execution or establish GPU fit or ARC effectiveness.\n\n## Verified\n\n- Original v23 evidence hash verified: actual64 training updates completed, then the old checkpoint guard rejected update64.\n- Final source has explicit, type-sensitive, source-bound global0/64/256, fixture0/1/2, and task0/8/16 contracts. Save/load/inference require explicit transfer schedules; inspection rejects missing schedule for a stored transfer identity. Legacy PortfolioTrainer stays bounded.\n- Independently replayed genuine tiny-Qwen+PEFT global0/64/256 plus task0/8/16,272 physical training updates. Exact complete-state resume, fresh resume, standalone inference token/NLL parity, live parameter bindings, and monotone physical accounting passed.\n- Fifteen independent native payload/binding adversaries passed. Plain PortfolioTrainer actual0/8/16 persistence/inference regression passed.\n- Final-source targeted native fixture0/1/2 plus task0/8/16 passed18 updates and the same persistence/inference parity checks.\n- Final-source synthetic production-label E2E passed save0/64/256, reload64→256→selected64→PUBLIC base0→64, full dev/holdout seals,167 synthetic PUBLIC slots, full16-parent TTT, representative TTT16 persistence/reload/reset.\n- Final-source61 boundary/timing/accounting tests passed in both ordinary and optimized Python.\n- Shape-only capacity bound is1,627,127,872 bytes, leaving520,355,776 bytes under the unchanged2GiB checkpoint store cap.\n\n## Exact source qualification\n\nThe272-update native run used source001 (`949bc2535b19f6e7f0bc8794e80a3ffdc3f1306cadad7f00dc0023252f71738f`). Final source002 changes only a three-line negative guard in shared checkpoints.py. It rejects a stored transfer-profile artifact with its schedule omitted. For every valid transfer artifact the added condition short-circuits true. All other source bytes match source001. The old native evidence has not been relabeled; the exact delta, real final inspector checks, final native fixture checks, and final orchestration E2E bridge it explicitly.\n\n## Limits\n\nCPU random tiny-model correctness only; no pretrained14B/GPU/full4096 execution, real PUBLIC gold, or scientific efficacy evidence. Synthetic orchestration is distinct from native-state proof. Historical source-bound checkpoints remain intentionally incompatible with modified source. Owned archive-envelope and final release publication/operator checks remain separate scopes.\n\nSee RUNTIME-SOURCE-APPROVAL.json for exact source/evidence hashes and limitations.\n'''.format(identity=identity)
(HERE/'REVIEW.md').write_text(summary)
print(json.dumps({'approved':True,'source_identity_sha256':identity,'approval_sha256':sha(HERE/'RUNTIME-SOURCE-APPROVAL.json'),'approval_path':str(HERE/'RUNTIME-SOURCE-APPROVAL.json')},indent=2))
