"""One read-only free accelerator quota snapshot; no kernel-state request."""
import argparse
import json
import math
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


def reconcile_quota(raw, typed):
    """Compare the primary response with SDK typed durations, never to_dict().

    The installed SDK's serializer drops timedelta.days and misprints fractions.
    This function also rejects a changed pay-to-scale flag or missing bounds.
    """
    quota = raw['gpuQuota']
    numbers = {'gpu_used_seconds':duration_seconds(quota['timeUsed']),
        'gpu_reserved_seconds':duration_seconds(quota['timeReserved']),
        'gpu_total_seconds':duration_seconds(quota['totalTimeAllowed'])}
    if any(type(typed.get(k)) not in (int,float) or not math.isfinite(typed[k]) or
           typed[k] < 0 or abs(typed[k]-v)>1e-6 for k,v in numbers.items()):
        raise ValidationError('primary quota and typed SDK durations differ')
    if typed.get('gpu_pay_to_scale_enabled') is not False or quota.get('isPayToScaleEnabled',False) is not False:
        raise ValidationError('free-only quota requires disabled pay-to-scale')
    remaining = numbers['gpu_total_seconds']-max(numbers['gpu_used_seconds'],typed['gpu_used_seconds'])-max(
        numbers['gpu_reserved_seconds'],typed['gpu_reserved_seconds'])
    if remaining < 0:
        raise ValidationError('account free quota is oversubscribed')
    return {'primary_wire_and_typed_quota_agree':True,'remaining_free_seconds':remaining,
            'gpu_pay_to_scale_enabled':False,'primary_response_used':True}


def inspect(output):
    from kagglesdk.kernels.types.kernels_api_service import ApiGetAcceleratorQuotaStatisticsRequest
    if output.exists():raise ValidationError('resource snapshot identity is immutable')
    output.mkdir(parents=True)
    atomic(output/'ledger.json',{'owner_decision':'Decision 0054','quota_read_reserved':1,
        'kernel_status_requests':0,'model_calls':0,'paid_usd':0,'reserved_utc':utc()})
    with client_for(token()) as client:
        session = client.http_client()._session
        send = session.send
        captured = []
        def retain_primary(prepared, **kwargs):
            if (prepared.method != 'POST' or prepared.url !=
                    'https://api.kaggle.com/v1/kernels.KernelsApiService/GetAcceleratorQuotaStatistics' or captured):
                raise ValidationError('one exact primary quota response required')
            response = send(prepared,**kwargs)
            response.raise_for_status()
            value = response.json()
            if not isinstance(value,dict) or not {'gpuQuota','tpuQuota','quotaRefreshTime'} <= set(value):
                raise ValidationError('primary quota response shape differs')
            captured.append({k:value[k] for k in ('gpuQuota','tpuQuota','quotaRefreshTime')})
            return response
        session.send = retain_primary
        response=client.kernels.kernels_api_client.get_accelerator_quota_statistics(ApiGetAcceleratorQuotaStatisticsRequest())
        projection=response.to_dict()
        typed={'gpu_used_seconds':response.gpu_quota.time_used.total_seconds(),
            'gpu_reserved_seconds':response.gpu_quota.time_reserved.total_seconds(),
            'gpu_total_seconds':response.gpu_quota.total_time_allowed.total_seconds(),
            'gpu_pay_to_scale_enabled':response.gpu_quota.is_pay_to_scale_enabled}
    if len(captured)!=1:
        raise ValidationError('one retained primary quota response required')
    result=captured[0]
    atomic(output/'provider-quota.json',result)
    atomic(output/'sdk-quota-projection.json',projection)
    atomic(output/'typed-quota.json',typed)
    atomic(output/'reconciliation.json',reconcile_quota(result,typed))
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    inspect(parser.parse_args().output)
