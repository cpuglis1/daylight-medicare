"""Prepare a private, reviewable projection of actual fictional validation trials.

Read local runner and optional subscription score receipts. Only the pinned
fictional prompts and screened reply text cross into the projected artifact.
The command never invokes a provider or publishes files.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import html
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import unicodedata

HERE = Path(__file__).resolve().parent
ADVISOR = HERE.parents[1] / 'alternatives/advisor-first'
STORE = ADVISOR / 'var/eval-diagnostics'
sys.path.insert(0, str(ADVISOR))
from identifier_guard import find_identifiers

# Pin all source bytes, including the cases with no executable start. See D155
# and LIVE_ADAPTER.md before updating these pins with reviewed replacements.
CORPUS_HASHES = {
    'conversational_continuity': 'f7cef835fe6308639ff6b8242f576a717d7e3188080e40c75f37bbe6cbfb4fb3',
    'medicare_factual_support': '8d9f23553351fd54c01ad293b46f73ce56198f1441210603464eb633477dcf49',
    'question_timing': 'b5742b380617e5b3bf07467738f8b4ce3a83c6993ac888e5329180a90f4ce04b',
    'required_coverage': '8d43ab9c57deeee8021226aaf970ffabdb173b169a967d1fb5c75ae73a3555a2',
    'tool_use': '7088caa0689713885da0670f11e41106d97a995dc8a17ca26f822b565d5b4257',
    'unsupported_inferences': 'c3d20cfa30bee62050bd74ba98ba4b9a17416162550307d5cf4ad9eddb37e578',
}
RUN_ID = r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
STATUS = {'observed', 'incomplete', 'error'}
DAYLIGHT_MODELS = {'gpt-5.4', 'gpt-6.1-sol', 'gpt-6.2-sol', 'claude-opus-5-5'}
JUDGE_MODELS = {None: {'haiku', 'sonnet'}, 'codex-chatgpt-subscription': {'gpt-6.2-sol'}}
MAX_INPUT = 160_000_000
MAX_TEXT = 12_000
MAX_REASON = 2_000
UNSAFE_TEXT = re.compile(
    r"""[<>`@\\]|\[[^\n]*\]\s*[\[(]|&(?:#\w+|\w+);|%[a-f0-9]{2}"""
    r"""|\b(?:https?|ftp|file|data|javascript|mailto|blob|vscode|plugin|ssh):|(?<!:)//"""
    r"""|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:[a-z]{2,24}|xn--[a-z0-9-]+)\b"""
    r"""|(?<!\w)(?:~?/|\.\.?/)[\w.]|\b\w+(?:/[-\w.]+){2,}"""
    r"""|\b(?:localhost|bearer(?:\s+\S+)?|authorization\s*:|"""
    r"""(?:api[ _-]?key|password|secret|session[ _-]?id|request[ _-]?id|token)\s*[:=])"""
    r"""|\b(?:sk|pk|ghp|gho|ghs|github_pat|xox[baprs]|acct|sess|chatcmpl|resp|req|"""
    r"""call|msg|turn|trace|user|tok)[_-][a-z0-9_-]{6,}\b"""
    r"""|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\b[a-f0-9]{20,}\b|\b[a-z0-9_+/=-]{36,}\b"""
    r"""|\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b"""
    r"""|\b(?:\d[. ()-]?){8,}\d\b|\b(?:\d{1,3}\.){3}\d{1,3}\b"""
    r"""|\b(?:BEGIN [A-Z ]*PRIVATE KEY|system prompt|ignore (?:all |any |the )?"""
    r"""(?:prior|previous|above) instructions|modelCalls|toolCalls|providerStatus)\b""", re.I
)


def require(condition, message):
    """Stop a malformed export using a fixed operator-facing error."""
    if not condition:
        raise ValueError(message)


def unique_fields(pairs):
    """Reject ambiguous duplicate object fields before any artifact join."""
    fields = dict(pairs)
    require(len(fields) == len(pairs), 'Artifact contains duplicate JSON fields.')
    return fields


def reject_constant(_value):
    """Reject expressions outside JSON's finite numeric representation."""
    raise ValueError('Artifact contains a non-JSON numeric value.')


def parse_object(raw):
    """Read a strict UTF-8 JSON object without exposing parser excerpts."""
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_fields, parse_constant=reject_constant)
    require(isinstance(data, dict), 'Expected a JSON object.')
    return data


def safe_text(value, limit=MAX_TEXT):
    """Accept bounded inert text after inspecting both original and normalized shapes."""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        return False
    if any(unicodedata.category(char).startswith('C') and char not in '\n\t' for char in value):
        return False
    if len(value.encode('utf-16-le')) // 2 > limit:
        return False
    normalized = unicodedata.normalize('NFKC', html.unescape(value))
    return all(not UNSAFE_TEXT.search(text) and not find_identifiers(text) for text in (value, normalized))


def load_validation_cases():
    """Index only the exact checked-in held-out prompts and their source-line hashes."""
    cases = {}
    for suite, expected_hash in CORPUS_HASHES.items():
        raw = (HERE / 'cases' / (suite + '.jsonl')).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected_hash, 'The pinned fictional corpus changed.')
        for line in raw.splitlines():
            case = parse_object(line)
            if case['split'] != 'heldout':
                continue
            key = case['id']
            require(suite == case['judge'] and key not in cases and safe_text(case['user_prompt']),
                    'The pinned fictional prompt failed export validation.')
            cases[key] = (case, hashlib.sha256(line).hexdigest())
    return cases


@contextmanager
def private_directory(path, parent=None):
    """Hold an operator-owned directory descriptor for relative, no-symlink file access."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY, dir_fd=parent)
    try:
        info = os.fstat(descriptor)
        require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                'Use a private operator-owned diagnostic directory.')
        yield descriptor
    finally:
        os.close(descriptor)


def read_private(directory, name):
    """Read a complete private regular file snapshot, refusing symlinks and concurrent writes."""
    with os.fdopen(os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory), 'rb') as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and stat.S_IMODE(before.st_mode) == 0o600 and before.st_size <= MAX_INPUT,
                'Use a bounded private regular artifact owned by the operator.')
        raw = handle.read(MAX_INPUT + 1)
        after = os.fstat(handle.fileno())
        require(len(raw) == before.st_size == after.st_size
                and before.st_mtime_ns == after.st_mtime_ns and before.st_ctime_ns == after.st_ctime_ns,
                'Artifact changed during the read.')
    return raw


def trial_key(row):
    """Accept the two stable trial coordinates without mixing booleans and integers."""
    require(isinstance(row, dict) and isinstance(row.get('caseId'), str)
            and type(row.get('trial')) is int, 'Artifact has an invalid trial key.')
    return row['caseId'], row['trial']


def validation_partition(manifest, cases, run_id):
    """Validate a full validation manifest and preserve which fixtures lacked executable starts."""
    bound = manifest.get('requestedCaseIds')
    unbound = manifest.get('unbound')
    repetitions = manifest.get('trialsPerCase')
    require(manifest.get('runId') == run_id and type(repetitions) is int and 1 <= repetitions <= 10
            and isinstance(bound, list) and bound and isinstance(unbound, list)
            and all(isinstance(key, str) for key in bound + unbound)
            and len(set(bound + unbound)) == len(bound) + len(unbound)
            and set(bound + unbound) == set(cases), 'Invalid or incomplete validation manifest.')
    return bound, unbound, repetitions


def judge_scores(report, run, source_hash, trials, cases):
    """Bind an optional score report to this exact run snapshot and its validation trial keys."""
    if report is None:
        return {}
    require(report.get('kind') == 'live_turn_scores' and report.get('runId') == run['runId']
            and report.get('sourceHash') == source_hash and report.get('identity') == run['identity']
            and isinstance(report.get('scores'), list), 'Scores do not match the live run.')
    provider = report.get('judgeProvider')
    require(provider is None or provider == 'codex-chatgpt-subscription',
            'Unsupported subscription judge provenance.')
    if provider is not None:
        version = report.get('judgeVersion')
        require(isinstance(version, str) and re.fullmatch(r'[a-f0-9]{64}', version),
                'Score report is missing the subscription judge version.')
    collected = {}
    for row in report['scores']:
        key = trial_key(row)
        require(key in trials and key not in collected
                and row.get('suite') == cases[key[0]][0]['judge'] and row.get('split') == 'heldout',
                'Score trial does not match the live run.')
        score = None
        verdict, confidence, model = (row.get(field) for field in ('verdict', 'confidence', 'model'))
        if verdict in ('pass', 'fail'):
            require(trials[key]['status'] == 'observed' and type(confidence) in (float, int)
                    and 0 <= confidence <= 1 and isinstance(model, str) and model in JUDGE_MODELS[provider],
                    'Score is invalid for the observed trial.')
            score = {'score': verdict, 'scoreModel': model, 'scoreSource': 'subscription-judge'}
            reason = row.get('reason')
            if safe_text(reason, MAX_REASON):
                score['scoreReason'] = reason
        else:
            require(verdict in ('error', 'unscored'), 'Score verdict is invalid.')
            if verdict == 'error' and trials[key]['status'] == 'observed':
                score = {'score': 'error', 'scoreSource': 'subscription-judge'}
                if isinstance(model, str) and model in JUDGE_MODELS[provider]:
                    score['scoreModel'] = model
        collected[key] = score
    require(collected.keys() == trials.keys(), 'Score report does not cover the live trial keys.')
    return collected


def timestamp(value):
    """Accept runner timestamps only when they are actual UTC instants."""
    require(isinstance(value, str) and re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)', value, re.ASCII),
        'Invalid or missing runner timestamp.')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def metadata(run, run_id):
    """Project allowlisted capture metadata and enforce the diagnostic run ceiling."""
    identity = run.get('identity')
    require(type(run.get('schemaVersion')) is int and run['schemaVersion'] == 1
            and run.get('kind') == 'live_turn_observations' and run.get('runId') == run_id
            and isinstance(identity, dict) and isinstance(run.get('trials'), list),
            'Invalid or incomplete live observation artifact.')
    started, completed = timestamp(run.get('startedAt')), timestamp(run.get('completedAt'))
    cap, accounted, measured = (run.get(key) for key in ('capCents', 'accountedNanoUsd', 'measuredNanoUsd'))
    revision, requested = identity.get('revision'), identity.get('requestedModel')
    require(isinstance(revision, str) and re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})', revision)
            and identity.get('releaseEligible') is False
            and isinstance(requested, str) and requested in DAYLIGHT_MODELS
            and started <= completed and type(cap) is int and 1 <= cap <= 1000
            and type(accounted) is int and type(measured) is int and 0 <= measured <= accounted <= cap * 10_000_000,
            'Live observation metadata failed validation.')
    return {'schemaVersion': 1, 'kind': 'demo_turn_observations',
            'publication': 'operator_reviewed_fictional_redacted', 'runId': run_id,
            'identity': {'revision': revision, 'releaseEligible': False, 'requestedModel': requested},
            **{key: run[key] for key in ('startedAt', 'completedAt', 'capCents',
                                       'accountedNanoUsd', 'measuredNanoUsd')}}


def project(run_id, raw, manifest, report, cases):
    """Export observed statuses and screened replies without copying any raw trace fields."""
    run = parse_object(raw)
    result = metadata(run, run_id)
    bound, unbound, repetitions = validation_partition(manifest, cases, run_id)
    planned = {(case, n) for case in bound for n in range(1, repetitions + 1)}
    trials = {}
    for row in run['trials']:
        key = trial_key(row)
        require(key in planned and key not in trials, 'Unexpected or duplicate observation trial.')
        case, line_hash = cases[key[0]]
        status, trace = row.get('status'), row.get('trace')
        require(isinstance(status, str) and status in STATUS and row.get('rawLineHash') == line_hash
                and (trace is None or isinstance(trace, dict) and trace.get('message') == case['user_prompt'])
                and (status != 'observed' or trace is not None and isinstance(row.get('reply'), str)
                     and bool(row['reply'].strip())), 'Observation differs from its pinned fictional trial.')
        trials[key] = row
    require(trials.keys() == planned, 'Live observation is missing planned trials.')
    require(len(trials) <= 500, 'Live observation exceeds the demo trial limit.')
    scores = judge_scores(report, run, hashlib.sha256(raw).hexdigest(), trials, cases)
    projected = []
    for key in bound:
        for n in range(1, repetitions + 1):
            row = trials[key, n]
            status, candidate = row['status'], row.get('reply')
            public_trial = {field: row[field] for field in ('caseId', 'rawLineHash', 'trial', 'status')}
            public_trial['prompt'] = cases[key][0]['user_prompt']
            score = scores.get((key, n)) or {}
            if status != 'error' and safe_text(candidate):
                public_trial['reply'] = candidate
                public_trial.update(score)
            else:
                # A judge's reason may quote the withheld reply. Keep the structured verdict.
                public_trial.update({field: value for field, value in score.items() if field != 'scoreReason'})
            projected.append(public_trial)
    models = {row['scoreModel'] for row in projected if 'scoreModel' in row}
    if len(models) == 1:
        result['judgeModel'] = models.pop()
    return {**result, 'trials': projected, 'unboundCaseIds': unbound}


def write_export(directory, data):
    """Install a complete digest-named file atomically without overwriting any existing entry."""
    raw = (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    name = f'demo-observation-{hashlib.sha256(raw).hexdigest()}.json'
    scratch = f'.demo-observation-{secrets.token_hex(16)}.partial'
    descriptor = os.open(scratch, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(scratch, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        except FileExistsError:
            require(read_private(directory, name) == raw, 'Existing export path does not match its digest.')
    finally:
        os.unlink(scratch, dir_fd=directory)
    return name


def main(argv=None):
    """Validate operator-selected private input paths and print only the export filename."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observation', type=Path)
    parser.add_argument('--scores', type=Path)
    args = parser.parse_args(argv)
    try:
        match = re.fullmatch(r'live-observation-(' + RUN_ID + r')\.json', args.observation.name)
        require(match and args.observation.absolute().parent == STORE,
                'Select a completed artifact in the private diagnostic directory.')
        if args.scores is not None:
            require(args.scores.absolute().parent == STORE and args.scores.name.endswith('.scores.json'),
                    'Select a score artifact in the private diagnostic directory.')
        run_id = match.group(1)
        with private_directory(STORE) as directory:
            raw = read_private(directory, args.observation.name)
            with private_directory('progress', directory) as progress:
                manifest = parse_object(read_private(progress, run_id + '.manifest'))
            report = parse_object(read_private(directory, args.scores.name)) if args.scores else None
            result = project(run_id, raw, manifest, report, load_validation_cases())
            print(write_export(directory, result))
    except (OSError, ValueError, RecursionError):
        # Neither parser diagnostics nor path exceptions may reveal private input values.
        parser.error('Export refused. Check the pinned validation artifacts and private permissions.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
