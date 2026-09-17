"""IRIS-X provider-neutral contract and admission command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .admission import admission_summary, validate_admission_file
from .errors import IrisxError, ValidationError
from .fixture import prepare_fixture, run_trial, validate_specification, validate_trial
from .package import build_package, verify_package


def _path(value: str) -> Path:
    return Path(value).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="irisx", description="IRIS-X offline product-contract and admission CLI")
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
