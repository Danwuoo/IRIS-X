from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[1];source=Path(sys.argv[1]);out=Path(sys.argv[2]);sys.path[:0]=[str(source),str(source/'src')]
from tools.arc_learning_agent_20261011.data import create_split_manifest,build_records
from tools.arc_qwen_transfer_20261012 import data
from tools.arc_next_models import digest
from tools.arc_learning_agent_20261011.budget import atomic_json

tasks={'authored-train':{'train':[{'input':[[1]],'output':[[7]]},{'input':[[2]],'output':[[7]]}]},
       'unused-split-only':{'train':[{'input':[[1,2],[3,4]],'output':[[1,2],[3,4]]},{'input':[[5,6],[7,8]],'output':[[5,6],[7,8]]}]}}
manifest=create_split_manifest(tasks,fixed_splits={'train':['authored-train'],'dev':['unused-split-only']},source_identity={'kind':'authored-checkpoint-correctness-control'})
records=[r for r in build_records(tasks,manifest,augmentations=1,seed=1917) if r['split']=='train']
taskseed=int(digest(['independent-task-rng',1917,'authored-ttt'])[:15],16)
task=data.build_task_records('authored-ttt',tasks['authored-train']['train'],augmentations=1,seed=taskseed)
for name,rows,branch,u in [('global',records,'global_grid',256),('task',task,'representative_ttt',16)]:
    p=out/'checkpoints'/branch/('update-%08d'%u)/'manifest.json';m=json.loads(p.read_text())
    assert m['binding']['records_sha256']==digest(rows)
    assert m['binding']['record_ids']==[r['record_id'] for r in rows]
    atomic_json(out/(name+'-records.json'),rows,exclusive=True)
    print(name,len(rows),digest(rows))
