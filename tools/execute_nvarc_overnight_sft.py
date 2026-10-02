"""Decision 0053: one immutable save-and-run per new Goal identity.

The init command is offline. All other actions are deliberate provider calls.
Credentials and signed output URLs are never written to the journal or stdout.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_combined import atomic, read, sha
import re
RUN = None
from irisx.canonical import digest_value
def preflight(package):
    if read(package/'plan.json')['format']=='irisx/nvarc-original-qwen3-probe-v1':
        from tools.stage_nvarc_qwen3_probe import preflight as check
    elif read(package/'plan.json')['format'] in {'irisx/nvarc-complete-ttt-v1','irisx/nvarc-long-ttt-resource-v1'}:
        from tools.stage_nvarc_overnight_ttt import preflight as check
    elif read(package/'plan.json')['format']=='irisx/nvarc-source-trm-training-v1':
        from tools.stage_nvarc_overnight_trm import preflight as check
    else:
        from tools.stage_nvarc_overnight_sft import preflight as check
    return check(package)


def utc():
    return datetime.now(timezone.utc).isoformat()


def session_state(response):
    # The SDK omits zero-valued enums from to_dict(). KernelWorkerStatus.QUEUED
    # is zero, so an empty wire object still has the typed QUEUED status.
    return response.status.name


def request(package):
    from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
    from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
    meta = read(package / "kernel/kernel-metadata.json")
    notebook = read(package / "kernel/notebook.ipynb")
    for cell in notebook["cells"]:
        if isinstance(cell["source"], list):
            cell["source"] = "".join(cell["source"])
    req = ApiSaveKernelRequest()
    fields = dict(slug=meta["id"], new_title=meta["title"], text=json.dumps(notebook),
        language="python", kernel_type="notebook", is_private=True, enable_gpu=True,
        enable_tpu=False, enable_internet=False, machine_shape="NvidiaL4",
        session_timeout_seconds=read(package / "plan.json")["maximum_notebook_wall_seconds"], dataset_data_sources=meta["dataset_sources"],
        competition_data_sources=meta["competition_sources"], kernel_data_sources=meta['kernel_sources'], model_data_sources=[])
    for key, value in fields.items():
        setattr(req, key, value)
    req.kernel_execution_type = KernelExecutionType.SAVE_AND_RUN_ALL
    wire = req.to_dict()
    assert wire["kernelExecutionType"] == "SAVE_AND_RUN_ALL"
    assert wire["isPrivate"] is True and wire.get("enableInternet", False) is False
    assert wire["machineShape"] == "NvidiaL4" and wire["sessionTimeoutSeconds"] == read(package / "plan.json")["maximum_notebook_wall_seconds"]
    assert wire["competitionDataSources"] == ["arc-prize-2026-arc-agi-2"]
    assert wire["slug"] == "danielwuu/" + RUN and wire["newTitle"] == RUN
    return req, wire


def token():
    from kagglesdk import KaggleClient, KaggleCredentials
    with KaggleClient(verbose=False) as client:
        credentials = KaggleCredentials.load(client)
        assert credentials is not None and credentials.get_username() == "danielwuu"
        if (not credentials._access_token_expiration or
                credentials._access_token_expiration < datetime.now(timezone.utc) + timedelta(minutes=5)):
            credentials.refresh_access_token()
        value = credentials.get_access_token()
        assert value
        return value


def client_for(value):
    from kagglesdk import KaggleClient
    client = KaggleClient(verbose=False, api_token=value)
    http = client.http_client()
    http._init_session()
    session = http._session
    assert all(adapter.max_retries.total == 0 for adapter in session.adapters.values())
    original = session.send
    def bounded_send(prepared, **kwargs):
        kwargs["timeout"] = (15, 120)
        return original(prepared, **kwargs)
    session.send = bounded_send
    return client


def bindings(package):
    summary = read(package / "stage-summary.json")
    actual = {p.relative_to(package).as_posix(): sha(p) for p in package.rglob("*")
              if p.is_file() and p.name != "stage-summary.json"}
    assert actual == summary["inventory"]
    return {"inventory": actual, "summary_sha256": sha(package / "stage-summary.json"),
            "plan_digest": digest_value(read(package / "plan.json"))}


def execute(action, package, journal_dir):
    global RUN
    RUN = read(package / "plan.json")["run_id"]
    original = re.fullmatch(r'nvarc-original-qwen3-probe-\d{3}', RUN)
    assert original or re.fullmatch(r"nvarc-overnight-(?:sft|ttt|trm)-\d{3}", RUN)
    authority = 'Decision 0054' if original else 'Decision 0053'
    assert read(package/'plan.json')['owner_decision'] == authority
    # This immutable identity has one journal, including after a process restart.
    # A fresh journal argument must never create a second submission allowance.
    run_root = ROOT / ".irisx/nvarc-original/runs" / RUN
    if package.resolve() != (run_root / "package-l4").resolve() or journal_dir.resolve() != (run_root / "execution-final").resolve():
        raise ValueError("the consumed run identity requires its sole fixed package/journal")
    journal_dir.mkdir(parents=True, exist_ok=True)
    ledger, wire_path, receipt_path = (journal_dir / name for name in
        ("execution-ledger.json", "save-request.json", "save-receipt.json"))
    if action == "init":
        assert not ledger.exists() and not wire_path.exists()
        checked = preflight(package)
        assert checked["external_calls"] == 0 and checked["offline_package_verified"] is True
        atomic(journal_dir / "preflight.json", checked)
        _, wire = request(package)
        atomic(wire_path, wire)
        atomic(ledger, {"owner_decision": authority, "run_id": RUN,
            "execution_type": "SAVE_AND_RUN_ALL", "push_reserved": 0, "status_checks_reserved": 0,
            "retrieval_reserved": 0, "maximum_status_checks": 40, "bindings": bindings(package),
            "request_sha256": sha(wire_path), "prepared_utc": utc(), "events": []})
        print(json.dumps(checked))
        return
    journal = read(ledger)
    assert journal["owner_decision"] == authority and journal["run_id"] == RUN
    assert journal["bindings"] == bindings(package) and journal["request_sha256"] == sha(wire_path)
    if action == "submit":
        req, wire = request(package)
        assert wire == read(wire_path) and journal["push_reserved"] == 0 and not receipt_path.exists()
        value = token()  # Refresh before reserving the single mutation.
        with client_for(value) as client:
            http = client.http_client()
            http._init_session()
            session = http._session
            original = session.send
            sends = []
            def exact_send(prepared, **kwargs):
                assert prepared.method == "POST" and prepared.url == "https://api.kaggle.com/v1/kernels.KernelsApiService/SaveKernel"
                assert json.loads(prepared.body) == wire and not sends
                sends.append("SaveKernel/SAVE_AND_RUN_ALL")
                return original(prepared, **kwargs)
            session.send = exact_send
            event = {"action": "SaveKernel", "reserved_utc": utc(), "execution_type": "SAVE_AND_RUN_ALL"}
            journal["push_reserved"] = 1
            journal["events"].append(event)
            atomic(ledger, journal)
            try:
                response = client.kernels.kernels_api_client.save_kernel(req)
                receipt = response.to_dict()
                atomic(receipt_path, receipt)
                expected = "https://www.kaggle.com/code/danielwuu/" + RUN
                accepted = not response.error and response.version_number == 1 and response.url == expected
                invalid = any(receipt.get(k) for k in ("invalidDatasetSources", "invalidCompetitionSources", "invalidKernelSources"))
                journal.update(accepted=accepted and not invalid, provider_version=response.version_number, url=response.url)
                event.update(completed_utc=utc(), sends=len(sends), receipt_sha256=sha(receipt_path),
                    outcome="accepted" if journal["accepted"] else "rejected-or-uncertain-no-retry")
                atomic(ledger, journal)
                print(json.dumps(receipt))
                assert journal["accepted"], "rejected or uncertain; no automatic retry"
            except Exception as error:
                event.update(completed_utc=utc(), sends=len(sends), error_type=type(error).__name__)
                event.setdefault("outcome", "uncertain-no-retry")
                if getattr(error, "response", None) is not None:
                    event["http_status"] = error.response.status_code
                    try:
                        body = error.response.json()
                        message = body.get('message',body.get('error','')) if isinstance(body,dict) else ''
                        if isinstance(message,dict):message = message.get('message','')
                        message = re.sub(r'https?://\S+','[redacted URL]',str(message))[:800]
                        event['provider_error_message'] = message
                    except (ValueError,TypeError):
                        event['provider_error_message'] = 'non-JSON provider response'
                atomic(ledger, journal)
                raise SystemExit("Save failed or uncertain: " + type(error).__name__ + "; " +
                    event.get('provider_error_message','') + "; this identity is frozen")
        return
    assert journal.get("accepted") is True and journal["provider_version"] == 1
    if action == "status":
        assert journal["status_checks_reserved"] < 40 and journal["retrieval_reserved"] == 0
        if journal.get("last_status_reserved_utc"):
            assert (datetime.now(timezone.utc) - datetime.fromisoformat(journal["last_status_reserved_utc"])).total_seconds() >= 60
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelSessionStatusRequest
        req = ApiGetKernelSessionStatusRequest()
        # The numeric version_label="1" returned 404. Match the installed official
        # CLI, which omits that field. This is a single-save kernel;
        # output plan/payload hashes must independently match its saved version.
        req.user_name, req.kernel_slug = "danielwuu", RUN
        with client_for(token()) as client:
            journal["status_checks_reserved"] += 1
            journal["last_status_reserved_utc"] = utc()
            event = {"action": "status", "version": 1, "reserved_utc": utc()}
            journal["events"].append(event)
            atomic(ledger, journal)
            try:
                response = client.kernels.kernels_api_client.get_kernel_session_status(req)
                result = response.to_dict()
                status = session_state(response)
                event.update(completed_utc=utc(), result=result, typed_status=status)
                journal["last_status"] = status
                journal["terminal_observed"] = status in {"COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED"}
                atomic(ledger, journal)
                print(json.dumps({"kernel_id": "danielwuu/" + RUN, "saved_version": 1, **result, "status": status}))
            except Exception as error:
                event.update(completed_utc=utc(), error_type=type(error).__name__)
                if getattr(error, "response", None) is not None:
                    event["http_status"] = error.response.status_code
                atomic(ledger, journal)
                raise
        return
    assert action == "retrieve" and journal.get("terminal_observed") is True and journal["retrieval_reserved"] == 0
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
    import requests
    destination = journal_dir / "retrieved"
    assert not destination.exists()
    destination.mkdir()
    with client_for(token()) as client:
        event = {"action": "terminal-output", "version": 1, "reserved_utc": utc(), "output_lists": 0, "archive_downloads": 0}
        journal["retrieval_reserved"] = 1
        journal["events"].append(event)
        atomic(ledger, journal)
        page, found, names, export_urls = "", False, [], {}
        try:
            for _ in range(4):
                req = ApiListKernelSessionOutputRequest()
                req.user_name, req.kernel_slug = "danielwuu", RUN
                req.page_size, req.page_token = 100, page
                event["output_lists"] += 1
                atomic(ledger, journal)
                response = client.kernels.kernels_api_client.list_kernel_session_output(req)
                if response.log and not (destination / "provider.log").exists():
                    assert len(response.log.encode("utf-8")) < 8 * 1024**2
                    (destination / "provider.log").write_text(response.log, encoding="utf-8")
                for file in response.files or []:
                    names.append(file.file_name)
                    if file.file_name.startswith(RUN + '/export/'):
                        assert file.file_name not in export_urls and file.url.startswith('https://')
                        export_urls[file.file_name] = file.url
                    if file.file_name != "gpu-preflight-result.zip":
                        continue
                    assert not found and file.url.startswith("https://")
                    found = True
                    event["archive_downloads"] += 1
                    atomic(ledger, journal)
                    with requests.get(file.url, stream=True, timeout=(15, 120)) as download:
                        download.raise_for_status()
                        size = 0
                        with (destination / "gpu-preflight-result.zip").open("xb") as stream:
                            for chunk in download.iter_content(1024**2):
                                size += len(chunk)
                                assert size <= 64 * 1024**2
                                stream.write(chunk)
                page = response.next_page_token
                if not page:
                    break
            assert not page, "bounded output listing incomplete"
            if found:
                import hashlib
                import shutil
                import zipfile
                archive_path = destination / 'gpu-preflight-result.zip'
                with zipfile.ZipFile(archive_path) as archive:
                    manifest = json.loads(archive.read('manifest.json'))
                    assert manifest['run_id'] == RUN and manifest['plan_digest'] == journal['bindings']['plan_digest']
                    expected_names = {item['path'] for item in manifest['members']}
                    assert set(archive.namelist()) == expected_names | {'manifest.json'}
                    for item in manifest['members']:
                        content = archive.read(item['path'])
                        assert len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256']
                    assert json.loads(archive.read('plan.json')) == read(package/'plan.json')
                    assert json.loads(archive.read('payload-bindings.json')) == read(package/'stage-summary.json')['payload_sha256']
                    terminal = json.loads(archive.read('terminal.json'))
                    entries = json.loads(archive.read('export-inventory.json')) if 'export-inventory.json' in expected_names else []
                if terminal['outcome'] == 'complete' and read(package/'plan.json').get('retain_export',True):
                    assert entries and sum(item['bytes'] for item in entries) < 9 * 1024**3
                    assert shutil.disk_usage(destination).free > sum(item['bytes'] for item in entries) + 2 * 1024**3
                    event['export_downloads'] = []
                    for item in entries:
                        relative = item['path']
                        assert relative.startswith('export/') and '\\' not in relative and ':' not in relative
                        assert not any(part in {'','.','..'} for part in relative.split('/'))
                        assert item['bytes'] < 3 * 1024**3
                        name = RUN + '/' + relative
                        assert name in export_urls
                        target = destination/relative
                        target.parent.mkdir(parents=True,exist_ok=True)
                        download_event = {'path':relative,'bytes_expected':item['bytes'],'reserved_utc':utc()}
                        event['export_downloads'].append(download_event)
                        atomic(ledger,journal)
                        digest = hashlib.sha256();written = 0
                        with requests.get(export_urls[name],stream=True,timeout=(15,120)) as download:
                            download.raise_for_status()
                            with target.open('xb') as stream:
                                for chunk in download.iter_content(1024**2):
                                    written += len(chunk)
                                    assert written <= item['bytes']
                                    digest.update(chunk);stream.write(chunk)
                        assert written == item['bytes'] and digest.hexdigest() == item['sha256']
                        download_event.update(verified=True,sha256=digest.hexdigest(),completed_utc=utc())
                        atomic(ledger,journal)
                        print(json.dumps({'export_member_verified':relative,'bytes':written}),flush=True)
                    if read(package/'plan.json')['format']=='irisx/nvarc-source-trm-training-v1':
                        from irisx.arc_nvarc_trm_training import verify_trm_export
                        verified=verify_trm_export(destination/'export',terminal['export_material_digest'])
                    else:
                        from irisx.arc_nvarc_representation import verify_model_material
                        verified = verify_model_material(destination/'export',terminal['export_material_digest'])
                    assert verified['training_identity_digest'] == terminal['identity_digest']
                    event['export_verified'] = True
                    event['export_material_digest'] = terminal['export_material_digest']
            event.update(completed_utc=utc(), output_names=names, archive_found=found,
                retained_inventory={p.relative_to(destination).as_posix(): sha(p) for p in destination.rglob('*') if p.is_file()},
                outcome="retrieved" if found else "terminal-output-no-archive")
            atomic(ledger, journal)
            print(json.dumps(event))
        except Exception as error:
            event.update(completed_utc=utc(), error_type=type(error).__name__, outcome="retrieval-failed-no-repeat")
            atomic(ledger, journal)
            raise SystemExit("Retrieval failed: " + type(error).__name__ + "; no repeat")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "submit", "status", "retrieve"))
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    execute(args.action, args.package, args.journal)
