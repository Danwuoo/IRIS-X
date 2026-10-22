"""python -m tools.cpt_data_admission_20261021 --help"""
import argparse
import json
from .admission import AdmissionError, admit, verify_bundle


def main():
    parser = argparse.ArgumentParser(description="Offline, bounded grid-corpus prerequisite admission. No training or acquisition.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("admit")
    build.add_argument("--registry", required=True)
    build.add_argument("--registry-sha256", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--max-total-bytes", type=int, default=64 * 1024 * 1024)
    build.add_argument("--max-record-bytes", type=int, default=1024 * 1024)
    build.add_argument("--max-records", type=int, default=100_000)
    build.add_argument("--stop-after-records", type=int)
    verify = sub.add_parser("verify")
    verify.add_argument("bundle")
    args = parser.parse_args()
    try:
        if args.command == "verify":
            result = verify_bundle(args.bundle)
        else:
            result = admit(args.registry, args.registry_sha256, args.output,
                           limits={"max_total_bytes": args.max_total_bytes, "max_record_bytes": args.max_record_bytes,
                                   "max_records": args.max_records}, stop_after_records=args.stop_after_records)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (AdmissionError, OSError) as exc:
        print(json.dumps({"status": "blocked_not_sealed", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
