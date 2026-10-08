"""Offline argv verification against exact official Kaggle CLI parser source.

Never imports Kaggle, authenticates, reads credentials, calls an API callback or
executes a CLI command. Only reviewed argparse construction statements run.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

from tools.nvarc_native_multitask import require

KAGGLE_224_CLI_SHA256 = '8ed42fe894ba75631cec80b99bf736e1c69c48799df54ce89457f8d0ae9a7edd'
KAGGLE_224_SUBMIT_HELP_SHA256 = '2f3b6ec1be1b6cdd58afd58f3c5987e4b9cabd79b2d4b4032340c0fd11966a54'


def submission_parser(source_path, *, expected_sha256=KAGGLE_224_CLI_SHA256):
    body = Path(source_path).read_bytes()
    require(hashlib.sha256(body).hexdigest() == expected_sha256, 'independently pinned official CLI source differs')
    tree = ast.parse(body)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'parse_competitions')
    def target(node, name):
        return isinstance(node, ast.Assign) and any(isinstance(item, ast.Name) and item.id == name for item in node.targets)
    begin = next(index for index, node in enumerate(function.body) if target(node, 'parser_competitions_submit'))
    end = next(index for index, node in enumerate(function.body) if target(node, 'parser_competitions_submissions'))
    selected = function.body[:4]+function.body[begin:end]
    used_help = {node.attr for statement in selected for node in ast.walk(statement)
                 if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'Help'}
    help_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Help')
    help_values = {}
    for statement in help_class.body:
        if isinstance(statement, ast.Assign):
            for name in statement.targets:
                if isinstance(name, ast.Name) and name.id in used_help: help_values[name.id] = ast.literal_eval(statement.value)
    require(set(help_values) == used_help, 'complete literal vendor parser help required')
    calls = []
    def forbidden_callback(*args, **kwargs):
        calls.append((args, kwargs)); raise RuntimeError('offline parser must never invoke competition API')
    parser = argparse.ArgumentParser(prog='kaggle')
    subparsers = parser.add_subparsers(dest='command'); subparsers.required = True
    namespace = {'argparse': argparse, 'Help': SimpleNamespace(**help_values), 'subparsers': subparsers,
                 'api': SimpleNamespace(competition_submit_cli=forbidden_callback)}
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, 'pinned-kaggle224-submit-parser', 'exec'), namespace)
    require(not calls, 'parser construction invoked a forbidden callback')
    return parser, calls


def verify_submission_argv(source_path, argv):
    require(isinstance(argv, list) and argv[:3] == ['kaggle', 'competitions', 'submit'], 'competition argv data required')
    parser, calls = submission_parser(source_path)
    result = vars(parser.parse_args(argv[1:])); result.pop('func')
    require(not calls, 'offline argv parsing invoked competition API')
    return {'cli_version': '2.2.4', 'cli_source_sha256': KAGGLE_224_CLI_SHA256,
            'parsed_arguments': result, 'api_calls': 0, 'credential_reads': 0, 'commands_executed': 0}
