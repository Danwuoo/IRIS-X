"""In-memory schema sizing, not generated runtime evidence or an overflow claim."""
import copy,json,zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];R=BASE/'cpu-owner-001'
canonical=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
native=json.loads((R/'experiment/dev/base/000-0.json').read_bytes())
side=json.loads((R/'experiment/dev/base/000-0.timing.json').read_bytes())
results=[]
for n in (4,930,1024):
 g=copy.deepcopy(native);s=copy.deepcopy(side);trace=[]
 for i in range(n):
  t=13600.123456789+i*.01
  trace.append({'attention_mask_tokens':3072+i,'cache_after':3072+i,'cache_before':0 if i==0 else 3071+i,
     'completed_monotonic':t+.005,'deadline_monotonic':13775.123456789,'finite_full_head':True,
     'input_tokens':3072 if i==0 else 1,'late':False,'position_end':3071+i,'position_start':0 if i==0 else 3071+i,
     'started_monotonic':t,'use_cache':True})
 g.update(forward_trace=trace,forward_calls=n,forward_input_tokens=3072+n-1,input_tokens=3072,
          output_token_ids=[151934]*n,output_tokens=n,text='9'*929,finish_reason='length',valid=False)
 s.update(forward_calls=n,forward_input_tokens=3072+n-1,input_tokens=3072,output_tokens=n,
          forward_trace=[{k:v for k,v in f.items() if k not in ('late','finite_full_head')} for f in trace])
 nb,sb=len(canonical(g)),len(canonical(s))
 results.append({'steps':n,'native_receipt_bytes':nb,'main_timing_sidecar_bytes':sb,
                 'fixed_main224_plus_public334_native_and_main224_sidecars_bytes':558*nb+224*sb})
archive=BASE.parent/'portfolio63-next-20261012/publication/run-evidence/downloads/irisx-qwen14b-transfer-20261012-run001/evidence.zip'
with zipfile.ZipFile(archive) as z:
 pre_main=sum(f.file_size for f in z.infolist())
 dataset=json.loads(z.read('dataset/solver-dataset.json'))
 chosen=set(dataset['plan']['ttt_dev_ids']+dataset['plan']['ttt_holdout_ids'])
 cases=[c for c in dataset['cases'] if c['parent_id'] in chosen]
 demos=sum(len(c['demos']) for c in cases)
 ttt_generations=3*demos+6*len(cases)
for r in results:
 r['plus_observed_v21_premain_bytes']=r['fixed_main224_plus_public334_native_and_main224_sidecars_bytes']+pre_main
 r['plus_optional_ttt_native_receipts_bytes']=r['plus_observed_v21_premain_bytes']+ttt_generations*r['native_receipt_bytes']
 r['remaining_for_new_training_prediction_checkpoint_metadata_bytes']=256*1024**2-r['plus_observed_v21_premain_bytes']
report={'format':'irisx/transfer-evidence-schema-size-estimate-v1','archive_cap_bytes':256*1024**2,
 'observed_v21_premain_inventory_bytes':pre_main,'fixed_ttt_parents':len(cases),'fixed_ttt_demo_count':demos,
 'optional_ttt_generation_calls':ttt_generations,'scenarios':results,
 'qualifications':['In-memory JSON schema projection; no large output files, model/provider/GPU work or prediction generation.',
 '1024 represents declared generation-cap stress, not observed output behavior or proof every grid can reach1024 steps.',
 '930 approximates one token per grid character plus EOS at maximum30x30 canonical grid; actual tokenizer behavior not inferred.',
 'Rows retain observed scalar metadata size and representative monotonic float encoding, not a mathematical maximum JSON-length proof.',
 'v21 pre-main inventory is observed real production overhead; main/public prediction, packing, training, metadata and archive-manifest additions remain outside these subtotals.',
 'Optional TTT generation rows omit new scoring/training/checkpoint metadata overhead; total shown is a lower subtotal for that stress scenario.']}
(BASE/'independent-runtime-review/evidence-size-estimate.json').write_bytes(canonical(report))
print(json.dumps(report,indent=2))
