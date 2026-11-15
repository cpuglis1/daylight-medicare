"""Legacy offline transport for historical regressions, never production routing.
This approximates old scripted fixtures; it is not evidence of model understanding.
New D173 cases supply semantic outputs explicitly, without this recognizer.
"""
import re
from conversation_planner import empty_proposal, UNREAL, NEGATED, LEARNING, PRODUCTS
import conversation_tasks

def _legacy_hint(message):
    """Fallback for missing/malformed interpreter metadata; never a choice."""
    out = empty_proposal()
    text = message[:600]
    if '?' in message or LEARNING.search(message) or re.match(r'\s*(?:why|how|what|which|when|where|is|does|can|could|should|would|do)\b', message, re.I):
        out.update(question_quote=text, purpose='understand', quote=text)
    if re.search(r'\b(?:timing|sign[ -]?up|part [ab].*prepar\w*|a and b.*start\w*|enroll.*part [ab])\b', message, re.I):
        out['focus'] = 'enrollment'
    elif re.search(r'\b(?:two .*paths|both (?:paths|options)|advantage.*medigap|medigap.*advantage|original.*advantage|advantage.*original)\b', message, re.I):
        out['focus'] = 'coverage_paths'
    elif re.search(r'\boriginal medicare\b', message, re.I) and not PRODUCTS['medigap'].search(message):
        out['focus'] = 'original'
    else:
        out['focus'] = next((k for k, p in PRODUCTS.items() if p.search(message)), '')
        if not out['focus'] and re.search(r'\b(?:options|paths)\b', message, re.I):
            out['focus'] = 'coverage_paths'
    drug_cost = bool(re.search(r'\b(?:cost\w*|cheap\w*|price\w*|pay|order)\b', message, re.I)
                    and re.search(r'\b(?:medicine\w*|drug\w*|prescription\w*|pharmacy)\b', message, re.I))
    if (not UNREAL.search(message) and not NEGATED.search(message)
            and (re.search(r'\b(?:prices?|pricing|premiums?|quotes?|how much)\b', message, re.I)
                 or drug_cost or re.search(r'\b(?:show|see|find|compare|review|look at)\b.{0,50}\b(?:plans?|options|advantage)\b', message, re.I))):
        inv = [k for k in ('medigap', 'advantage', 'part_d') if PRODUCTS[k].search(message)]
        # A held supplement is context for separate drug research, not a
        # request to price that supplement again.
        if drug_cost and 'part_d' in inv and re.search(r'\bkeep\w*\b.{0,20}\b(?:plan g|medigap|supplement)\b', message, re.I):
            inv = [k for k in inv if k != 'medigap']
        if re.search(r'\bboth (?:paths|options)\b', message, re.I):
            inv = ['medigap', 'advantage', 'part_d']
        out.update(purpose='investigate', quote=text, investigate=inv, request_quote=text)
        if drug_cost:
            out['investigate'] = list(dict.fromkeys(inv + ['medicines']))
    if (re.search(r'(?:^\s*(?:please )?|\b(?:can|could|would) you )(?:check|compare|research)\b.{0,35}\b(?:doctors?|medicines?)\b', message, re.I)
            and not UNREAL.search(message) and not NEGATED.search(message)):
        inv = [k for k in ('doctors', 'medicines') if PRODUCTS[k].search(message)]
        out.update(purpose='investigate', quote=text, investigate=inv, request_quote=text)
    if (out['focus'] == 'enrollment' and not UNREAL.search(message)
            and not re.search(r"\b(?:not ready|don['’]?t want|do not want|later|just explain)\b", message, re.I)
            and re.search(r'\b(?:settle|work (?:out|through)|figure out|sort out|coordinate|help (?:me|us) (?:with|enroll)|start with|focus on)\b', message, re.I)):
        out.update(purpose='problem', quote=text, question_quote=text)
    clauses = re.split(r'(?<=[.!?])\s+|;', message)
    if len(clauses) > 1:
        # A negative factual report elsewhere must not cancel an explicit
        # investigation request (e.g. “Compare 2027. I don't want old plans”).
        requests = [_legacy_hint(clause) for clause in clauses if clause.strip()]
        explicit = [p for p in requests if p['purpose'] == 'investigate' and p['investigate']]
        if explicit:
            latest = explicit[-1]
            out.update(purpose='investigate', investigate=latest['investigate'],
                       request_quote=latest['request_quote'], quote=latest['quote'])
    return out


def bind_guidance(p, text, prior=None):
    prior = prior or {}
    if p.get('guidance', {}).get('quote'): return p
    from journey_completion import request
    mode = 'discuss'
    task = {'enrollment':'timing','doctors':'providers','medicines':'drug_coverage',
            'medigap':'medigap','part_d':'drug_pricing','advantage':'advantage','costs':'costs'}.get(p['focus'],'compare')
    products=set(p.get('investigate',[])) & {'medigap','part_d','advantage'}
    if p['purpose']=='investigate' and len(products)==1:
        task={'medigap':'medigap','part_d':'drug_pricing','advantage':'advantage'}[next(iter(products))]
    elif len(products)>1: task='compare'
    if p['purpose'] in ('investigate','problem','review','compare'): mode='work'
    if p['purpose']=='none' and prior.get('active_task'):
        mode,task='work',prior['active_task']
    if p['purpose']=='understand' and prior.get('active_task'): mode='detour'
    if p.get('decision',{}).get('stance') in ('chosen','leaning') and not p.get('investigate'): mode='discuss'
    if re.search(r'education only|just want to understand|not ready to give personal|skip personal details|not asked for a quote',text,re.I): mode='discuss'
    finish=request(text)
    if finish:
        mode='finish'
        if finish in ('keep_current','wait'):
            p['decision']=dict(stance='chosen',path=finish,quote=text)
    p['guidance']=dict(mode=mode,task=task if mode in ('work','suggest') else '',
        checks=['payer_order','job_loss','drug_gap','coverage_change'] if task=='timing' else [],
        quote=text[:600],finish=finish or '')
    return p


def scripted_proposal(text, prior=None):
    return bind_guidance(_legacy_hint(text),text,prior)
