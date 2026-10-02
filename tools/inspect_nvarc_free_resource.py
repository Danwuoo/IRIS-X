"""One read-only free accelerator quota snapshot; no kernel-state request."""
import argparse
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.errors import ValidationError
from tools.execute_nvarc_overnight_sft import client_for,token,utc


def duration_seconds(value):
    # The installed SDK appends '.0s' to a fractional timedelta total. Its
    # synthetic 7904 s + 971004 us observation reproduces this exact string.
    if re.fullmatch(r'[0-9]+\.[0-9]+\.0s',value):value=value[:-3]+'s'
    if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?s',value) is None:
        raise ValidationError('unknown provider/SDK duration encoding')
    return float(value[:-1])


def inspect(output):
    from kagglesdk.kernels.types.kernels_api_service import ApiGetAcceleratorQuotaStatisticsRequest
    if output.exists():raise ValidationError('resource snapshot identity is immutable')
    output.mkdir(parents=True)
    atomic(output/'ledger.json',{'owner_decision':'Decision 0054','quota_read_reserved':1,
        'kernel_status_requests':0,'model_calls':0,'paid_usd':0,'reserved_utc':utc()})
    with client_for(token()) as client:
        response=client.kernels.kernels_api_client.get_accelerator_quota_statistics(ApiGetAcceleratorQuotaStatisticsRequest())
        result=response.to_dict()
        typed={'gpu_used_seconds':response.gpu_quota.time_used.total_seconds(),
            'gpu_reserved_seconds':response.gpu_quota.time_reserved.total_seconds(),
            'gpu_total_seconds':response.gpu_quota.total_time_allowed.total_seconds(),
            'gpu_pay_to_scale_enabled':response.gpu_quota.is_pay_to_scale_enabled}
    atomic(output/'provider-quota.json',result)
    atomic(output/'typed-quota.json',typed)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    inspect(parser.parse_args().output)
