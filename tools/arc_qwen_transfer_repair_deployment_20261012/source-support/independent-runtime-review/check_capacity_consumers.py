"""Independent real384MiB archive consumer replay. No model/provider/network."""
import hashlib,json,socket,subprocess,sys
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(BASE/'validation'),str(BASE/'publication'),str(BASE/'worktree'),str(BASE/'worktree/src')]
from tools.arc_qwen_transfer_20261012 import runner
import operator_common as op
import validate_transfer_outputs as v
receipt=json.loads((BASE/'author-evidence/archive-capacity-receipt.json').read_bytes())
ref=receipt['checks']['384MiB_actual_export']['result'];path=Path(ref['path'])
with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')),patch.object(subprocess,'Popen',side_effect=AssertionError('subprocess forbidden')):
    manifest=op.check_zip(path,512*1024**2,12000,runner.LARGE_DIAGNOSTICS,compressed_max_bytes=544*1024**2)
    archive=v.ClosedArchive(path)
    assert len(archive.members)==769
    assert archive.sha256==ref['sha256']
    assert all(manifest[n]['sha256']==row['sha256'] and manifest[n]['bytes']==row['bytes'] for n,row in archive.inventory['files'].items())
    expanded=sum(row['bytes'] for row in manifest.values())
    archive.close()
assert (runner.MAX_TOTAL_BYTES,runner.MAX_FILE_BYTES,runner.MAX_DIAGNOSTIC_BYTES)==(512*1024**2,16*1024**2,64*1024**2)
result={'format':'irisx/independent-transfer-capacity-consumer-review-v1','passed':True,
        'artifact':ref,'expanded_bytes_including_manifest':expanded,'members':len(manifest),
        'source_exporter_expanded_cap':runner.MAX_TOTAL_BYTES,'collector_expanded_cap':512*1024**2,
        'validator_expanded_cap':512*1024**2,'collector_and_validator_compressed_cap':544*1024**2,
        'ordinary_member_cap':runner.MAX_FILE_BYTES,'large_diagnostic_member_cap':runner.MAX_DIAGNOSTIC_BYTES,
        'ordinary_cap_count':12000,'both_actual_consumer_paths_crc_and_sha_verified':True,
        'network_provider_gpu_model_calls':0,
        'qualification':'Real expanded 384 MiB schema fixture; not actual neural predictions or a worst-case performance guarantee.'}
(BASE/'independent-runtime-review/capacity-consumers-check.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps(result,indent=2))
