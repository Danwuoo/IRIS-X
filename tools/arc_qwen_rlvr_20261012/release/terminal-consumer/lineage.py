"""Replay parent-only scorer lineage without opening evaluator or PUBLIC gold."""
from .consumer.safe_io import need,same,is_sha,digest
from .consumer.prediction_checks import reference
from .consumer.public_checks import SCORER_PINS


def validate_parent_lineage(root,*,source_sha256,source_archive_sha256=None,synthetic=False):
    request=root.json('owner-request.json');owned=root.json('owned-result.json');original=request['output_root']
    bootstrap=request.get('bootstrap',{});index=root.json('parent-lineage/index.json')
    need(same(reference(root,owned.get('parent_lineage_ref'),original),index),'owned result parent-lineage reference differs')
    need(index.get('format')=='owned-rl-parent-lineage-copies-v1'
         and index.get('all_original_bytes_retained') is True and index.get('independent_approval_claim') is False,
         'complete parent lineage copies required without self-approval')
    names={'outer_notebook','operator','original_request','source_archive','material_review','parent_scorer'}
    need(set(index.get('files',{}))==names,'complete original parent lineage member set')
    paths={};raw={}
    for name,row in index['files'].items():
        path=root.remap(row['retained']['path'],original);paths[name]=path
        h=root.file_sha(path,256*1024**2)
        need(h==row['original']['file_sha256']==row['retained']['file_sha256']
             and row.get('bytes')==root.member(path).stat().st_size and row.get('matches_original_binding') is True,
             'retained raw parent bytes differ: '+name)
        if name not in ('source_archive','material_review'):raw[name]=root.json(path)
        if name=='parent_scorer':need(bootstrap.get('parent_scorer_sha256')==h,'bootstrap parent scorer digest differs')
        else:need(same(bootstrap.get(name),row['original']),'bootstrap original parent reference differs: '+name)
    if source_archive_sha256 is not None:
        need(index['files']['source_archive']['original']['file_sha256']==source_archive_sha256,
             'externally reviewed raw source archive differs')
    operator=raw['operator'];owner=raw['original_request'];descriptor=raw['parent_scorer'];notebook=raw['outer_notebook']
    need(operator.get('format')=='owned-rl-reviewed-operator-v2' and operator.get('raw_source_sha256')==source_sha256,
         'reviewed v2 operator/source required')
    need(notebook.get('metadata',{}).get('owned_rl_release')=={
         'format':'owned-rl-outer-notebook-v1','operator_sha256':root.file_sha(paths['operator'])},
         'complete actual outer notebook pins operator bytes')
    for name in ('source_archive','material_review','original_request','parent_scorer'):
        need(operator.get(name+'_sha256')==root.file_sha(paths[name],256*1024**2),'operator raw input binding differs: '+name)
    fields={'format','scope','role','owner_id','original_request_id','original_request_sha256',
            'raw_source_sha256','evaluator_root','evaluator_manifest_sha256','scorer_pins_sha256'}
    need(set(descriptor)==fields and descriptor['format']=='owned-rl-parent-scorer-material-v1',
         'closed parent-private scorer descriptor')
    need(all(is_sha(descriptor[k]) for k in ('original_request_sha256','raw_source_sha256','evaluator_manifest_sha256','scorer_pins_sha256')),
         'actual parent descriptor hash bindings')
    need(descriptor['raw_source_sha256']==source_sha256 and descriptor['original_request_sha256']==root.file_sha(paths['original_request']),
         'parent scorer descriptor owner/source differs')
    for k in ('scope','role','owner_id'):
        need(descriptor[k]==operator.get(k)==owner.get(k)==bootstrap.get(k),'parent scorer owner scope differs: '+k)
    need(descriptor['original_request_id']==operator.get('original_request_id')==owner.get('request_id')==bootstrap.get('original_request_id'),
         'original owner request identity differs')
    need(owner.get('original_epoch')==operator.get('original_epoch')==bootstrap.get('original_epoch')==root.json('owner-clock.json')['original_epoch'],
         'parent original epoch differs')
    if not synthetic:
        need(descriptor['scope']=='production-rl-abc' and descriptor['role']=='rl-abc'
             and descriptor['scorer_pins_sha256']==digest(SCORER_PINS),'production original scorer pins/scope differ')
    environment=root.json('worker-environment.json')
    need(request.get('worker_environment_sha256')==environment.get('environment_sha256')==digest(environment.get('environment')),
         'actual child environment hash binding differs')
    import json
    for secret in (descriptor['evaluator_root'],index['files']['parent_scorer']['original']['path']):
        need(type(secret) is str and secret and secret not in json.dumps(request) and secret not in json.dumps(environment),
             'parent-only evaluator location leaked to child request/environment')
    if owned.get('PUBLIC_score') is not None:
        inp=root.json('parent-scorer-input.json');receipt=root.json('parent-scorer-receipt.json')
        need(same(reference(root,owned.get('parent_scoring_ref'),original),receipt),'owned result parent scorer receipt reference differs')
        need(inp.get('format')=='owned-rl-parent-scorer-input-v1' and same(inp.get('descriptor'),descriptor)
             and same(inp.get('checked_outer'),bootstrap) and same(inp.get('descriptor_original_ref'),index['files']['parent_scorer']['original']),
             'parent scoring input differs from actual checked owner descriptor')
        need(inp.get('owner_request_sha256')==root.file_sha('owner-request.json')
             and inp.get('owner_inner_closure_sha256')==root.file_sha('inner-closure.json')
             and same(reference(root,inp['owner_outer_closure'],original),root.json('outer-closure.json')),
             'parent scoring input not bound to actual closed owner')
        need(receipt.get('format')=='owned-rl-parent-scorer-receipt-v1' and receipt.get('fixture') is synthetic
             and receipt.get('production_admitted') is False and receipt.get('original_epoch')==owner['original_epoch']
             and receipt.get('owner_request_sha256')==root.file_sha('owner-request.json'),
             'parent scoring receipt identity/scope differs')
        need(same(reference(root,receipt['input'],original),inp)
             and same(reference(root,receipt['score'],original),reference(root,owned['PUBLIC_score'],original)),
             'persisted parent scorer input/result references differ')
    return {'raw_parent_lineage_verified':True,'parent_scorer_receipt_verified':owned.get('PUBLIC_score') is not None,
            'evaluator_opened':False,'source_archive_sha256':root.file_sha(paths['source_archive'],256*1024**2)}
