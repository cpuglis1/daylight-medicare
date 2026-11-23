"""Keep generated dialogue and citations; omit prepared explanation blocks."""


def generated_conversation(out):
    advisor = out.setdefault('advisor', {})
    sources = list(advisor.get('sources', []))
    for fact in out.get('facts', []):
        links = ([{'url': fact['source'], 'label': fact.get('title', 'Source')}]
                 if fact.get('source') else []) + fact.get('sources', [])
        for link in links:
            if link.get('url') and all(item.get('url') != link['url'] for item in sources):
                sources.append(link)
    advisor.update(visual='none', sources=sources)
    out['facts'] = []
    out.pop('understanding', None)
    if out.get('generated', {}).get('status') != 'complete' and advisor.get('reason') not in {'recovery', 'tool_result'}:
        # Owner exception to D88 (November 8, 2026): a failed generation may show
        # one reviewed statement (advisor.reason == 'recovery') instead of silence.
        out['reply'] = ''
        advisor['teachingFactIds'] = []
        advisor['educationFollowups'] = []
    return out
