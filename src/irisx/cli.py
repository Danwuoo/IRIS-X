"""IRIS-X offline contract, trial-preparation, and verification CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .admission import admission_summary, validate_admission_file
from .arc_agi2 import materialize_source, prepare_trial as prepare_arc_trial, validate_source, validate_trial_bundle
from .arc_package import build_arc_package, verify_arc_package
from .artifacts import write_artifact
from .errors import IrisxError, ValidationError
from .fixture import prepare_fixture, run_trial, validate_specification, validate_trial
from .kaggle import (
    build_outbound_package,
    evaluate_imported_run,
    import_quarantine,
    materialize_model,
    preflight as kaggle_preflight,
    validate_model_source,
    verify_outbound_package,
    verify_result_package,
)
from .package import build_package, verify_package


def _path(value: str) -> Path:
    return Path(value).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="irisx", description="IRIS-X offline contracts, trial preparation, and verification CLI")
    subcommands = parser.add_subparsers(dest="command", required=True)

    fixture = subcommands.add_parser("fixture", help="manage the synthetic offline qualification fixture")
    fixture_sub = fixture.add_subparsers(dest="fixture_command", required=True)
    fixture_prepare = fixture_sub.add_parser("prepare", help="write deterministic fixture inputs")
    fixture_prepare.add_argument("--output", required=True, type=_path)

    spec = subcommands.add_parser("spec", help="Domain Specification operations")
    spec_sub = spec.add_subparsers(dest="spec_command", required=True)
    spec_validate = spec_sub.add_parser("validate", help="validate a specification and its bound local evidence")
    spec_validate.add_argument("path", type=_path)

    trial = subcommands.add_parser("trial", help="Engineering Trial contract operations")
    trial_sub = trial.add_subparsers(dest="trial_command", required=True)
    trial_validate = trial_sub.add_parser("validate", help="validate a trial bundle without executing it")
    trial_validate.add_argument("path", type=_path)
    trial_run = trial_sub.add_parser("run", help="run the bounded deterministic reference adapter")
    trial_run.add_argument("--trial", required=True, type=_path)
    trial_run.add_argument("--output", required=True, type=_path)

    package = subcommands.add_parser("package", help="Domain Package operations")
    package_sub = package.add_subparsers(dest="package_command", required=True)
    package_build = package_sub.add_parser("build", help="build a package from a completed P1 run")
    package_build.add_argument("--run", required=True, type=_path)
    package_build.add_argument("--output", required=True, type=_path)
    package_verify = package_sub.add_parser("verify", help="independently verify every package artifact")
    package_verify.add_argument("path", type=_path)

    admission = subcommands.add_parser("admission", help="P2 admission package operations")
    admission_sub = admission.add_subparsers(dest="admission_command", required=True)
    admission_validate = admission_sub.add_parser("validate", help="validate the blocked P2 admission snapshot")
    admission_validate.add_argument("path", type=_path)

    arc = subcommands.add_parser("arc-agi-2", help="prepare and verify the admitted ARC-AGI-2 Trial 001 path")
    arc_sub = arc.add_subparsers(dest="arc_command", required=True)

    arc_source = arc_sub.add_parser("source", help="official ARC source operations")
    arc_source_sub = arc_source.add_subparsers(dest="arc_source_command", required=True)
    arc_source_materialize = arc_source_sub.add_parser("materialize", help="deliberately acquire the one pinned official ARC source")
    arc_source_materialize.add_argument("--output", required=True, type=_path)
    arc_source_validate = arc_source_sub.add_parser("validate", help="validate a local pinned ARC source offline")
    arc_source_validate.add_argument("path", type=_path)

    arc_model = arc_sub.add_parser("model", help="selected frozen Qwen raw-source operations")
    arc_model_sub = arc_model.add_subparsers(dest="arc_model_command", required=True)
    arc_model_materialize = arc_model_sub.add_parser("materialize", help="deliberately acquire the one selected model revision")
    arc_model_materialize.add_argument("--output", required=True, type=_path)
    arc_model_validate = arc_model_sub.add_parser("validate", help="validate a local selected model source offline")
    arc_model_validate.add_argument("path", type=_path)

    arc_trial = arc_sub.add_parser("trial", help="ARC trial construction, outbound transport, and preflight")
    arc_trial_sub = arc_trial.add_subparsers(dest="arc_trial_command", required=True)
    arc_trial_prepare = arc_trial_sub.add_parser("prepare", help="build isolated views and P1 contracts offline")
    arc_trial_prepare.add_argument("--source", required=True, type=_path)
    arc_trial_prepare.add_argument("--output", required=True, type=_path)
    arc_trial_validate = arc_trial_sub.add_parser("validate", help="validate the complete local Trial 001 bundle offline")
    arc_trial_validate.add_argument("path", type=_path)
    arc_outbound_build = arc_trial_sub.add_parser("outbound-build", help="build one closed-world trial-input.zip")
    arc_outbound_build.add_argument("--trial", required=True, type=_path)
    arc_outbound_build.add_argument("--model-source", required=True, type=_path)
    arc_outbound_build.add_argument("--binding", required=True, type=_path)
    arc_outbound_build.add_argument("--output", required=True, type=_path)
    arc_outbound_verify = arc_trial_sub.add_parser("outbound-verify", help="verify trial-input.zip offline")
    arc_outbound_verify.add_argument("path", type=_path)
    arc_preflight = arc_trial_sub.add_parser("preflight", help="write technical Kaggle readiness evidence without authorizing a run")
    arc_preflight.add_argument("--trial", required=True, type=_path)
    arc_preflight.add_argument("--model-source", required=True, type=_path)
    arc_preflight.add_argument("--trial-package", required=True, type=_path)
    arc_preflight.add_argument("--binding", required=True, type=_path)
    arc_preflight.add_argument("--output", required=True, type=_path)

    arc_result = arc_sub.add_parser("result", help="verify, quarantine-import, and locally score returned predictions")
    arc_result_sub = arc_result.add_subparsers(dest="arc_result_command", required=True)
    arc_result_verify = arc_result_sub.add_parser("verify", help="verify a result-package.zip without trusting quarantine")
    arc_result_verify.add_argument("--package", required=True, type=_path)
    arc_result_verify.add_argument("--trial-package", required=True, type=_path)
    arc_result_verify.add_argument("--trial", required=True, type=_path)
    arc_result_import = arc_result_sub.add_parser("import", help="promote a fully valid quarantine result into normalized run evidence")
    arc_result_import.add_argument("--package", required=True, type=_path)
    arc_result_import.add_argument("--trial-package", required=True, type=_path)
    arc_result_import.add_argument("--trial", required=True, type=_path)
    arc_result_import.add_argument("--run-root", required=True, type=_path)
    arc_result_evaluate = arc_result_sub.add_parser("evaluate", help="score, select, and apply P2 acceptance locally")
    arc_result_evaluate.add_argument("--trial", required=True, type=_path)
    arc_result_evaluate.add_argument("--run", required=True, type=_path)

    arc_package = arc_sub.add_parser("package", help="eligible ARC Domain Package operations")
    arc_package_sub = arc_package.add_subparsers(dest="arc_package_command", required=True)
    arc_package_build = arc_package_sub.add_parser("build", help="build a self-contained eligible ARC Domain Package")
    arc_package_build.add_argument("--trial", required=True, type=_path)
    arc_package_build.add_argument("--source", required=True, type=_path)
    arc_package_build.add_argument("--run", required=True, type=_path)
    arc_package_build.add_argument("--model-source", required=True, type=_path)
    arc_package_build.add_argument("--trial-package", required=True, type=_path)
    arc_package_build.add_argument("--result-package", required=True, type=_path)
    arc_package_build.add_argument("--output", required=True, type=_path)
    arc_package_verify = arc_package_sub.add_parser("verify", help="independently verify an ARC Domain Package")
    arc_package_verify.add_argument("path", type=_path)
    return parser


def execute(args: argparse.Namespace) -> str:
    if args.command == "fixture" and args.fixture_command == "prepare":
        prepare_fixture(args.output)
        return f"prepared deterministic fixture: {args.output}"
    if args.command == "spec" and args.spec_command == "validate":
        contract = validate_specification(args.path)
        return f"valid Domain Specification: {contract.artifact_id} {contract.content_digest}"
    if args.command == "trial" and args.trial_command == "validate":
        contract = validate_trial(args.path)
        return f"valid Engineering Trial: {contract.artifact_id} {contract.content_digest}"
    if args.command == "trial" and args.trial_command == "run":
        summary = run_trial(args.trial, args.output)
        return f"trial completed offline: {summary['outcome']} {summary['decision_digest']}"
    if args.command == "package" and args.package_command == "build":
        manifest = build_package(args.run, args.output)
        return f"built verified Domain Package: {manifest.content_digest}"
    if args.command == "package" and args.package_command == "verify":
        manifest = verify_package(args.path)
        return f"verified Domain Package: {manifest.content_digest}"
    if args.command == "admission" and args.admission_command == "validate":
        summary = admission_summary(validate_admission_file(args.path))
        return (
            f"valid P2 admission: {summary['status']} "
            f"({len(summary['unresolved_gates'])} unresolved gates; execution/promotion/package ineligible)"
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
            repository_root = Path(__file__).resolve().parents[2]
            digest = build_outbound_package(
                args.trial, args.model_source, args.binding, args.output, repository_root=repository_root
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
    raise ValidationError("unsupported command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        message = execute(parser.parse_args(argv))
    except (IrisxError, OSError) as exc:
        print(f"irisx: error: {exc}", file=sys.stderr)
        return 2
    print(message)
    return 0
