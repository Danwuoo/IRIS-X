"""Mutable parser/dispatch facade; legacy implementations retain frozen paths."""
from __future__ import annotations
import argparse
from pathlib import Path
from ...artifacts import write_artifact
from ...canonical import digest_value, write_json
from ...errors import ValidationError


def register_parser(subcommands, path_type):
    arc = subcommands.add_parser("arc-agi-2", help="prepare and verify the admitted ARC-AGI-2 Trial 001 path")
    arc_sub = arc.add_subparsers(dest="arc_command", required=True)

    arc_source = arc_sub.add_parser("source", help="official ARC source operations")
    arc_source_sub = arc_source.add_subparsers(dest="arc_source_command", required=True)
    arc_source_materialize = arc_source_sub.add_parser("materialize", help="deliberately acquire the one pinned official ARC source")
    arc_source_materialize.add_argument("--output", required=True, type=path_type)
    arc_source_validate = arc_source_sub.add_parser("validate", help="validate a local pinned ARC source offline")
    arc_source_validate.add_argument("path", type=path_type)

    arc_model = arc_sub.add_parser("model", help="selected frozen Qwen raw-source operations")
    arc_model_sub = arc_model.add_subparsers(dest="arc_model_command", required=True)
    arc_model_materialize = arc_model_sub.add_parser("materialize", help="deliberately acquire the one selected model revision")
    arc_model_materialize.add_argument("--output", required=True, type=path_type)
    arc_model_validate = arc_model_sub.add_parser("validate", help="validate a local selected model source offline")
    arc_model_validate.add_argument("path", type=path_type)

    arc_trial = arc_sub.add_parser("trial", help="ARC trial construction, outbound transport, and preflight")
    arc_trial_sub = arc_trial.add_subparsers(dest="arc_trial_command", required=True)
    arc_trial_prepare = arc_trial_sub.add_parser("prepare", help="build isolated views and P1 contracts offline")
    arc_trial_prepare.add_argument("--source", required=True, type=path_type)
    arc_trial_prepare.add_argument("--output", required=True, type=path_type)
    arc_trial_validate = arc_trial_sub.add_parser("validate", help="validate the complete local Trial 001 bundle offline")
    arc_trial_validate.add_argument("path", type=path_type)
    arc_outbound_build = arc_trial_sub.add_parser("outbound-build", help="build one closed-world trial-input.zip")
    arc_outbound_build.add_argument("--trial", required=True, type=path_type)
    arc_outbound_build.add_argument("--model-source", required=True, type=path_type)
    arc_outbound_build.add_argument("--binding", required=True, type=path_type)
    arc_outbound_build.add_argument("--runtime-wheels", required=True, type=path_type)
    arc_outbound_build.add_argument("--output", required=True, type=path_type)
    arc_outbound_verify = arc_trial_sub.add_parser("outbound-verify", help="verify trial-input.zip offline")
    arc_outbound_verify.add_argument("path", type=path_type)
    arc_preflight = arc_trial_sub.add_parser("preflight", help="write technical Kaggle readiness evidence without authorizing a run")
    arc_preflight.add_argument("--trial", required=True, type=path_type)
    arc_preflight.add_argument("--model-source", required=True, type=path_type)
    arc_preflight.add_argument("--trial-package", required=True, type=path_type)
    arc_preflight.add_argument("--binding", required=True, type=path_type)
    arc_preflight.add_argument("--output", required=True, type=path_type)

    arc_result = arc_sub.add_parser("result", help="verify, quarantine-import, and locally score returned predictions")
    arc_result_sub = arc_result.add_subparsers(dest="arc_result_command", required=True)
    arc_result_verify = arc_result_sub.add_parser("verify", help="verify a result-package.zip without trusting quarantine")
    arc_result_verify.add_argument("--package", required=True, type=path_type)
    arc_result_verify.add_argument("--trial-package", required=True, type=path_type)
    arc_result_verify.add_argument("--trial", required=True, type=path_type)
    arc_benchmark_verify = arc_result_sub.add_parser(
        "benchmark-verify",
        help="verify an untrusted run-003 four-invocation result.zip offline",
    )
    arc_benchmark_verify.add_argument("--package", required=True, type=path_type)
    arc_benchmark_verify.add_argument("--trial-package", required=True, type=path_type)
    arc_result_import = arc_result_sub.add_parser("import", help="promote a fully valid quarantine result into normalized run evidence")
    arc_result_import.add_argument("--package", required=True, type=path_type)
    arc_result_import.add_argument("--trial-package", required=True, type=path_type)
    arc_result_import.add_argument("--trial", required=True, type=path_type)
    arc_result_import.add_argument("--run-root", required=True, type=path_type)
    arc_result_evaluate = arc_result_sub.add_parser("evaluate", help="score, select, and apply P2 acceptance locally")
    arc_result_evaluate.add_argument("--trial", required=True, type=path_type)
    arc_result_evaluate.add_argument("--run", required=True, type=path_type)

    arc_package = arc_sub.add_parser("package", help="eligible ARC Domain Package operations")
    arc_package_sub = arc_package.add_subparsers(dest="arc_package_command", required=True)
    arc_package_build = arc_package_sub.add_parser("build", help="build a self-contained eligible ARC Domain Package")
    arc_package_build.add_argument("--trial", required=True, type=path_type)
    arc_package_build.add_argument("--source", required=True, type=path_type)
    arc_package_build.add_argument("--run", required=True, type=path_type)
    arc_package_build.add_argument("--model-source", required=True, type=path_type)
    arc_package_build.add_argument("--trial-package", required=True, type=path_type)
    arc_package_build.add_argument("--result-package", required=True, type=path_type)
    arc_package_build.add_argument("--output", required=True, type=path_type)
    arc_package_verify = arc_package_sub.add_parser("verify", help="independently verify an ARC Domain Package")
    arc_package_verify.add_argument("path", type=path_type)

    baseline = arc_sub.add_parser("baseline", help="ARC-AGI-2 Trial 002 completable baseline operations")
    baseline_sub = baseline.add_subparsers(dest="baseline_command", required=True)
    baseline_prepare = baseline_sub.add_parser("prepare", help="prepare the fixed four-task answer-blind smoke workload")
    baseline_prepare.add_argument("--source", required=True, type=path_type)
    baseline_prepare.add_argument("--competition-challenges", required=True, type=path_type)
    baseline_prepare.add_argument("--output", required=True, type=path_type)
    baseline_validate = baseline_sub.add_parser("validate", help="validate the local Trial 002 workload and truth isolation")
    baseline_validate.add_argument("path", type=path_type)
    baseline_outbound = baseline_sub.add_parser("outbound-build", help="build the truth-free Trial 002 input package")
    baseline_outbound.add_argument("--trial", required=True, type=path_type)
    baseline_outbound.add_argument("--model", required=True, type=path_type)
    baseline_outbound.add_argument("--nvarc", required=True, type=path_type)
    baseline_outbound.add_argument("--wheels", required=True, type=path_type)
    baseline_outbound.add_argument("--output", required=True, type=path_type)
    baseline_outbound_verify = baseline_sub.add_parser("outbound-verify", help="verify the truth-free Trial 002 input package")
    baseline_outbound_verify.add_argument("path", type=path_type)
    baseline_kernel_stage = baseline_sub.add_parser("kernel-stage", help="bind outbound digest and exact Dataset source into Kaggle kernel staging")
    baseline_kernel_stage.add_argument("--template", required=True, type=path_type)
    baseline_kernel_stage.add_argument("--output", required=True, type=path_type)
    baseline_kernel_stage.add_argument("--dataset-ref", required=True)
    baseline_kernel_stage.add_argument("--outbound-digest", required=True)
    baseline_preflight = baseline_sub.add_parser("preflight", help="verify all bound local bytes before the authorized smoke")
    baseline_preflight.add_argument("--trial", required=True, type=path_type)
    baseline_preflight.add_argument("--outbound", required=True, type=path_type)
    baseline_preflight.add_argument("--model", required=True, type=path_type)
    baseline_preflight.add_argument("--nvarc", required=True, type=path_type)
    baseline_preflight.add_argument("--wheels", required=True, type=path_type)
    baseline_preflight.add_argument("--competition-challenges", required=True, type=path_type)
    baseline_preflight.add_argument("--dataset", required=True, type=path_type)
    baseline_preflight.add_argument("--kernel", required=True, type=path_type)
    baseline_preflight.add_argument("--dataset-ref", required=True)
    baseline_preflight.add_argument("--output", required=True, type=path_type)
    baseline_result_verify = baseline_sub.add_parser("result-verify", help="verify an untrusted Trial 002 result package")
    baseline_result_verify.add_argument("--package", required=True, type=path_type)
    baseline_result_verify.add_argument("--outbound", required=True, type=path_type)
    baseline_result_import = baseline_sub.add_parser("result-import", help="verify and import a Trial 002 result into quarantine")
    baseline_result_import.add_argument("--package", required=True, type=path_type)
    baseline_result_import.add_argument("--outbound", required=True, type=path_type)
    baseline_result_import.add_argument("--quarantine", required=True, type=path_type)
    baseline_result_score = baseline_sub.add_parser("result-score", help="score a verified Trial 002 quarantine result locally")
    baseline_result_score.add_argument("--trial", required=True, type=path_type)
    baseline_result_score.add_argument("--quarantined", required=True, type=path_type)
    baseline_result_score.add_argument("--output", required=True, type=path_type)


def execute(args: argparse.Namespace, repository_root: Path) -> str:
    from ...arc_agi2 import materialize_source, prepare_trial as prepare_arc_trial, validate_source, validate_trial_bundle
    from ...arc_package import build_arc_package, verify_arc_package
    from ...arc_trial_002 import (
        build_outbound_package as build_trial_002_outbound,
        import_quarantine as import_trial_002_quarantine,
        prepare_trial as prepare_trial_002,
        score_quarantined as score_trial_002_quarantined,
        stage_kaggle_kernel as stage_trial_002_kernel,
        technical_preflight as trial_002_preflight,
        validate_trial as validate_trial_002,
        verify_outbound_package as verify_trial_002_outbound,
        verify_result_package as verify_trial_002_result,
    )
    from ...kaggle import (
        build_outbound_package,
        evaluate_imported_run,
        import_quarantine,
        materialize_model,
        preflight as kaggle_preflight,
        validate_model_source,
        verify_benchmark_result_package,
        verify_outbound_package,
        verify_result_package,
    )
    if args.command == "arc-agi-2" and args.arc_command == "source":
        if args.arc_source_command == "materialize":
            provenance = materialize_source(args.output)
            return f"materialized pinned official ARC source: {provenance['content_digest']}"
        if args.arc_source_command == "validate":
            provenance = validate_source(args.path)
            return f"verified pinned official ARC source offline: {provenance['content_digest']}"
    if args.command == "arc-agi-2" and args.arc_command == "model":
        if args.arc_model_command == "materialize":
            provenance = materialize_model(args.output)
            return f"materialized selected frozen model source: {provenance['content_digest']}"
        if args.arc_model_command == "validate":
            provenance = validate_model_source(args.path)
            return f"verified selected model source offline: {provenance['content_digest']}"
    if args.command == "arc-agi-2" and args.arc_command == "trial":
        if args.arc_trial_command == "prepare":
            contract = prepare_arc_trial(args.source, args.output)
            return f"prepared ARC-AGI-2 Trial 001 offline: {contract.content_digest}"
        if args.arc_trial_command == "validate":
            contract = validate_trial_bundle(args.path)
            return f"verified ARC-AGI-2 Trial 001 offline: {contract.content_digest}"
        if args.arc_trial_command == "outbound-build":
            digest = build_outbound_package(
                args.trial,
                args.model_source,
                args.binding,
                args.runtime_wheels,
                args.output,
                repository_root=repository_root,
            )
            return f"built closed-world Kaggle trial input: {digest}"
        if args.arc_trial_command == "outbound-verify":
            _, digest = verify_outbound_package(args.path)
            return f"verified closed-world Kaggle trial input: {digest}"
        if args.arc_trial_command == "preflight":
            if args.output.exists():
                raise ValidationError(f"preflight output already exists: {args.output}")
            report = kaggle_preflight(
                args.trial, args.model_source, args.trial_package, args.binding
            )
            write_artifact(args.output, report)
            state = "technically ready; owner authorization still absent" if report["payload"]["technical_ready"] else "blocked"
            return f"wrote Kaggle technical preflight ({state}): {report['content_digest']}"
    if args.command == "arc-agi-2" and args.arc_command == "result":
        if args.arc_result_command == "verify":
            _, _, digest = verify_result_package(args.package, args.trial_package, args.trial)
            return f"verified untrusted result package offline: {digest}"
        if args.arc_result_command == "benchmark-verify":
            _, _, digest = verify_benchmark_result_package(args.package, args.trial_package)
            return f"verified untrusted four-invocation benchmark result: {digest}"
        if args.arc_result_command == "import":
            target = import_quarantine(args.package, args.trial_package, args.trial, args.run_root)
            return f"validated and normalized quarantine result: {target}"
        if args.arc_result_command == "evaluate":
            summary = evaluate_imported_run(args.trial, args.run)
            return (
                f"completed local ARC scoring and selection: {summary['selection_outcome']} "
                f"(P2 accepted={summary['p2_accepted']})"
            )
    if args.command == "arc-agi-2" and args.arc_command == "package":
        if args.arc_package_command == "build":
            manifest = build_arc_package(
                args.trial,
                args.source,
                args.run,
                args.model_source,
                args.trial_package,
                args.result_package,
                args.output,
            )
            return f"built eligible ARC Domain Package: {manifest.content_digest}"
        if args.arc_package_command == "verify":
            manifest = verify_arc_package(args.path)
            return f"verified ARC Domain Package: {manifest.content_digest}"
    if args.command == "arc-agi-2" and args.arc_command == "baseline":
        if args.baseline_command == "prepare":
            run = prepare_trial_002(args.source, args.competition_challenges, args.output)
            return f"prepared ARC-AGI-2 Trial 002 smoke: {run['run_identity_digest']}"
        if args.baseline_command == "validate":
            run = validate_trial_002(args.path)
            return f"verified ARC-AGI-2 Trial 002 smoke offline: {run['run_identity_digest']}"
        if args.baseline_command == "outbound-build":
            digest = build_trial_002_outbound(
                args.trial,
                args.model,
                args.nvarc,
                args.wheels,
                args.output,
                repository_root=repository_root,
            )
            return f"built Trial 002 truth-free outbound: {digest}"
        if args.baseline_command == "outbound-verify":
            _, _, digest = verify_trial_002_outbound(args.path)
            return f"verified Trial 002 truth-free outbound: {digest}"
        if args.baseline_command == "kernel-stage":
            metadata = stage_trial_002_kernel(
                args.template,
                args.output,
                expected_dataset_ref=args.dataset_ref,
                outbound_digest=args.outbound_digest,
            )
            return f"staged Trial 002 Kaggle kernel: {metadata['id']}"
        if args.baseline_command == "preflight":
            if args.output.exists():
                raise ValidationError(f"preflight output already exists: {args.output}")
            report = trial_002_preflight(
                args.trial,
                args.outbound,
                args.model,
                args.nvarc,
                args.wheels,
                args.competition_challenges,
                args.dataset,
                args.kernel,
                args.dataset_ref,
            )
            write_json(args.output, report)
            return f"wrote Trial 002 package preflight (technical_ready={report['technical_ready']}): {digest_value(report)}"
        if args.baseline_command == "result-verify":
            _, _, digest = verify_trial_002_result(args.package, args.outbound)
            return f"verified untrusted Trial 002 result offline: {digest}"
        if args.baseline_command == "result-import":
            target = import_trial_002_quarantine(args.package, args.outbound, args.quarantine)
            return f"verified and imported Trial 002 result to quarantine: {target}"
        if args.baseline_command == "result-score":
            if args.output.exists():
                raise ValidationError(f"score output already exists: {args.output}")
            score = score_trial_002_quarantined(args.trial, args.quarantined)
            write_json(args.output, score)
            return f"scored Trial 002 smoke locally: {score['passed_test_outputs']}/{score['total_test_outputs']} ({score['score']:.6f})"
    raise ValidationError("unsupported command")
