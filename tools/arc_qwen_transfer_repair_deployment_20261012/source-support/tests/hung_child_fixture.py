"""Explicit CPU watchdog fixture: reserve work then simulate a blocked native call."""
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]/'worktree'
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.arc_qwen_transfer_20261012.call_policy import generation_window
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json
request=json.loads(Path(sys.argv[-2]).read_bytes())
root=Path(request['output_root']);ledger=WorkLedger(root/'physical-work.jsonl')
ledger.reserve('qwen14b-generation-1',{'generation_calls':1,'input_tokens':3670016,'output_tokens':1024})
window=generation_window(min(request['work_deadline'],time.monotonic()+.35))
atomic_json(root/'active-call.json',{**window,'event_id':'qwen14b-generation-1','status':'active'})
time.sleep(60)
