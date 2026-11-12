"""Run Daylight's five evaluation suites and write a dated report.

    python3 tools/evaluation/run_suites.py                    # all suites
    python3 tools/evaluation/run_suites.py --suite abstention
    python3 tools/evaluation/run_suites.py --check            # validate config only

Run from the repository root with Python 3.11 or newer (the repo uses 3.14).
Every suite is offline and uses fictional data. A suite passes only when every
command exits 0; a missing requirement (such as pytest) is reported as
"unavailable", never as a pass.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name("suites.json")
TIMEOUT_SECONDS = 900
MIN_PYTHON = (3, 11)


def load(config_path: Path = CONFIG) -> dict:
    config = json.loads(config_path.read_text())
    if config.get("schema") != "daylight-evaluation-suites/1":
        raise SystemExit("Unsupported suites.json schema")
    return config


def check(config: dict) -> list[str]:
    problems = []
    ids = [s["suite_id"] for s in config["suites"]]
    if len(ids) != len(set(ids)):
        problems.append("duplicate suite_id")
    for suite in config["suites"]:
        for command in suite["commands"]:
            cwd = ROOT / command["cwd"]
            if not cwd.is_dir():
                problems.append(f"{suite['suite_id']}: missing directory {command['cwd']}")
                continue
            argv = command["argv"]
            if argv[1:2] == ["-m"] and argv[2] == "unittest":
                targets = [a for a in argv[3:] if not a.startswith("-")]
                for target in targets:
                    if not (cwd / (target.split(".")[0] + ".py")).is_file():
                        problems.append(f"{suite['suite_id']}: missing test module {target}")
            for arg in argv[1:]:
                if arg.endswith(".py") and not (cwd / arg).is_file():
                    problems.append(f"{suite['suite_id']}: missing file {command['cwd']}/{arg}")
    return problems


def _tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def run_command(command: dict, report_dir: Path) -> dict:
    missing = [name for name in command.get("requires", []) if importlib.util.find_spec(name) is None]
    argv = [part.replace("{python}", sys.executable).replace("{report_dir}", str(report_dir))
            for part in command["argv"]]
    entry = {"cwd": command["cwd"], "argv": [Path(a).name if a == sys.executable else a for a in argv]}
    if missing:
        return {**entry, "status": "unavailable", "detail": f"missing: {', '.join(missing)}"}
    start = time.monotonic()
    try:
        done = subprocess.run(argv, cwd=ROOT / command["cwd"], capture_output=True, text=True,
                              timeout=TIMEOUT_SECONDS, env={**_clean_env(), "PYTHONDONTWRITEBYTECODE": "1",
                                                            "PYTHONPATH": str(ROOT / "infrastructure/daylight-operations/src")})
    except subprocess.TimeoutExpired:
        return {**entry, "status": "failed", "detail": f"timed out after {TIMEOUT_SECONDS}s"}
    return {**entry, "status": "passed" if done.returncode == 0 else "failed", "exit_code": done.returncode,
            "seconds": round(time.monotonic() - start, 1), "output_tail": _tail(done.stdout + "\n" + done.stderr)}


def _clean_env() -> dict:
    import os
    # Never hand provider credentials to test processes.
    return {k: v for k, v in os.environ.items()
            if not any(s in k.upper() for s in ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "DATABASE_URL", "DSN"))}


def run(config: dict, selected: set[str] | None, report_dir: Path) -> dict:
    report_dir.mkdir(parents=True, exist_ok=True)
    suites = []
    for suite in config["suites"]:
        if selected and suite["suite_id"] not in selected:
            continue
        commands = [run_command(command, report_dir) for command in suite["commands"]]
        states = {c["status"] for c in commands}
        status = "failed" if "failed" in states else "unavailable" if "unavailable" in states else "passed"
        suites.append({"suite_id": suite["suite_id"], "status": status, "measures": suite["measures"],
                       "gaps": suite["gaps"], "commands": commands})
    return {"schema": "daylight-evaluation-report/1",
            "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version.split()[0], "paid_model_calls": 0,
            "suites": suites, "passed": all(s["status"] == "passed" for s in suites)}


def markdown(report: dict) -> str:
    lines = [f"# Evaluation report · {report['run_at']}", "",
             f"Python {report['python']}. Offline; {report['paid_model_calls']} paid model calls.", "",
             "| Suite | Result | Known gaps |", "| --- | --- | --- |"]
    for suite in report["suites"]:
        lines.append(f"| {suite['suite_id']} | {suite['status']} | {' '.join(suite['gaps'])} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", action="append", help="Run only this suite (repeatable)")
    parser.add_argument("--out", type=Path, help="Report directory (default: outputs/evaluation/<UTC time>)")
    parser.add_argument("--check", action="store_true", help="Validate suites.json against the repository and exit")
    args = parser.parse_args(argv)
    config = load()
    problems = check(config)
    if args.check or problems:
        print("\n".join(problems) or "suites.json OK")
        return 1 if problems else 0
    if sys.version_info < MIN_PYTHON:
        print(f"Python {'.'.join(map(str, MIN_PYTHON))}+ required; this is {sys.version.split()[0]}")
        return 2
    known = {s["suite_id"] for s in config["suites"]}
    if args.suite and set(args.suite) - known:
        parser.error(f"unknown suite: {sorted(set(args.suite) - known)}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = args.out or ROOT / "outputs" / "evaluation" / stamp
    report = run(config, set(args.suite or []), report_dir)
    (report_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (report_dir / "REPORT.md").write_text(markdown(report))
    print(markdown(report))
    print(f"Report: {report_dir}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
