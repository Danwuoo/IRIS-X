"""Terminal consumer orchestration. No producer code imports or model calls."""
from .consumer.safe_io import Root,need,finite,same
from .consumer.validate_owned_outputs import validate_owned_outputs
from .terminal import verify_terminal,materialize_archive,check_external_bodies
from .lineage import validate_parent_lineage


def classification(report,*,authenticated,synthetic=False):
    """Independent operational/comparison/PUBLIC axes; never shrink167 rows."""
    content=report.get('evidence_valid') is True
    admitted=bool(authenticated and content and not synthetic and report.get('release_content_binding_valid') is True)
    comparison=bool(report.get('generation_count')==288 and report.get('comparison_complete',True))
    matched=report.get('metering',{}).get('time_matching',{}).get('matched') is True
    public=report.get('public',{});metric=public.get('micro_pass_at_2',{})
    eligible=bool(admitted and public.get('status')=='SEALED_SCORER_ROWS_REPLAYED'
                  and public.get('scorer_rows_complete') is True and type(metric.get('denominator')) is int
                  and metric['denominator']==167 and type(metric.get('numerator')) is int
                  and 0<=metric['numerator']<=167 and finite(metric.get('value'))
                  and abs(metric['value']-metric['numerator']/167)<=1e-12)
    goal=bool(eligible and metric['numerator']>=151 and public.get('metric_threshold_reached') is True)
    report.update(production_admitted=admitted,authenticated_collection_verified=bool(authenticated),
        operational_complete=bool(admitted and report.get('phase_status',{}).get('owner_process_closed') is True),
        comparison_complete=comparison,compute_matched=bool(content and matched),
        comparison_eligible=bool(admitted and comparison and matched),
        public_benchmark_evidence_eligible=eligible,public_goal_met=goal,scientific_goal_met=goal,
        external_owner_envelope_verified=bool(admitted))
    if admitted:report['status']='REVIEWED_PRODUCTION_CONTENT_COMPLETE'
    return report


def _transport(collection,*,archive_path,terminal_path,output_root):
    terminal,verified=verify_terminal(archive_path,terminal_path,
        expected_archive_sha256=collection['archive_sha256'],expected_terminal_sha256=collection['terminal_sha256'],
        expected_source_sha256=collection['source_sha256'],expected_inventory_sha256=collection['artifact_inventory_sha256'],
        expected_request_sha256=collection['owner_request_sha256'],expected_outer_sha256=collection['outer_closure_sha256'])
    observed=collection['checkpoint_archive_observation'];local=terminal.get('checkpoint_archive_observation')
    need(observed is None and local is None or type(observed) is dict and type(local) is dict and same(
         {k:v for k,v in observed.items() if k!='transport_observation'},
         {k:v for k,v in local.items() if k!='transport_observation'}),
         'authenticated external header presence/length differs from local terminal declaration')
    exception=terminal.get('retained_body_exceptions',{}).get('checkpoints.zip')
    body={'bytes':exception['original_bytes'],'sha256':exception['original_sha256']} if exception else None
    materialize_archive(archive_path,output_root,verified=verified,checkpoint_archive_body=body)
    root=Root(output_root);external=check_external_bodies(root,terminal,verified)
    auth=terminal['authorization'];outer=root.json('outer-closure.json');clock=root.json('owner-clock.json')
    need(same(auth.get('original_clock'),clock) and same(auth.get('original_deadlines'),outer.get('original_deadlines'))
         and auth.get('worker_pid')==outer.get('worker_pid') and auth.get('output_root')==root.json('owner-request.json')['output_root'],
         'terminal original clock/process/output lineage differs')
    return root,terminal,verified,external


def validate_received_collection(collection,*,archive_path,terminal_path,output_root,source_root,release_root):
    """Called by pinned outside-in entry only; this module grants no authority."""
    root,terminal,verified,external=_transport(collection,archive_path=archive_path,terminal_path=terminal_path,output_root=output_root)
    need(root.json('owned-result.json').get('fixture') is False,'production consumer rejects synthetic/tiny evidence without override')
    need(collection['checkpoint_archive_observation'] is None and 'checkpoints.zip' not in terminal['external_bodies'] or
         type(collection['checkpoint_archive_observation']) is dict and collection['checkpoint_archive_observation'].get('transport_observation')=='HTTP200_CONTENT_LENGTH_VERIFIED',
         'production collection requires actual independent checkpoint header observation')
    lineage=validate_parent_lineage(root,source_sha256=collection['source_sha256'],source_archive_sha256=collection['source_archive_sha256'],synthetic=False)
    report=validate_owned_outputs(root.path,source_root=source_root,expected_source_sha256=collection['source_sha256'],
        expected_dataset_sha256=collection['dataset_sha256'],expected_artifact_inventory_sha256=collection['artifact_inventory_sha256'],
        checkpoint_mode='runtime-reload-bound',checkpoint_archive_observation=collection['checkpoint_archive_observation'],
        release_root=release_root,expected_launch_envelope_sha256=collection['launch_sha256'],
        expected_release_manifest_sha256=collection['release_sha256'])
    report.update(terminal_archive={k:v for k,v in verified.items() if k!='members'},parent_lineage=lineage,
                  external_tensor_bodies=external,policy_sha256=collection['policy_sha256'])
    return classification(report,authenticated=False)


def replay_fixture(collection,*,archive_path,terminal_path,output_root,source_root):
    """Explicitly synthetic offline mechanics only, never production admission."""
    root,terminal,verified,external=_transport(collection,archive_path=archive_path,terminal_path=terminal_path,output_root=output_root)
    need(root.json('owned-result.json').get('fixture') is True,'fixture API accepts explicitly synthetic products only')
    lineage=validate_parent_lineage(root,source_sha256=collection['source_sha256'],source_archive_sha256=collection.get('source_archive_sha256'),synthetic=True)
    report=validate_owned_outputs(root.path,source_root=source_root,expected_source_sha256=collection['source_sha256'],
        expected_dataset_sha256=collection['dataset_sha256'],expected_artifact_inventory_sha256=collection['artifact_inventory_sha256'],
        allow_synthetic=True,checkpoint_mode='runtime-reload-bound',checkpoint_archive_observation=collection['checkpoint_archive_observation'])
    report.update(terminal_archive={k:v for k,v in verified.items() if k!='members'},parent_lineage=lineage,external_tensor_bodies=external)
    return classification(report,authenticated=False,synthetic=True)


def replay_materialized_tensors(output_root,*,source_root,expected_source_sha256,expected_dataset_sha256,
                                expected_artifact_inventory_sha256,fixture=False,release_root=None,
                                expected_launch_envelope_sha256=None,expected_release_manifest_sha256=None):
    """Optional independent weights_only=True body replay; content-only forever."""
    root=Root(output_root);need(root.json('owned-result.json').get('fixture') is fixture,'explicit full-body scope differs')
    report=validate_owned_outputs(root.path,source_root=source_root,expected_source_sha256=expected_source_sha256,
        expected_dataset_sha256=expected_dataset_sha256,expected_artifact_inventory_sha256=expected_artifact_inventory_sha256,
        allow_synthetic=fixture,checkpoint_mode='full-materialized',release_root=release_root,
        expected_launch_envelope_sha256=expected_launch_envelope_sha256,
        expected_release_manifest_sha256=expected_release_manifest_sha256)
    return classification(report,authenticated=False,synthetic=fixture)
