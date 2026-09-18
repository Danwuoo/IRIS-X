"""IRIS-X contract, admission, and bounded trial command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .admission import admission_summary, validate_admission_file
from .arc_agi_2 import (
    build_p2_package,
    materialize_source,
    preflight_trial as preflight_arc_trial,
    prepare_trial as prepare_arc_trial,
    select_run as select_arc_run,
    validate_run_results as validate_arc_results,
    validate_source as validate_arc_source,
    validate_trial_bundle as validate_arc_trial,
    verify_p2_package,
)
from .artifacts import write_artifact
from .errors import IrisxError, ValidationError
from .fixture import prepare_fixture, run_trial, validate_specification, validate_trial
from .package import build_package, verify_package


def _path(value: str) -> Path:
    return Path(value).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="irisx",
        description="IRIS-X product-contract, admission, and bounded trial evidence CLI",
    )
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

    arc = subcommands.add_parser("arc-agi-2", help="manage the bounded local/offline ARC-AGI-2 Trial 001 path")
    arc_sub = arc.add_subparsers(dest="arc_command", required=True)
    arc_source = arc_sub.add_parser("source", help="official pinned-source operations")
    arc_source_sub = arc_source.add_subparsers(dest="source_command", required=True)
    arc_materialize = arc_source_sub.add_parser(
        "materialize",
        help="deliberately acquire only the fixed official repository and commit (networked source acquisition)",
    )
    arc_materialize.add_argument("--output", required=True, type=_path)
    arc_source_validate = arc_source_sub.add_parser("validate", help="validate the preserved source offline")
    arc_source_validate.add_argument("path", type=_path)

    arc_trial = arc_sub.add_parser("trial", help="prepare and validate Trial 001 without executing a solver")
    arc_trial_sub = arc_trial.add_subparsers(dest="arc_trial_command", required=True)
    arc_prepare = arc_trial_sub.add_parser("prepare", help="build isolated views and the existing P1 contract graph offline")
    arc_prepare.add_argument("--source", required=True, type=_path)
    arc_prepare.add_argument("--output", required=True, type=_path)
    arc_validate = arc_trial_sub.add_parser("validate", help="validate contracts, isolation, identity, and evaluator bindings offline")
    arc_validate.add_argument("path", type=_path)
    arc_preflight = arc_trial_sub.add_parser("preflight", help="fail closed unless every technical and owner-authorization gate passes")
    arc_preflight.add_argument("path", type=_path)
    arc_preflight.add_argument("--output", type=_path)

    arc_result = arc_sub.add_parser("result", help="future result-evidence operations; never executes a model or solver")
    arc_result_sub = arc_result.add_subparsers(dest="result_command", required=True)
    arc_result_validate = arc_result_sub.add_parser("validate", help="independently recompute and validate stored result evidence")
    arc_result_validate.add_argument("path", type=_path)

    arc_select = arc_sub.add_parser("select", help="recompute generic selection and the separate P2 acceptance gate")
    arc_select.add_argument("path", type=_path)

    arc_package = arc_sub.add_parser("package", help="P2 package operations")
    arc_package_sub = arc_package.add_subparsers(dest="arc_package_command", required=True)
    arc_package_build = arc_package_sub.add_parser("build", help="build a P2 package only from accepted, preflighted evidence")
    arc_package_build.add_argument("--run", required=True, type=_path)
    arc_package_build.add_argument("--output", required=True, type=_path)
    arc_package_verify = arc_package_sub.add_parser("verify", help="independently verify a closed-world P2 package")
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
        if args.source_command == "materialize":
            source = materialize_source(args.output)
            return f"materialized pinned official ARC-AGI-2 source: {source['payload']['head_commit']}"
        if args.source_command == "validate":
            source = validate_arc_source(args.path)
            return f"valid pinned official ARC-AGI-2 source: {source['content_digest']}"
    if args.command == "arc-agi-2" and args.arc_command == "trial":
        if args.arc_trial_command == "prepare":
            trial = prepare_arc_trial(args.source, args.output)
            return f"prepared offline ARC-AGI-2 Trial 001: {trial.content_digest}"
        if args.arc_trial_command == "validate":
            trial = validate_arc_trial(args.path)
            return f"valid offline ARC-AGI-2 Trial 001: {trial.content_digest}"
        if args.arc_trial_command == "preflight":
            report = preflight_arc_trial(args.path)
            if args.output is not None:
                write_artifact(args.output, report)
            if not report["payload"]["ready"]:
                raise ValidationError(
                    "ARC-AGI-2 Trial 001 preflight blocked: "
                    + ", ".join(report["payload"]["blockers"])
                )
            return f"ARC-AGI-2 Trial 001 preflight ready: {report['content_digest']}"
    if args.command == "arc-agi-2" and args.arc_command == "result" and args.result_command == "validate":
        baseline, candidate = validate_arc_results(args.path)
        return f"valid ARC-AGI-2 result evidence: {baseline.content_digest} {candidate.content_digest}"
    if args.command == "arc-agi-2" and args.arc_command == "select":
        decision, acceptance = select_arc_run(args.path)
        return (
            f"ARC-AGI-2 selection: {decision.payload['outcome']}; "
            f"P2 accepted={str(acceptance['payload']['accepted']).lower()}"
        )
    if args.command == "arc-agi-2" and args.arc_command == "package":
        if args.arc_package_command == "build":
            manifest = build_p2_package(args.run, args.output)
            return f"built verified ARC-AGI-2 Domain Package: {manifest.content_digest}"
        if args.arc_package_command == "verify":
            manifest = verify_p2_package(args.path)
            return f"verified ARC-AGI-2 Domain Package: {manifest.content_digest}"
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
