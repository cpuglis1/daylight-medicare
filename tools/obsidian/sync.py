#!/usr/bin/env python3
"""Local, non-destructive Daylight knowledge projection. No network/model calls."""
import argparse
import collections
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
VAULT_NAME = 'daylight_obsidian'
MARKER = '\n<!-- daylight:personal-notes -->\n'
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.cache',
             '.pytest_cache', 'tmp', VAULT_NAME, '.DS_Store'}
PRIVATE_DIRS = {'var', 'conversations', 'demo-sessions', 'eval-private', 'guest-stores',
                'customer-data', 'private-transcripts', 'local-checkpoints'}
TEXT_EXT = {'.md', '.txt', '.rst'}
MAX_TEXT = 2_000_000
SECRET = re.compile(r'(?s)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{28,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,})\b')
GOVERNING = {'PRINCIPLES.md', 'AGENTS.md', 'DAYLIGHT_REQUIREMENTS.md', 'PRODUCT.md',
             'DESIGN.md', 'docs/project/CURRENT_STATE.md', 'docs/product/MASTER_DESIGN.md',
             'docs/product/STRATEGIC_THESIS.md', 'docs/project/DIRECTIVE_HISTORY.md'}

def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def slug(s):
    return re.sub(r'[^\w .-]+', '-', s, flags=re.UNICODE).strip(' .-')[:100] or 'Source'

def dump(path, value):
    atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.daylight-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(value if isinstance(value, bytes) else value.encode())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def frontmatter(data):
    return '---\n' + '\n'.join(k + ': ' + json.dumps(v, ensure_ascii=False) for k, v in data.items()) + '\n---\n\n'

def read_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default

def safe_target(vault, relative):
    target = vault / relative
    if not target.resolve().is_relative_to(vault.resolve()):
        raise ValueError('Output escapes vault: ' + str(relative))
    return target

def note_path(kind, title, source_id):
    return f'90 Sources/{kind}/{slug(title)}--{digest(source_id)[:12]}.md'

def wiki(path, label=None):
    return '[[' + str(path).removesuffix('.md') + ('|' + label.replace('|', '-') if label else '') + ']]'

def redact(text):
    return SECRET.subn('[REDACTED CREDENTIAL — original retained at source]', text)

def role(path):
    if path in GOVERNING:
        return 'governing'
    if any(x in path.split('/') for x in ['before', 'history', 'archive', 'snapshot']):
        return 'historical'
    if path.startswith(('audit-evidence/', 'docs/data/', 'docs/reviews/', 'docs/evaluations/')):
        return 'evidence'
    return 'working'

def inventory(root):
    records = []
    for base, dirs, files in os.walk(root, followlinks=False):
        for d in sorted(dirs[:]):
            p = Path(base) / d
            why = ('excluded_dependency_or_generated' if d in SKIP_DIRS else
                   'excluded_private_runtime' if d in PRIVATE_DIRS else
                   'excluded_symlink' if p.is_symlink() else None)
            if why:
                records.append({'path': str(p.relative_to(root)) + '/', 'disposition': why})
                dirs.remove(d)
        dirs.sort()
        for name in sorted(files):
            p = Path(base) / name
            rel = str(p.relative_to(root))
            if p.is_symlink():
                records.append({'path': rel, 'disposition': 'excluded_symlink'}); continue
            if name.startswith('.env') or p.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.sqlite', '.db', '.sqlite3'} or re.search(r'(credentials|secrets|auth\.json|history\.jsonl)', name, re.I):
                records.append({'path': rel, 'disposition': 'excluded_sensitive_or_database'}); continue
            try:
                s = p.stat()
            except OSError as exc:
                records.append({'path': rel, 'disposition': 'unreadable', 'error': str(exc)}); continue
            ext = p.suffix.lower()
            include = ext == '.md' or (ext in {'.txt', '.rst'} and rel.startswith(('docs/company/', 'docs/project/', 'docs/planning/', 'docs/research/')))
            records.append({'path': rel, 'size': s.st_size, 'mtime_ns': s.st_mtime_ns,
                            'disposition': 'snapshot' if include and s.st_size <= MAX_TEXT else 'linked_original',
                            'reason': 'text_document' if include and s.st_size <= MAX_TEXT else 'code_binary_or_bulk_evidence_kept_at_original',
                            'source_role': role(rel)})
    return records

def rewrite_links(text, source, root, mapping):
    # Preserve wording; adapt relative Markdown destinations to the vault or original.
    def replace(m):
        label, dest = m.group(1), m.group(2).strip().strip('<>')
        if not dest or dest.startswith(('#', 'http:', 'https:', 'mailto:', 'data:', 'obsidian:', 'file:')):
            return m.group(0)
        if ' "' in dest:
            dest = dest.split(' "', 1)[0]
        part, _, fragment = dest.partition('#')
        target = (source.parent / unquote(part)).resolve()
        if not target.is_relative_to(root.resolve()):
            return m.group(0)
        rel = str(target.relative_to(root.resolve()))
        # Original anchors remain available at the source; do not guess Obsidian anchors.
        if rel in mapping and not fragment:
            link = wiki(mapping[rel], label)
            line_start = text.rfind('\n', 0, m.start()) + 1
            if text[line_start:m.start()].lstrip().startswith('|'):
                link = link.replace('|', r'\|')
            return link
        return '[' + label + '](' + target.as_uri() + ('#' + fragment if fragment else '') + ')'
    return re.sub(r'(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)', replace, text)

def doc_text(resource):
    parts = []
    def walk(x):
        if isinstance(x, dict):
            if 'textRun' in x:
                run = x['textRun']; content = run.get('content', '')
                url = run.get('textStyle', {}).get('link', {}).get('url')
                parts.append('[' + content.rstrip('\n') + '](' + url + ')' + ('\n' if content.endswith('\n') else '') if url and content.strip() else content)
                return
            if 'table' in x:
                parts.append('\n[Table: cells in source order]\n')
            if 'inlineObjectElement' in x:
                parts.append('\n[Embedded object: inspect original Google Doc]\n')
            for k, v in x.items():
                if k not in {'documentStyle', 'namedStyles', 'lists', 'suggestedNamedStylesChanges', 'inlineObjects', 'positionedObjects'}:
                    walk(v)
        elif isinstance(x, list):
            for a in x: walk(a)
    if resource.get('tabs'):
        for tab in resource['tabs']:
            parts.append('\n## Tab: ' + (tab.get('title') or tab.get('tabProperties', {}).get('title', 'Untitled')) + '\n\n')
            for field in ['body', 'headers', 'footers', 'footnotes']:
                if tab.get(field): walk(tab[field])
    else:
        walk(resource.get('body', resource))
    return ''.join(parts)

def chat_text(data):
    turns, attachments = {}, {}
    for page in data.get('pages', []):
        for t in page.get('turns', []): turns[t['id']] = t
        for a in page.get('attachments', []): attachments[a.get('name', str(a))] = a
    lines, gaps = [], []
    for t in sorted(turns.values(), key=lambda x: x.get('startedAt') or 0):
        date = dt.datetime.fromtimestamp(t['startedAt'], dt.timezone.utc).isoformat() if t.get('startedAt') else 'date unavailable'
        lines.append('\n## Turn ' + t['id'] + '\n\n' + date + '\n')
        for i in t.get('items', []):
            if i.get('type') == 'userMessage':
                text = '\n'.join(c.get('text', '') for c in i.get('content', []) if c.get('type') == 'text')
                who = 'Owner message — historical context'
            elif i.get('type') == 'agentMessage':
                text = i.get('text', ''); who = 'Assistant response — not verified authority'
            else:
                continue
            lines.append('\n### ' + who + '\n\n' + text + '\n')
            if i.get('truncated'): gaps.append('Message truncated by history tool: ' + i.get('id', t['id']))
            if 'contents were not included' in text: gaps.append('Attachment content absent from message text; see attachment inventory.')
            if ':chatgpt-content-reference' in text: gaps.append('Historical citation placeholders require the original conversation to resolve.')
    if attachments:
        lines.append('\n## Attachment inventory\n')
        for name, a in attachments.items():
            p = Path(a.get('path', ''))
            lines.append('- ' + name + (' — materialized during capture; original chat remains authority.' if p.is_file() else ' — attachment bytes unavailable locally.'))
    return '\n'.join(lines), sorted(set(gaps)), list(attachments.values())

class Projection:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve(); self.vault = self.root / VAULT_NAME
        self.system = self.vault / '.knowledge-imports'
        self.state_path = self.system / 'state.json'
        self.state = read_json(self.state_path, {'sources': {}, 'events': []})
        self.records = []; self.counts = collections.Counter()

    def event(self, kind, sid, detail, target=None):
        key = digest(kind + sid + detail)
        if not any(e['key'] == key for e in self.state['events']):
            self.state['events'].append({'key': key, 'kind': kind, 'source_id': sid,
                                         'detail': detail, 'target': target, 'detected_at': stamp()})

    def project(self, rec, content, issues=()):
        sid = rec['source_id']; previous = self.state['sources'].get(sid)
        # Stable output identity even if the title changes.
        path = previous['note'] if previous else rec['note']
        rec['note'] = path
        target = safe_target(self.vault, path)
        source_hash = rec.get('sha256') or digest(content)
        rec['sha256'] = source_hash
        changed = previous and previous['sha256'] != source_hash
        reviewed_at = previous.get('captured_at') if previous and not changed else rec.get('captured_at', stamp())
        rec['captured_at'] = reviewed_at
        clean, redactions = redact(content)
        if redactions:
            issues = [*issues, f'{redactions} credential-shaped values redacted from projection.']
        props = {k: rec[k] for k in ['source_id', 'title', 'source_kind', 'source_role', 'source_location', 'source_modified', 'captured_at', 'sha256'] if k in rec}
        props.update({'type': 'source', 'status': rec.get('status', 'snapshot'), 'fidelity': rec.get('fidelity', 'text_snapshot'),
                      'review_state': 'needs_review' if issues else 'source_not_accepted_by_import', 'generated': True})
        warnings = '\n'.join('- ' + x for x in issues)
        body = frontmatter(props) + '# ' + rec['title'] + '\n\n' + '> [!info] Source copy\n> Refreshable reference, not a new acceptance or instruction. Edit your notes below the personal-notes divider.\n\n'
        body += '[Open original](' + rec['source_location'] + ') · ' + wiki('00 Start/Source authority', 'Authority and freshness') + '\n\n'
        if warnings: body += '> [!warning] Extraction or review limits\n' + '\n'.join('> ' + l for l in warnings.splitlines()) + '\n\n'
        body += clean.rstrip() + '\n'
        expected_hash = digest(body)
        notes = '\n## Your notes\n\n'
        if target.exists():
            old = target.read_text()
            generated, sep, tail = old.partition(MARKER)
            notes = tail if sep else notes
            if not previous or not sep or digest(generated) != previous['generated_sha256']:
                incoming = f'91 Reviews/Incoming/{slug(rec["title"])}--{expected_hash[:12]}.md'
                incoming_path = safe_target(self.vault, incoming)
                if not incoming_path.exists(): atomic(incoming_path, body + MARKER + '\n## Resolution notes\n\n')
                self.event('edited_projection', sid, 'Existing generated content was edited; preserved it and staged an incoming copy.', incoming)
                self.counts['conflicts'] += 1
                if previous:
                    previous['pending_sha256'] = source_hash
                    previous['status'] = 'conflict'
                self.records.append(rec)
                return
            if generated == body:
                self.counts['unchanged'] += 1
            else:
                oldpath = self.system / 'history' / digest(sid)[:16] / (digest(old) + '.md')
                if not oldpath.exists(): atomic(oldpath, old)
                atomic(target, body + MARKER + notes)
                self.counts['updated'] += 1
        else:
            atomic(target, body + MARKER + notes); self.counts['created'] += 1
        if changed:
            self.event('source_changed', sid, 'Source fingerprint changed; dependent summaries need rechecking. Previous projection preserved.', path)
        for issue in issues:
            self.event('source_limit', sid, issue, path)
        self.state['sources'][sid] = {**rec, 'generated_sha256': expected_hash}
        self.records.append(rec)

    def local(self):
        rows = inventory(self.root)
        mapping = {r['path']: note_path('Local', r['path'].replace('/', ' - '), 'local:' + r['path']) for r in rows if r['disposition'] == 'snapshot'}
        for r in rows:
            if r['disposition'] != 'snapshot': continue
            p = self.root / r['path']
            try:
                raw = p.read_bytes(); content = raw.decode('utf-8-sig')
            except (OSError, UnicodeError) as exc:
                r.update(disposition='unreadable_text', error=str(exc)); continue
            r['sha256'] = digest(raw); r['note'] = mapping[r['path']]
            rec = {'source_id': 'local:' + r['path'], 'title': r['path'], 'source_kind': 'local',
                   'source_role': r['source_role'], 'source_location': p.as_uri(), 'note': r['note'],
                   'sha256': r['sha256'], 'source_modified': dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).isoformat(),
                   'status': 'historical' if r['source_role'] == 'historical' else 'snapshot',
                   'fidelity': 'full_text_relative_links_adapted'}
            self.project(rec, rewrite_links(content, p, self.root, mapping))
        dump(self.system / 'local-inventory.json', rows)
        self.inventory = rows

    def connected(self):
        for path in sorted((self.system / 'drive').glob('*.json')):
            d = read_json(path, {}); m = d['metadata']; response = d['response']; sid = 'drive:' + m['id']
            issues = list(d.get('issues', []))
            if d.get('isError'):
                content = 'Content unavailable. ' + json.dumps(response, ensure_ascii=False)
                issues.append('Content read failed; original remains linked. Do not bypass a permission or source STOP.')
            elif d.get('method') == 'native_document':
                content = doc_text(response)
                if not content.strip(): issues.append('No text was extracted from native document structure.')
                if '[Embedded object:' in content: issues.append('Embedded objects require inspection in the original document.')
            else:
                content = response.get('content') or response.get('text') or json.dumps(response, ensure_ascii=False)
                if not isinstance(content, str): content = json.dumps(content, ensure_ascii=False)
                issues.append('Readable extraction only; spreadsheet formulas, comments, layout and embedded media are not a complete archival copy.')
            source_role = 'historical' if re.search(r'superseded|old\.xlsx', m['title'], re.I) else 'working'
            rec = {'source_id': sid, 'title': m['title'], 'source_kind': 'drive', 'source_role': source_role,
                   'source_location': m['url'], 'source_modified': m.get('updated_at'), 'captured_at': d.get('fetched_at'),
                   'note': note_path('Drive', m['title'], sid), 'status': 'unavailable' if d.get('isError') else source_role,
                   'fidelity': d.get('method'), 'sha256': digest(json.dumps(response, ensure_ascii=False, sort_keys=True))}
            self.project(rec, content, issues)
        selection = read_json(self.system / 'chatgpt-selection.json', {})
        for path in sorted((self.system / 'chatgpt').glob('*.json')):
            d = read_json(path, {}); m = d['metadata']; disposition = selection.get(m['id'], {}).get('disposition', 'review_relevance')
            if disposition == 'excluded_unrelated': continue
            sid = 'chatgpt:' + m['id']; content, issues, attachments = chat_text(d)
            if disposition == 'review_relevance': issues.append('Potential context only: relevance to Daylight requires owner review.')
            # Copy only available attachments for selected relevant chats; never fetch guessed URLs.
            for attachment in attachments:
                origin = Path(attachment.get('path', ''))
                if origin.is_file() and not origin.is_symlink():
                    rel = f'90 Sources/ChatGPT Attachments/{m["id"]}/{slug(origin.name)}'
                    dest = safe_target(self.vault, rel)
                    if not dest.exists(): atomic(dest, origin.read_bytes())
                    content += '\n\n' + wiki(rel, attachment.get('name', origin.name)) + '\n'
            rec = {'source_id': sid, 'title': m['title'], 'source_kind': 'chatgpt', 'source_role': 'historical_discussion',
                   'source_location': 'https://chatgpt.com/c/' + m['id'], 'source_modified': m.get('updatedAt'),
                   'captured_at': d.get('fetched_at'), 'note': note_path('ChatGPT', m['title'], sid),
                   'status': disposition, 'fidelity': 'available_conversation_messages', 'sha256': digest(content)}
            self.project(rec, content, issues)

    def reports(self):
        seen = {r['source_id'] for r in self.records}
        for sid, old in self.state['sources'].items():
            if sid not in seen:
                self.event('source_missing', sid, 'Source no longer appears in the configured scan or staged inputs; its note is retained.', old['note'])
                old['status'] = 'missing_from_scan'
        groups = collections.defaultdict(list)
        for rec in self.records: groups[(rec['source_kind'], rec['title'].lower())].append(rec)
        for key, group in groups.items():
            if len(group) > 1:
                self.event('same_title', '|'.join(r['source_id'] for r in group), 'Distinct source IDs share this title: ' + key[1] + '. No authority winner was selected.', group[0]['note'])
        counts = collections.Counter(r['disposition'] for r in self.inventory)
        source_counts = collections.Counter(r['source_kind'] for r in self.records)
        report = '# Source coverage\n\nGenerated by the local refresh command. Full local scope means every discovered path is accounted for; bulk evidence and code remain linked at their original locations. Directory exclusions are recorded as subtrees, not individual-file counts.\n\n'
        report += '| Local disposition | Count |\n|---|---:|\n' + '\n'.join(f'| {k} | {v} |' for k, v in sorted(counts.items()))
        report += '\n\n| Searchable source notes | Count |\n|---|---:|\n' + '\n'.join(f'| {k} | {v} |' for k, v in sorted(source_counts.items()))
        report += '\n\n' + wiki('99 System/Local file catalog', 'Browse linked files and exclusion groups') + '\n\n' + wiki('91 Reviews/Import review queue') + '\n\nThe hidden `.knowledge-imports/local-inventory.json` records exact paths, sizes and dispositions. Source snapshots have content hashes; large linked files have size/time metadata only. The importer does not claim a full byte-integrity audit of bulk databases.\n'
        atomic(self.vault / '99 System/Source coverage.md', report)
        by_area = collections.defaultdict(list)
        for r in self.inventory: by_area[r['path'].split('/')[0]].append(r)
        catalog = '# Local file catalog\n\nOriginal files stay in place. Indexes cover code, evidence and documents.\n\n'
        for area, rows in sorted(by_area.items()):
            rel = '99 System/File catalogs/' + slug(area) + '.md'
            catalog += '- ' + wiki(rel, area) + ' — ' + str(len(rows)) + ' entries\n'
            text = '# ' + area + '\n\n| Original | Disposition | Bytes |\n|---|---|---:|\n'
            for r in rows:
                label = r['path'].replace('|', '\\|')
                text += '| [' + label + '](' + (self.root / r['path']).as_uri() + ') | ' + r['disposition'] + ' | ' + str(r.get('size', '')) + ' |\n'
            atomic(self.vault / rel, text)
        atomic(self.vault / '99 System/Local file catalog.md', catalog)
        queue = '# Import review queue\n\nThis generated index records conflicts, changed sources and extraction limits. Add resolutions in separate review notes; importer history remains intact. ' + wiki('91 Reviews/Owner decisions needed') + '\n\n'
        by_kind = collections.defaultdict(list)
        for e in self.state['events']: by_kind[e['kind']].append(e)
        for kind, events in sorted(by_kind.items()):
            queue += '\n## ' + kind.replace('_', ' ').title() + '\n\n'
            for e in events:
                queue += '- ' + (wiki(e['target']) if e.get('target') else e['source_id']) + ': ' + e['detail'] + '\n'
        if not by_kind: queue += 'No mechanical import conflicts detected. This is not a semantic or acceptance review.\n'
        atomic(self.vault / '91 Reviews/Import review queue.md', queue)
        dump(self.state_path, self.state)
        dump(self.system / 'last-run.json', {'completed_at': stamp(), 'changes': dict(self.counts), 'source_counts': dict(source_counts), 'local_dispositions': dict(counts), 'events': len(self.state['events'])})
        return dict(self.counts)

    def refresh(self):
        self.system.mkdir(parents=True, exist_ok=True)
        with (self.system / 'refresh.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Reload under the lock, so concurrent refreshes never use stale state.
            self.state = read_json(self.state_path, {'sources': {}, 'events': []})
            self.local(); self.connected(); return self.reports()

def backup(root):
    vault = root / VAULT_NAME
    destination = root / 'tmp/obsidian-backups'
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / ('daylight-vault-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.tar.gz')
    paths = [p for p in vault.rglob('*') if p.is_file() and not p.is_symlink() and p.name != 'refresh.lock']
    expected = {str(p.relative_to(vault)): digest(p.read_bytes()) for p in paths}
    with tarfile.open(target, 'w:gz') as archive:
        for p in paths: archive.add(p, arcname=str(p.relative_to(vault)), recursive=False)
    with tarfile.open(target, 'r:gz') as archive:
        actual = {m.name: digest(archive.extractfile(m).read()) for m in archive.getmembers() if m.isfile()}
    if expected != actual: raise RuntimeError('Backup readback failed')
    dump(target.with_suffix('.manifest.json'), {'files': expected, 'verified_at': stamp(), 'archive_sha256': digest(target.read_bytes())})
    return {'archive': str(target), 'files_verified': len(expected)}

def check(root):
    vault = root / VAULT_NAME; state = read_json(vault / '.knowledge-imports/state.json', {'sources': {}})
    errors = []; changed_sources = []; edited = []
    for sid, rec in state['sources'].items():
        p = safe_target(vault, rec['note'])
        if not p.is_file(): errors.append('Missing note: ' + rec['note']); continue
        body, sep, _ = p.read_text().partition(MARKER)
        if not sep or digest(body) != rec['generated_sha256']: edited.append(rec['note'])
        if sid.startswith('local:'):
            origin = root / sid.removeprefix('local:')
            if not origin.is_file() or digest(origin.read_bytes()) != rec['sha256']: changed_sources.append(sid)
    result = {'source_notes': len(state['sources']), 'errors': errors, 'edited_generated_notes': edited, 'local_sources_changed_since_refresh': changed_sources}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors or edited or changed_sources else 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['refresh', 'check', 'backup', 'status'])
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(); root = args.root.resolve()
    if args.command == 'refresh': print(json.dumps(Projection(root).refresh(), indent=2))
    elif args.command == 'backup': print(json.dumps(backup(root), indent=2))
    elif args.command == 'check': return check(root)
    else: print(json.dumps(read_json(root / VAULT_NAME / '.knowledge-imports/last-run.json', {}), indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
