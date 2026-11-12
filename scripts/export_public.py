#!/usr/bin/env python3
"""Check and export a GitHub-ready source archive using only Python and Git.

Run from any directory with ``python scripts/export_public.py --check-only``.
Candidate files come from an empty, temporary Git repository and the source
tree's .gitignore rules; the real repository and its index are never changed.
Only the documented source directories are eligible for the archive.

The credential checks are conservative helper rules, not a complete security
audit: they cannot recognize every newly introduced secret or encoded value.
Keep .gitignore correct, review the archive, and never force-add private files.
This tool does not classify personal information or remove publicity assets.
No matched credential values are printed or written to a diagnostic file.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "TJ-ToothAI"
ALLOWED_FILES = {"README.md", ".env.example", ".gitignore"}
ALLOWED_DIRECTORIES = ("docs/", "tests/", "scripts/", "www/tjtooth/", "qrcode-server/")
BLOCKED_DIRECTORIES = {
    ".git", ".private", "private", ".aws", ".codex", ".agents",
    "ssl", "ssl_old", "certs", "certificates", "backup", "backups",
    "var", "temp", "uploads", "outputs", "reports", "patient_info",
    "patient_data", "patient_reports", "annotated_images", "logs",
    "venv", ".venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "dist", "build",
}
BLOCKED_SUFFIXES = {
    ".pem", ".key", ".p12", ".pfx", ".crt", ".cer", ".der", ".p7b",
    ".jks", ".keystore", ".db", ".sqlite", ".sqlite3", ".mdb",
    ".pth", ".pt", ".ckpt", ".onnx", ".h5", ".hdf5", ".safetensors",
    ".tflite", ".pyc", ".pyo", ".log", ".bak", ".backup", ".orig",
    ".zip", ".tar", ".tgz", ".gz", ".7z", ".rar",
}
PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)
TOKEN_PATTERNS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bpat_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
)
# Python uses AST checks; Markdown only checks quoted assignments, and vendor
# JS/CSS only undergo private-key and recognizable-token checks.
ASSIGNMENT_PATTERN = re.compile(
    r'''(?<![\w/])(?:["']?)([A-Za-z_][A-Za-z0-9_.-]*)["']?[ \t]*[:=][ \t]*'''
    r'''(?:"([^"\n]*)"|'([^'\n]*)'|([^\s,;#<>]+))'''
)


@dataclass(frozen=True, order=True)
class Issue:
    path: str
    line: int
    kind: str


@dataclass
class CheckedFile:
    path: str
    data: bytes
    mode: int


def is_allowed(path: str) -> bool:
    return path in ALLOWED_FILES or path.startswith(ALLOWED_DIRECTORIES)


def forbidden_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if "\\" in path or ":" in path or any(ord(character) < 32 for character in path):
        return True
    if not parts or any(part in ("", ".", "..") for part in parts):
        return True
    if PurePosixPath(path).is_absolute():
        return True
    lower = [part.lower() for part in parts]
    if any(part in BLOCKED_DIRECTORIES or part.startswith(".venv-") for part in lower):
        return True
    name = lower[-1]
    if (name == ".env" or name.startswith(".env.")) and path != ".env.example":
        return True
    if name.startswith(("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")):
        return True
    if name in {".ds_store", "thumbs.db", "nohup.out", "temp_image.jpg"}:
        return True
    if name.endswith("~") or any(mark in name for mark in (".bak.", ".backup.", ".log.")):
        return True
    return PurePosixPath(name).suffix in BLOCKED_SUFFIXES


def candidate_paths(root: Path) -> list[str]:
    """Ask a disposable Git index, not the user's real index, about ignores."""
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git-unavailable")
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("GIT_"):
            environment.pop(key)
    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
    })
    with tempfile.TemporaryDirectory(prefix="tjtooth-export-git-") as temporary:
        git_dir = Path(temporary) / "index.git"
        subprocess.run(
            [git, "init", "--bare", "--quiet", str(git_dir)],
            env=environment, check=True, capture_output=True,
        )
        result = subprocess.run(
            [git, "--git-dir=" + str(git_dir), "--work-tree=" + str(root),
             "-c", "core.excludesFile=" + os.devnull, "-c", "core.fsmonitor=false",
             "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=root, env=environment, check=True, capture_output=True,
        )
    paths = {os.fsdecode(item) for item in result.stdout.split(b"\0") if item}
    return sorted(path for path in paths if is_allowed(path))


def credential_name(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    return normalized.endswith((
        "apikey", "secretkey", "password", "passwd", "accesstoken", "authtoken",
        "token", "clientsecret", "secret", "privatekey", "accesskey",
        "accesskeyid", "secretaccesskey", "authorization",
    ))


def is_placeholder(value: str) -> bool:
    """Allow obvious examples; do not exempt every value in tests or docs."""
    value = value.strip()
    if not value:
        return True
    if re.fullmatch(r"<[^<>]+>|\$\{[A-Z0-9_]+\}", value):
        return True
    if re.fullmatch(r"(?:[A-Za-z]{2,8}[_-])?[xX*._-]+", value):
        return True
    if re.fullmatch(r"(?i)(?:your|replace|insert)[_-][a-z0-9_-]+", value):
        return True
    if re.fullmatch(r"(?i)(?:file|process)[_-](?:demo|test)[_-]value", value):
        return True
    return bool(re.fullmatch(
        r"(?i)(?:test|demo|dummy|fake|example|placeholder|changeme)"
        r"(?:[-_](?:only|api|key|token|secret|password|value|credential|123))*",
        value,
    ))


def literal_text(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        if isinstance(node.value, bytes):
            return node.value.decode("utf-8", errors="replace")
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return str(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = literal_text(node.left), literal_text(node.right)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr) and all(isinstance(part, ast.Constant) for part in node.values):
        return "".join(str(part.value) for part in node.values)
    return None


def target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, ast.Subscript):
        value = literal_text(node.slice)
        return [value] if value is not None else []
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for item in node.elts for name in target_names(item)]
    return []


def python_issues(path: str, text: str) -> list[Issue]:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as error:
        return [Issue(path, error.lineno or 1, "python-syntax")]
    issues = []

    def inspect(name: str, value: ast.AST | None, line: int) -> None:
        literal = literal_text(value)
        if credential_name(name) and literal is not None and not is_placeholder(literal):
            issues.append(Issue(path, line, "hardcoded-credential"))

    def inspect_binding(target: ast.AST, value: ast.AST, line: int) -> None:
        if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
            for left, right in zip(target.elts, value.elts):
                inspect_binding(left, right, line)
        else:
            for name in target_names(target):
                inspect(name, value, line)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                inspect_binding(target, node.value, node.lineno)
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            for name in target_names(node.target):
                inspect(name, node.value, node.lineno)
        elif isinstance(node, ast.keyword) and node.arg:
            inspect(node.arg, node.value, node.lineno)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                name = literal_text(key)
                if name is not None:
                    inspect(name, value, getattr(value, "lineno", node.lineno))
        elif isinstance(node, ast.Call) and len(node.args) >= 2:
            # Also reject a real fallback literal in getenv/get-style lookups.
            function = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            name = literal_text(node.args[0])
            if function in {"getenv", "get"} and name is not None:
                inspect(name, node.args[1], node.lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = node.args
            positional = arguments.posonlyargs + arguments.args
            if arguments.defaults:
                for argument, value in zip(positional[-len(arguments.defaults):], arguments.defaults):
                    inspect(argument.arg, value, node.lineno)
            for argument, value in zip(arguments.kwonlyargs, arguments.kw_defaults):
                inspect(argument.arg, value, node.lineno)
    return issues


def text_issues(path: str, data: bytes) -> list[Issue]:
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        text = data.decode("utf-32", errors="replace")
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16", errors="replace")
    else:
        text = data.decode("utf-8-sig", errors="replace")
    issues = []
    for pattern, kind in [(PRIVATE_KEY_PATTERN, "private-key-material")]:
        for match in pattern.finditer(text):
            issues.append(Issue(path, text.count("\n", 0, match.start()) + 1, kind))
    for pattern in TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            if not is_placeholder(match.group()):
                issues.append(Issue(path, text.count("\n", 0, match.start()) + 1, "token-pattern"))

    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {".py", ".wsgi"}:
        issues.extend(python_issues(path, text))
    elif suffix not in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp"}:
        vendored = "/static/js/" in path or "/static/css/" in path
        if not vendored:
            for match in ASSIGNMENT_PATTERN.finditer(text):
                if suffix == ".md" and match.group(2) is None and match.group(3) is None:
                    continue
                value = next((part for part in match.groups()[1:] if part is not None), "")
                if credential_name(match.group(1)) and not is_placeholder(value):
                    issues.append(Issue(path, text.count("\n", 0, match.start()) + 1, "hardcoded-credential"))
    return issues


def check_files(root: Path, paths: list[str]) -> tuple[list[CheckedFile], list[Issue]]:
    checked, issues = [], []
    for relative in paths:
        if forbidden_path(relative):
            issues.append(Issue(relative, 1, "forbidden-path"))
            continue
        path = root / relative
        current = root
        linked = False
        for component in PurePosixPath(relative).parts:
            current = current / component
            linked = linked or current.is_symlink()
        if linked:
            issues.append(Issue(relative, 1, "symlink"))
            continue
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as stream:
                status = os.fstat(stream.fileno())
                if not stat.S_ISREG(status.st_mode):
                    issues.append(Issue(relative, 1, "non-regular-file"))
                    continue
                data = stream.read()
        except OSError:
            issues.append(Issue(relative, 1, "unreadable-file"))
            continue
        issues.extend(text_issues(relative, data))
        # Archive exactly the checked bytes, even if source files later change.
        checked.append(CheckedFile(relative, data, stat.S_IMODE(status.st_mode)))
    return checked, sorted(set(issues))


def write_archive(output: Path, files: list[CheckedFile]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".tjtooth-export-", suffix=".zip", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in files:
                entry = zipfile.ZipInfo(ARCHIVE_ROOT + "/" + item.path)
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = (stat.S_IFREG | item.mode) << 16
                archive.writestr(entry, item.data)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Check candidates without creating an archive.")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/TJ-ToothAI-public.zip", help="Output ZIP path; relative paths use the current directory.")
    arguments = parser.parse_args(argv)
    try:
        paths = candidate_paths(ROOT)
        files, issues = check_files(ROOT, paths)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        print(".:1:candidate-check-failed", file=sys.stderr)
        return 1
    if issues:
        for issue in issues:
            print(f"{json.dumps(issue.path, ensure_ascii=False)}:{issue.line}:{issue.kind}", file=sys.stderr)
        return 1
    if not files:
        print(".:1:no-source-candidates", file=sys.stderr)
        return 1
    total = sum(len(item.data) for item in files)
    print(f"Checked {len(files)} files, {total} bytes; no blocking rule matched.")
    if arguments.check_only:
        return 0
    output = arguments.output.expanduser().absolute()
    if output.suffix.lower() != ".zip" or output.is_symlink():
        print(".:1:invalid-output-path", file=sys.stderr)
        return 1
    if any(output == ROOT / item.path for item in files):
        print(".:1:output-overlaps-source", file=sys.stderr)
        return 1
    try:
        write_archive(output, files)
    except (OSError, zipfile.BadZipFile, ValueError):
        print(".:1:archive-write-failed", file=sys.stderr)
        return 1
    print("Created " + str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
