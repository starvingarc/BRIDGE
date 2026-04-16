from __future__ import annotations

import argparse
import json

from bridge.workflows.cls import run_cls_workflow
from bridge.workflows.config import load_config, load_config_list
from bridge.workflows.identity import run_identity_workflow
from bridge.workflows.report import run_report_summary, run_report_summary_batch


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bridge", description="BRIDGE workflow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    identity_parser = subparsers.add_parser("identity", help="Run Step 2 identity assessment workflows")
    identity_subparsers = identity_parser.add_subparsers(dest="subcommand", required=True)
    identity_run = identity_subparsers.add_parser("run", help="Run identity workflow")
    identity_run.add_argument("--config", required=True, help="Path to workflow YAML config")
    identity_run.add_argument("--dry-run", action="store_true", help="Validate config and print run plan only")

    cls_parser = subparsers.add_parser("cls", help="Run Step 3 CLS workflows")
    cls_subparsers = cls_parser.add_subparsers(dest="subcommand", required=True)
    cls_run = cls_subparsers.add_parser("run", help="Run CLS workflow")
    cls_run.add_argument("--config", required=True, help="Path to workflow YAML config")
    cls_run.add_argument("--dry-run", action="store_true", help="Validate config and print run plan only")

    report_parser = subparsers.add_parser("report", help="Run reporting workflows")
    report_subparsers = report_parser.add_subparsers(dest="subcommand", required=True)
    report_run = report_subparsers.add_parser("summarize", help="Summarize CLS outputs into CSV and JSON")
    report_run.add_argument("--config", required=True, help="Path to workflow YAML config")
    report_run.add_argument("--dry-run", action="store_true", help="Validate config and print run plan only")
    report_batch = report_subparsers.add_parser("summarize-batch", help="Summarize multiple dataset configs into per-dataset and combined reports")
    report_batch.add_argument("--config-list", required=True, help="Path to YAML file containing a list of config paths")
    report_batch.add_argument("--dry-run", action="store_true", help="Validate config list and print run plan only")
    return parser


def _print_plan(plan: dict) -> None:
    print(json.dumps(plan, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "identity" and args.subcommand == "run":
        config = load_config(args.config)
        result = run_identity_workflow(config, dry_run=args.dry_run)
    elif args.command == "cls" and args.subcommand == "run":
        config = load_config(args.config)
        result = run_cls_workflow(config, dry_run=args.dry_run)
    elif args.command == "report" and args.subcommand == "summarize":
        config = load_config(args.config)
        result = run_report_summary(config, dry_run=args.dry_run)
    elif args.command == "report" and args.subcommand == "summarize-batch":
        config_batch = load_config_list(args.config_list)
        result = run_report_summary_batch(config_batch, dry_run=args.dry_run)
    else:
        parser.error("Unsupported command")
        return 2

    if args.dry_run:
        _print_plan(result)
    return 0
