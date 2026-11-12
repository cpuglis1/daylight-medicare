"""Source-named scope keys for schedules, never expected benefit values."""
from __future__ import annotations
import re
from l03_semantic_clauses import clean


def financial_context(name,label='',row=None):
    text=clean(name+' '+label);low=text.lower();row=row or{}
    result={}
    tiers=[(k,v)for k,v in row.items()if re.search(r'(?:^|_)tier(?:_post)?_id$',k)and v not in ['',None]]
    if tiers:result['source_tier']={k:str(v)for k,v in tiers}
    m=re.search(r'rx(?:Insulin)?Tier(\d+)',text,re.I)
    if m:result['source_tier_number']=m.group(1)
    if re.search(r'Insulin|(?:^|_)ira(?:_|\b)',text,re.I):result['drug_scope']='insulin'
    if re.search(r'long.?term.?care|ltcp|LongTermCare',text,re.I):result['pharmacy']='long_term_care'
    elif re.search(r'(?:preferred.*mail|MailOrderPreferred|MailOrder.*Preferred|mopref)',text,re.I):result['pharmacy']='preferred_mail_order'
    elif re.search(r'mail.?order|mostd|MailOrder',text,re.I):result['pharmacy']='standard_or_source_default_mail_order'
    elif re.search(r'preferred.*retail|retpref|PreferredRetail',text,re.I):result['pharmacy']='preferred_retail'
    elif re.search(r'retail|retstd',text,re.I):result['pharmacy']='standard_or_source_default_retail'
    if re.search(r'out.of.network|(?:^|_)oon(?:_|\b)',text,re.I):result['network']='out_of_network'
    words={'one':1,'two':2,'three':3}
    m=re.search(r'(One|Two|Three)Month|\b(one|two|three)[ -]+month|(?:_|\b)([123])m(?:_|\b)|\b([123])[ -]+month',text,re.I)
    if m:
        value=next(x for x in m.groups()if x)
        result['source_supply_months']=words.get(value.lower(),int(value)if value.isdigit()else None)
    if re.search(r'daily|per day|_dly|_day_',text,re.I):result['price_denominator']='day'
    if re.search(r'pre.?icl|Initial Coverage',text,re.I):result['source_phase']='pre_icl'
    elif re.search(r'post.?ootp|post.?oopt|tier_post|catastrophic',text,re.I):result['source_phase']='post_threshold'
    elif re.search(r'deduct',text,re.I):result['source_phase']='deductible'
    return result


def source_question_target(label):
    """Remove cost instrument/endpoint words, preserving the actual target."""
    t=clean(label).lower()
    t=re.sub(r'\b(?:the|minimum|maximum|min|max|copayments?|copays?|coinsurance|percentage|percent|amount|amt|dollar|dollars|rate)\b',' ',t)
    t=re.sub(r'\s+',' ',t).strip(' :-')
    return t or 'source_selected_cost_schedule'


def printed_attribute_headers(text):
    """Retain printed pharmacy/supply headers with exact physical line refs."""
    frames={};active={}
    lines=text.splitlines()
    for n,line in enumerate(lines,1):
        t=clean(line)
        if re.match(r'(?:Section\s+\d|Chapter\s+\d)',t,re.I):active={}
        if not t or re.search(r'\$\s*\d|\d+\s*%',t):
            frames[n]=dict(active);continue
        if len(t)<180 and re.search(r'pharmacy|mail.?order|long.term care|preferred\s*/\s*standard',t,re.I):
            active['preference_header'if re.search(r'preferred\s*/\s*standard',t,re.I)else'pharmacy_header']={'text':t,'line':n}
        if len(t)<180 and re.search(r'\b\d+[ -]month.*supply|\b\d+[ -]day.*supply',t,re.I):
            active['supply_header']={'text':t,'line':n}
        frames[n]=dict(active)
    return frames


def plan_cost_question(pointer,native):
    """Separate selected plan amounts from category membership and controls."""
    leaf=pointer.rsplit('/',1)[-1];low=leaf.lower();context={};role='source_plan_condition';group=pointer
    if 'combined' in low or 'combin' in low or low.startswith('comb'):context['network']='combined_source_basis'
    elif any(x in low for x in ['outofnw','outofnetwork','oon']):context['network']='out_of_network'
    elif any(x in low for x in ['nonnetwork','nonnet','nonnw']):context['network']='non_network_source_basis'
    elif any(x in low for x in ['innetwork','innw','inn']):context['network']='in_network'
    member=re.search(r'/(medicareServices|nonMedicareServices)/(\d+)/',pointer)
    if member:
        base=pointer[:member.end()-1];base=base.rsplit('/',1)[0]if not base[-1].isdigit()else base
        # The array item, not its first field value, names its service category.
        root=pointer[:pointer.index('/'+member.group(1))]+'/'+member.group(1)+'/'+member.group(2)
        obj=native
        for part in root.split('/')[1:]:obj=obj[int(part)]if isinstance(obj,list)else obj[part]
        if 'combined'in low:context['source_budget_scope']='combined'
        if 'outofnetwork'in low:context['network']='out_of_network'
        elif 'innetwork'in low:context['network']='in_network'
        context['category_code']=obj.get('categoryCode');context['category_type']=member.group(1)
        context['membership_question']=leaf
        return group,role,context
    if '/planDeductibleDetails/'in pointer and re.match(r'(?:has)?(?:inNetwork|combined|outOfNetwork|nonNetwork)',leaf,re.I)and not re.search(r'CovBen|Slct|Chk',leaf,re.I):
        budget=context.get('network','source_named_network')
        group=pointer.rsplit('/',1)[0]+'/deductible_schedule/'+budget;role='published_plan_schedule'
    elif '/maxEnrolleeCostLimitDetails/'in pointer and re.match(r'(?:type)?(?:inNWMoop|outOfNWMoop|combinedMoop|nonNWMoop)(?:Amount)?$',leaf,re.I):
        budget=context.get('network','source_named_network')
        group=pointer.rsplit('/',1)[0]+'/MOOP_schedule/'+budget;role='published_plan_schedule'
    elif re.search(r'(?:Amt|Amount)$',leaf)and not re.search(r'YesNo|NumOf',leaf,re.I):
        role='published_plan_schedule'
    return group,role,context


def pharmacy_column_questions(text):
    """Enumerate printed pharmacy columns without assigning their prices.

    The exact multi-line header and physical column anchors are retained. This
    identifies required questions; normalization/value binding remains held.
    """
    lines=text.splitlines();result=[]
    for n,line in enumerate(lines):
        days=list(re.finditer(r"\b\d+[ -]day\b",line,re.I))
        nearby=' '.join(lines[max(0,n-6):n+3])
        if len(days)>=2 and re.search(r"days?\s+supply|supply\s+length",line,re.I)and re.search(r"retail|mail|pharmacy|LTC",nearby,re.I):
            return [{'source_pharmacy_column':i,'printed_label':m.group(),'header_line':n+1,
                     'header_anchor_character':m.start(),'complete_header':nearby}for i,m in enumerate(days,1)]
    for n,line in enumerate(lines):
        matches=list(re.finditer(r'Preferred|Standard|Long[- ]term|Out[- ]of[- ]',line,re.I))
        nearby=' '.join(lines[max(0,n-3):n+6])
        if len(matches)<2 or not re.search(r'retail|mail|pharmacy|LTC',nearby,re.I):continue
        if re.search(r'\$\s*\d|\d+\s*%',line):continue
        for column,match in enumerate(matches,1):
            result.append({'source_pharmacy_column':column,'printed_label':match.group(),'header_line':n+1,
                           'header_anchor_character':match.start(),'complete_header':nearby})
        break
    return result


def pharmacy_table_rows(text):
    """Physical tier/cost-sharing rows, with exact observed start lines."""
    lines=text.splitlines();starts={};active=None;frames={}
    future_label=None;last_label=None;has_cost=False;left_edge=None
    for n,line in enumerate(lines,1):
        t=clean(line);indent=len(line)-len(line.lstrip())
        tier=re.match(r"(?:cost[- ]sharing\s+)?tier\s*(\d+)\b",t,re.I)
        cost_start=bool(re.match(r"Cost[- ]Sharing\b",t,re.I)and re.search(r"\$|\d+\s*%",t))
        money=bool(re.search(r"\$|\d+\s*%",t))
        if tier and re.match(r"(?:is|are|may|will|can)\b",t[tier.end():].strip(),re.I):tier=None
        # A wrapped sentence such as "available for drugs in / Tier 1."
        # appears inside a cost cell, to the right of the tier-label column.
        if tier and active and left_edge is not None and indent>left_edge+4 and n!=future_label:tier=None
        if cost_start and active and not has_cost and last_label and n-last_label<=3:
            has_cost=True;tier=None
        elif cost_start:
            candidate=None
            for offset,following in enumerate(lines[n-1:n+3]):
                candidate=re.search(r"\btier\s*(\d+)\b",following,re.I)
                if candidate:future_label=n+offset;break
            if candidate:
                active='Published pharmacy table row: Tier '+candidate.group(1)
                starts[n]=active;has_cost=True;left_edge=indent if left_edge is None else min(left_edge,indent)
            tier=None
        elif tier:
            last_label=n
            if n!=future_label:
                active='Published pharmacy table row: Tier '+tier.group(1)
                starts[n]=active;has_cost=money;left_edge=indent if left_edge is None else min(left_edge,indent)
        elif active and indent<=(left_edge or 0)+4 and re.match(r"(?:You|We|Our plan|For |If |When |Section |Retail|Mail|Insulin cost|Standard retail)",t,re.I):
            active=None;has_cost=False
        if active:frames[n]=active
    return frames,starts


def pharmacy_columns_by_line(text):
    """Bind each table to its own repeated header on the same page."""
    lines=text.splitlines();events={}
    for n,line in enumerate(lines):
        if re.search(r"\$\s*\d|\d+\s*%",line):continue
        matches=list(re.finditer(r"Preferred|Standard|Long[- ]term|Out[- ]of[- ]",line,re.I))
        if len(matches)>=2 and re.search(r"retail|mail|pharmacy|LTC",' '.join(lines[max(0,n-3):n+6]),re.I):
            events[n+1]=[{'source_pharmacy_column':i,'printed_label':m.group(),'header_line':n+1,'header_anchor_character':m.start(),'complete_header':' '.join(lines[max(0,n-3):n+6])}for i,m in enumerate(matches,1)]
        days=list(re.finditer(r"\b\d+[ -]day\b",line,re.I))
        if len(days)>=2 and re.search(r"days?\s+supply|supply\s+length",line,re.I):
            events[n+1]=[{'source_pharmacy_column':i,'printed_label':m.group(),'header_line':n+1,'header_anchor_character':m.start(),'complete_header':' '.join(lines[max(0,n-6):n+3])}for i,m in enumerate(days,1)]
    active=[];frames={}
    for n in range(1,len(lines)+1):
        if n in events:active=events[n]
        frames[n]=active
    return frames
