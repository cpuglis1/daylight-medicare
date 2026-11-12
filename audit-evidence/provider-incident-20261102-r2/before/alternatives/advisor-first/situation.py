"""Reported circumstances, kept distinct from coverage and eligibility.

Two additive profile observations; no new required intake question or policy rule.
Only explicit, scoped words may populate these fields. Never supply a missing year.
"""
import re

MONTHS = 'january february march april may june july august september october november december'.split()
FIELDS = {'retirement':'situation.retirement', 'age65':'situation.age65'}
RELATIVE = r'mother|father|mom|dad|parent|spouse|wife|husband'

def _circumstance_subject(text,position):
    """Find the stated subject of this observation, within its sentence.

    A possessive insurance relationship ("my wife's job") is not a new subject
    for an earlier first-person birthday. Coordinated predicates can inherit
    their preceding subject, but a subject from another sentence cannot.
    """
    start=max([text.rfind(mark,0,position) for mark in '.!?;\n'])+1
    sentence=text[start:]
    subject=re.compile(r"\bI\b|\bmy(?=\s+(?:65th\s+birthday|retirement)\b)|\bmy\s+(?:"+RELATIVE+r")(?=\s+(?:is|has|was|will|turns?|retir(?:ed|ing))\b|'s\s+(?:65th\s+birthday|retirement)\b)",re.I)
    matches=[match for match in subject.finditer(sentence) if match.start()<=position-start]
    if not matches:return None
    named=re.match(r'(?i)my\s+('+RELATIVE+r')\b',matches[-1].group())
    return named[1].lower() if named else 'self'

def observations(message, role=None):
    text=message.replace('’',"'")
    if re.search(r'\b(?:if|suppose|hypothetically|for example)\b',text,re.I):return {}
    candidates=[]
    patterns=[
        ('working',r"\bI(?:'m| am)\s+(?:still )?working\b|\bI(?:'m| am)\s+not retired\b"),
        ('retired',r"\b(?:I(?:'ve| have) been|I(?:'m| am)|my (?:"+RELATIVE+r") (?:has been|is))\s+(?:already\s+)?retired\b(?:\s+(for\s+(?:(?:a|an|few|several|many|couple|of|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+){0,5}(?:years?|months?)))?"),
        ('past',r'\bI retired\b(?:\s+((?:in|since)\s+(?:19|20)\d{2}|(?:(?:a|few|several|many|couple|of|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+){1,5}(?:years?|months?)\s+ago))?'),
        ('retiring',r"\b(?:I(?:'m| am)|my (?:"+RELATIVE+r") is)\s+retiring\b")]
    for kind,pattern in patterns:
        for match in re.finditer(pattern,text,re.I):
            actor=_circumstance_subject(text,match.start())
            when=(match[1] or '') if kind in {'retired','past'} else ''
            candidates.append(('retirement',{'status':'retired' if kind=='past' else kind,'when':when},actor))
    age_pattern=r'\b(?:turn(?:ing|s)?\s+65|65th\s+birthday)(?:\s+(?:is|will be))?\s+(?:in|on|this)\s+('+ '|'.join(MONTHS)+r')(?:\s+((?:19|20)\d{2}))?\b'
    for match in re.finditer(age_pattern,text,re.I):
        actor=_circumstance_subject(text,match.start())
        # Preserve a subjectless follow-on fragment such as "I'm retired.
        # Turning 65 in November." only when the reported circumstance already
        # names one subject and no other person has been introduced.
        if actor is None:
            sentence_start=max([text.rfind(mark,0,match.start()) for mark in '.!?;\n'])+1
            fragment=text[sentence_start:match.start()].strip().lower()
            prior={item[2] for item in candidates if item[2] is not None}
            relatives=set(re.findall(r'\bmy\s+('+RELATIVE+r')\b',text,re.I))
            first_person=bool(re.search(r'\bI\b',text,re.I))
            if fragment in {'','and','also'} and len(prior)==1:
                sole=next(iter(prior))
                if (sole=='self' and not relatives or sole!='self' and not first_person and {x.lower() for x in relatives}=={sole}):
                    actor=sole
        candidates.append(('age65',{'month':MONTHS.index(match[1].lower())+1,'year':int(match[2]) if match[2] else None},actor))
    # An explicitly named beneficiary takes precedence over a helper's own life
    # details. Otherwise mixed observed subjects remain unresolved. Mere spouse
    # mentions in insurance clauses do not participate in this test.
    helper=re.search(r"\b(?:(?:this|it)\s+(?:is|'s)\s+for|I(?:'m| am)\s+helping|help(?:ing)?\s+for)\s+my\s+("+RELATIVE+r')\b',text,re.I)
    target=helper[1].lower() if helper else 'self' if role=='self' else None
    if helper and role=='self':return {}
    candidates=[item for item in candidates if item[2] is not None
                and (item[2]==target if target else item[2]!='self' if role=='someone' else True)]
    if len({item[2] for item in candidates})>1:return {}
    result={}
    for kind,value,_ in candidates:result.setdefault(kind,value)
    return result

def timing_request(message):
    return bool(re.search(r'\bturn(?:ing|s)?\s+65\b|\b65th birthday\b|\bretiring\b|\btransition\b|\b(?:insurance|coverage|job)\b.{0,35}\b(?:end|ends|ending|ended)\b|\b(?:when|timing|enroll|sign up|start)\b.{0,45}\bmedicare\b',message,re.I))

def soonest_start_supported(quote, active=None):
    """Recognize support for a desired-start preference, never a calendar date.

    The model selects the report and its exact supporting span. A brief answer
    can inherit the active desired-start question; an unsolicited statement must
    identify the coverage preference itself. Urgent help or a job ending soon
    does not establish when the person wants Medicare to start.
    """
    if not isinstance(quote, str):return False
    text=quote.replace('’',"'").strip().lower()
    urgent=r'(?:asap|as soon as (?:possible|i can)|(?:the )?(?:earliest|soonest)(?: possible)?|right away|immediately)'
    if not re.search(r'\b'+urgent+r'\b',text):return False
    if re.search(r'\b(?:if|suppose|hypothetically|for example|maybe|might|probably|not sure)\b',text):return False
    if re.search(r"\b(?:don't|do not|doesn't|does not|no longer)\s+(?:want|need|prefer|hope)|\bnot\s+"+urgent+r'\b',text):return False
    if '?' in text:return False
    asked=bool(active and active.get('id')=='T04')
    if asked and re.fullmatch(r'(?:please\s+)?'+urgent+r'[.!\s]*',text):return True
    return bool(re.search(r'\b(?:medicare|coverage|insurance)\b',text)
        and re.search(r"\b(?:want|need|prefer|like|hope|hoping|start|begin)\b",text)
        and not re.search(r'\b(?:job|employment|insurance|coverage)\b.{0,25}\b(?:ends?|ending)\b',text))

def supported_choice(id, choice, quote, active=None):
    """Extra checks for the consequential categorical confusions in this incident.

The model still interprets language; these guards reject known unsupported leaps.
Other 41-question meanings remain covered by their existing contracts/validators.
"""
    text=quote.replace('’',"'").lower()
    if id=='T04' and choice=='soonest':return soonest_start_supported(quote,active)
    if id not in {'T02','T05','RC09','RC04','RC06'}:return True
    if id=='T02':
        # Process progress is not Medicare knowledge. A scoped familiarity answer
        # can be short; an unsolicited report must actually concern knowledge.
        return bool(re.search(r'\b(?:know|understand|familiar|knowledge|basics|learn|learning|new to medicare|comfortable with medicare)\b',text)
            or active and active.get('id')=='T02' and re.search(r'\b(?:new|beginner|some|little|comfortable)\b',text))
    if id=='RC06' and choice=='age65':return bool(re.search(r'\b65\b|\bsixty.five\b',text))
    if id=='RC04':
        if choice in {'unknown','deferred'}:return True
        asked=bool(active and active.get('id')=='RC04' and '?' not in text)
        parta=bool(re.search(r'\bparts?\s+a\b|\ba\s+(?:and|&)\s+b\b',text))
        partb=bool(re.search(r'\bparts?\s+b\b|\ba\s+(?:and|&)\s+b\b',text))
        if choice=='pending':
            return bool(not re.search(r"\b(?:haven't|have not|hasn't|has not|not|never)\s+(?:yet\s+)?applied\b|\b(?:waiting|plan|planning|going)\s+to\s+apply\b",text)
                and re.search(r'\b(?:applied|application (?:is )?(?:pending|submitted)|waiting for (?:approval|a decision|my (?:medicare )?card))\b',text))
        if choice=='neither':
            return bool(asked and re.fullmatch(r'(?:neither|none|not yet)[.!]?',text.strip())
                or re.search(r"\b(?:do not|don't|does not|doesn't)\s+have\s+(?:any\s+)?(?:medicare|(?:either\s+)?parts?\s+[ab])\b|\b(?:no|neither)\s+(?:medicare|parts?\s+[ab])\b|\bnot\s+(?:currently\s+)?(?:enrolled|covered)\s+(?:in|by|under)\s+medicare\b",text))
        ownership=bool(re.search(r'\b(?:have|has|enrolled in|covered (?:by|under)|receiv(?:e|es))\s+(?:(?:both|medicare)\s+)?(?:parts?\s+[ab]|a\s+(?:and|&)\s+b)\b|\b(?:already|currently) enrolled\b',text))
        current=bool(asked or ownership)
        if re.search(r'\b(?:applied|applying|plan to|planning to|will enroll|want|hope)\b',text) and not ownership:return False
        if choice=='both':return bool(current and (parta and partb or asked and re.fullmatch(r'both[.!]?',text.strip())))
        if choice=='a_only':return bool(current and parta and (asked or re.search(r"\bonly\b|\b(?:not|no|without)\s+(?:part\s+)?b\b|\bdon't have part b\b",text)))
        if choice=='b_only':return bool(current and partb and (asked or re.search(r"\bonly\b|\b(?:not|no|without)\s+(?:part\s+)?a\b|\bdon't have part a\b",text)))
        return False
    choices=choice.split(',')
    # A short answer can inherit an explicitly asked employment relationship.
    # A broad current-insurance question does not establish that relationship.
    contextual_job=bool(active and active.get('id')=='RC09'
        and re.search(r'\bwhose\b.{0,35}\b(?:job|work|employment|employer)\b',active.get('question',''),re.I)
        and '?' not in text and not re.search(r'\b(?:not|retired|former|used to|cobra|retiree|maybe|might|think|probably)\b',text))
    for value in choices:
        if value in {'unknown','deferred'}:continue
        term={'retiree':'retiree','cobra':'cobra','original':'original medicare','advantage':'medicare advantage','medigap':'medigap'}.get(value)
        if term and re.search(r"\b(?:no|not|don.t have|do not have)\s+(?:(?:any|current)\s+)?"+term+r'\b',text):return False
        if value=='retiree':
            if not re.search(r'\b(?:insurance|coverage|health plan|health benefits|covers? me)\b',text):return False
            if not re.search(r'\bretiree\b|\bformer employer\b|\bold employer\b|\bretirement (?:insurance|coverage|health)',text):return False
            if not re.search(r'\b(?:my|our|have|get|covered|covers)\b',text) and not (active and active.get('id') in {'T05','RC09'} and '?' not in text):return False
        if value in {'employer','my_job','spouse_job','family_job'}:
            if not re.search(r'\b(?:insurance|coverage|health plan|health benefits|covers? me)\b',text) and not (active and active.get('id') in {'T05','RC09'}):return False
            if not contextual_job and not re.search(r'\b(?:current job|work|working|employer|job|employment)\b',text):return False
        if value=='my_job' and not re.search(r"\bmy (?:own )?(?:current )?(?:job|employer)\b|\bthrough work\b|\bI(?:'m| am) (?:still )?working\b|\bI work\b",quote,re.I):return False
        if value=='spouse_job' and not re.search(r'\b(?:spouse|wife|husband)\b',text):return False
        if value=='family_job' and not re.search(r'\b(?:family|parent|mother|father|partner)\b',text):return False
        if value=='original' and not re.search(r'\boriginal medicare\b',text):return False
        if value=='advantage' and not re.search(r'\b(?:advantage|part c)\b',text):return False
        if value=='medigap' and not re.search(r'\b(?:medigap|supplement)\b',text):return False
        if value=='cobra' and 'cobra' not in text:return False
        if value=='none' and not re.search(r'\buninsured\b|\bno (?:health )?(?:insurance|coverage)\b|\b(?:don.t|do not) have (?:any |health )?(?:insurance|coverage)\b',text):return False
    return True

def describe(kind,value):
    if kind=='retirement':
        return {'retired':'Retired','retiring':'Planning to retire','working':'Working'}[value['status']]+(' '+value['when'] if value.get('when') else '')
    return 'Turning 65 in '+MONTHS[value['month']-1].title()+(' '+str(value['year']) if value.get('year') else ' (year not stated)')

def summary(guide):
    values={kind:guide['fields'].get(field,{}).get('value') for kind,field in FIELDS.items()}
    pieces=[]
    if values['retirement']:pieces.append(describe('retirement',values['retirement']).lower())
    if values['age65']:
        birthday=describe('age65',values['age65']).replace(' (year not stated)','')
        pieces.append(birthday[0].lower()+birthday[1:])
    if not pieces:return ''
    subject='The person you’re helping is' if guide['fields'].get('subject.role',{}).get('value')=='someone' else 'You’re'
    if subject=='You’re' and values['retirement'] and values['retirement']['status']=='retired' and values['retirement'].get('when','').startswith('for '):
        lead='You’ve been '+pieces[0]
        return lead+(' and are '+pieces[1] if len(pieces)>1 else '')+'.'
    return subject+' '+ ' and '.join(pieces)+'.'
