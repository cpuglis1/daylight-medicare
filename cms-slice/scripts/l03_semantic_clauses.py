"""Source-faithful proposition segmentation for the L03 inventory milestone.

This module inventories assertions; it does not verify benefit amounts or make
personal coverage decisions. Every proposition retains its exact source span.
"""
from __future__ import annotations

import re
import unicodedata

VERSION = "l03-semantic-clauses/2"
FAMILIES = {
    "authorization": r"prior authori[sz]|preauthori[sz]|precertif|authorization (?:is |may be |must be |requirements)|authori[sz]ation required",
    "referral": r"referral|referred by|refer you|refer you to",
    "deductible": r"deductible",
    "network_setting": r"in.network|out.of.network|network provider|network pharmacy|approved provider|participating provider|non.participating|provider.*(?:must|need|only)|(?:only|must).*provider|office setting|nursing home|FQHC|federally qualified|ambulatory surgical",
    "frequency_quantity": r"\bonce\b(?=\W*(?:$|[.!?,])|\s+(?:every|per|a\b|each|in\b|annually|monthly))|\btwice\b|every (?:\d+|one|two|three|four|six|year|month)|per (?:calendar |benefit )?(?:year|month|quarter)|\b\d+\s+(?:visits|trips|pairs|sessions|treatments|hours|units)|frequency|quantity|(?<!not )limited to|no more than|up to|not exceed|carry.over|carried over|roll.?over|expire|expires|reset",
    "day_bands": r"\b(?:days?[ -]+\d|\d+[ -]+days?|per (?:day|stay)|benefit period|reserve days)",
    "shared_allowance": r"shared|combined|allowance|wallet|maximum|budget|plan payment limit",
    "qualification": r"eligible|eligibility|qualif|medical necessity|medically necessary|Medicaid|\bQMB\b|chronic|diagnos|prescrib|order(?:ed)? by|under.*supervision|beneficiary|low.income|\bif\b|\bonly\b|\bunless\b|subject to|must|need to|required|participating in|high risk|provided that|creditable|entitled|responsible.*(?:pay|cost|charge|expense)|liable|owe",
    "exclusion": r"not cover|aren.t covered|isn.t covered|doesn.t cover|don.t cover|not included|excluded|exclusion|not eligible|not available|not pay|do not pay for|no coverage",
    "waiver_replacement": r"waiv|except|replac|instead|in lieu|rather than|doesn.t apply|does not apply|don.t apply|do not apply",
}
MONEY = re.compile(r"\$\s*\d|\d+(?:\.\d+)?\s*%|\b(?:copayment|copay|coinsurance|premium|deductible|cost.sharing|allowance|wallet|spending limit|no charge|no cost)\b", re.I)
VERB = re.compile(r"\b(?:is|are|was|were|be|covers?|covered|pays?|paying|provides?|provided|includes?|included|excludes?|excluded|receives?|received|requires?|required|applies|apply|counts?|counted|can|cannot|may|must|will|won.t|does|doesn.t|don.t|do|have|has|need|needs|get|gets|qualify|qualifies|lets?|allows?|offer|offers|limits?|limited|eligible|available|depends?|aren.t|isn.t|can.t|could|should|consists?|involves?|means?|defined|measured?)\b", re.I)
ADMIN_REQUEST = re.compile(r"^(?:please\s+)?(?:call|contact|visit|write|mail|fax|email|send|go to|check|ask|read|see|refer to|look|use the (?:phone|website)|tell us|let us know|keep|carry|show|bring)\b", re.I)
MATERIAL = re.compile(r"\b(?:covered|covers?|coverage|benefits?|copay|copayment|coinsurance|deductible|premium|pays?|paying|costs?|allowance|limits?|authorization|referral|eligible|qualify|medically necessary|not included|excluded|waived|reimbursement|repayment|refund|liability|liable|charges?|expenses?|owe)\b|\$\s*\d|\d+\s*%", re.I)
IMMEDIATE_CONDITION = re.compile(r"prior authori|preauthor|precertif|referral|required before|must.*before|only if|must.*network|must.*provider|medically necessary|not covered|won.t pay|doesn.t pay|we (?:cover|pay)|our plan (?:covers|pays)|you (?:will |must )?pay|\$\s*\d|\d+\s*%", re.I)

CHAPTER_RULES = [
    ("medical_benefits", r"medical benefits chart|medical benefits.*cost|what.s covered and what you pay"),
    ("medical_access", r"using.*plan.*medical|using.*medical.*services|using.*covered services"),
    ("drug_costs", r"what.*pay.*part d|part d.*cost"),
    ("drug_coverage", r"using.*part d.*drugs|prescription drug coverage"),
    ("contacts", r"phone numbers|important phone|important.*resources"),
    ("appeals", r"problem or complaint|coverage decisions.*appeals|appeals.*complaint"),
    ("rights", r"rights and responsibilities"),
    ("termination", r"ending.*membership|membership.*end|disenroll"),
    ("legal", r"legal notices"),
    ("definitions", r"definitions|important words"),
    ("payment_procedure", r"asking us to pay|pay our share.*bill|pay.*bill.*covered"),
    ("introduction", r"get started|getting started|welcome|introduction|member.*plan"),
]


def clean(text):
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"’":"'", "‘":"'", "–":"-", "—":"-", "‑":"-", "\u00ad":""}))
    return re.sub(r"\s+", " ", text).strip()


def page_context(text, previous=None, kind="EOC"):
    lines = text.splitlines()
    front = " ".join(clean(l) for l in lines[:10])
    context = dict(previous or {})
    if re.search(r"table\s+of\s+contents", front, re.I):
        return {"chapter_role":"contents", "chapter_title":"Table of Contents", "chapter_number":None}
    # Only a printed chapter heading in the page front can establish a chapter;
    # cross-references in the body do not move source context.
    headings = []
    for i,line in enumerate(lines[:10]):
        m = re.match(r"\s*Chapter\s+(\d+)\s*[:.]?\s*(.*)", line, re.I)
        if m:
            title = clean(m.group(2))
            if len(title) < 5:
                title = clean(" ".join(lines[i+1:i+4]))
            headings.append((int(m.group(1)), title))
    for number,title in headings:
        role = next((name for name,pattern in CHAPTER_RULES if re.search(pattern,title,re.I)),None)
        if role:
            context.update(chapter_number=number, chapter_title=title, chapter_role=role)
            break
    if context.get("chapter_role") == "contents":
        context = {}
    if not context:
        context = {"chapter_role":"summary" if kind=="SB" else "supplemental" if kind=="supplemental" else "front_matter",
                   "chapter_title":"Source front matter" if kind=="EOC" else kind, "chapter_number":None}
    return context


def normalize_with_offsets(text):
    """Whitespace-only projection; original punctuation/characters are kept."""
    chars = []; offsets = []; in_space = True
    for index,char in enumerate(text):
        if char.isspace():
            if not in_space:
                chars.append(" "); offsets.append(index)
            in_space = True
        else:
            chars.append(char); offsets.append(index); in_space=False
    if chars and chars[-1] == " ":
        chars.pop(); offsets.pop()
    return "".join(chars), offsets


def sentence_spans(text):
    """Split source sentences/semicolons without splitting decimals/US names."""
    starts = [0]
    for match in re.finditer(r"[.!?;](?:\s+|$)", text):
        punctuation = match.start()
        prefix = text[max(0,punctuation-12):punctuation+1]
        if text[punctuation] == "." and re.search(r"(?:\b(?:Dr|Mr|Mrs|Ms|St|Inc|e\.g|i\.e|U\.S)|\b[A-Z]|a\.m|p\.m)\.$", prefix):
            if not (prefix.endswith("U.S.")and re.match(r"(?:You|We|Our|The plan)\b",text[match.end():])):
                continue
        starts.append(match.end())
    starts.append(len(text))
    for a,b in zip(starts,starts[1:]):
        while a < b and text[a].isspace():a+=1
        while b > a and text[b-1].isspace():b-=1
        if a < b:yield a,b


def independent_clause_spans(text, start, end):
    """Split independent coordinated/conditional assertions; keep noun sets.

    Remaining conjunctions are recorded as explicit logical groups rather than
    silently turning alternative services into separately chargeable benefits.
    """
    value = text[start:end]
    boundaries = []
    # Some pinned OCR renders a printed bullet as "e" or "e." inline.
    # Split only before an unmistakable new finite plan/member assertion.
    for match in re.finditer(r"\s+[e•●▪]\.?\s*(?=(?:our plan|we|you)\s+(?:can.t|cannot|covers?|pay|must|will|may|have|need)\b)",value,re.I):
        if len(value[:match.start()].strip())>12:
            boundaries.append((start+match.start(),start+match.end(),"printed_list_next_assertion"))
    pattern = re.compile(r",?\s+\b(?:and|but|however|except that|unless|provided that|only if|if|when)\s+", re.I)
    for match in pattern.finditer(value):
        left,right=value[:match.start()],value[match.end():]
        connector=clean(match.group()).strip(", ").lower()
        new_subject = re.match(r"(?:you|we|our plan|the plan|they|it|these services|this benefit|Medicare|your provider)\b",right,re.I)
        new_amount = re.match(r"\$\s*\d|\d+(?:\.\d+)?\s*%",right)
        conditional = connector in {"unless","provided that","only if","if","when","except that"}
        if len(left.strip())>12 and ((new_subject and VERB.search(right)) or new_amount or (conditional and len(right.strip())>8)):
            boundaries.append((start+match.start(),start+match.end(),connector))
    for match in re.finditer(r"\s+(?=(?:We|You|Our plan|The plan)\s+(?:cover|pay|must|need|can|will|have|offer|provide|require|get|are)\b)",value):
        if len(value[:match.start()].strip())>12 and not re.search(r"[.!?:]\s*$",value[:match.start()]):
            boundaries.append((start+match.start(),start+match.end(),"next_assertion"))
    if re.match(r"(?:If|When|Once|Unless|After|Before)\b",value):
        for match in re.finditer(r",\s+",value):
            right=value[match.end():]
            if re.match(r"(?:you|we|our plan|the plan|[A-Z][A-Za-z -]{1,55})\s+(?:will|may|must|can|is|are|have|has|cover|pay)\b",right,re.I):
                boundaries.append((start+match.start(),start+match.end(),"conditional_main_assertion"));break
    for match in re.finditer(r"(?:,\s+|\s+(?:and|or)\s+)(?=(?:have|has|are|is|must|need to)\b)",value,re.I):
        connector="or"if re.search(r"\bor\b",match.group(),re.I)else"and"
        if len(value[:match.start()].strip())>12:boundaries.append((start+match.start(),start+match.end(),connector))
    boundaries=sorted(set(boundaries))
    position=start; relation="assertion"
    for a,b,connector in boundaries:
        if position<a:
            yield position,a,relation
        position=b;relation=connector
    if position<end:yield position,end,relation


def line_units(text):
    """Yield paragraphs, headings and list items with original char bounds."""
    lines=text.splitlines(keepends=True);positions=[0]
    for line in lines:positions.append(positions[-1]+len(line))
    start=None;start_type="prose";i=0
    while i<len(lines):
        line=lines[i];position=positions[i]
        content=line.rstrip("\r\n")
        stripped=content.strip()
        bullet=bool(re.match(r"\s*(?:[•●▪◦*¢]|e\s+(?=[A-Z])|e(?=[A-Z])|[-–—]\s|\(?\d+[.)]\s|[a-z][.)]\s)",content))
        heading=bool(re.match(r"\s*(?:Chapter\s+\d|Section\s+\d|Table\s+of\s+Contents)",content,re.I) or
                     re.fullmatch(r"\s*(?:Covered\s+Services?|What\s+you\s+pay|In.network\s+Out.of.network)[\s:|]*",content,re.I))
        identity=bool(re.match(r"\s*(?:2026\s+Evidence\s+of\s+Coverage|2026\s+Summary\s+of\s+Benefits|Y\d{4}[_ ]|©)",content,re.I))
        if not stripped or bullet or heading or identity:
            if start is not None and start<position:
                yield start,position,start_type
            start=None
            if stripped:
                start=position;start_type="list_item"if bullet else"prose"
                if heading or identity:
                    end=i+1
                    match=re.match(r"\s*(?:Section\s+[\d.]+|Chapter\s+\d+)\s*[:.]?\s+(.+)",content,re.I)
                    if match:
                        title_start=match.start(1)
                        while end<min(len(lines),i+3):
                            following=lines[end].rstrip("\r\n");indent=len(following)-len(following.lstrip())
                            if following.strip()and title_start>=25 and abs(indent-title_start)<=4 and not re.match(r"\s*[•●▪◦*¢]|\s*(?:You|We|Our|The)\b",following):end+=1
                            else:break
                    yield position,positions[end]-len(lines[end-1])+len(lines[end-1].rstrip("\r\n")),"heading"
                    start=None;i=end;continue
        elif start is None:
            start=position;start_type="prose"
        i+=1
    if start is not None and start<positions[-1]:yield start,positions[-1],start_type


def classify(text, context, *, unit_type="prose", relation="assertion", subject=""):
    """Return a source assertion role with an inspectable semantic rule.

    A retained administrative clause must have a specific rule. Medical source
    assertions are required even when their comparison attributes are unknown.
    """
    t=clean(text).strip(" •●▪◦*-")
    low=t.lower(); role=context.get("chapter_role","")
    if not t:return "retained_layout","empty_layout",[]
    if role=="contents":return "retained_structure","printed_contents_entry",[]
    if re.fullmatch(r"[\d\W_]+",t):return "retained_layout","page_number_or_rule",[]
    if unit_type=="heading":return "retained_structure","printed_section_or_column_header",[]
    if t.endswith("?") and re.match(r"^(?:what|how|which|when|where|who|why|do|does|can|is|are)\b",t,re.I):
        return "retained_structure","printed_source_question",[]
    if re.fullmatch(r"(?:(?:covered services?|what you pay|in.network|out.of.network|network providers?|non.network providers?|providers?|continued|\(continued\)|medical benefits chart)\s*[:|()/ -]*\s*)+",t,re.I):
        return "retained_structure","printed_table_column_or_continuation_label",[]
    if len(t)<220 and re.match(r"^(?:2026\s+)?(?:Evidence of Coverage|Summary of Benefits)(?:\s+for|$)|^Chapter\s+\d+\b|^Y\d{4}[_ ]|^H\d{4}[-_ ]\d{3}|^©",t,re.I):
        return "retained_structure","document_identity_or_repeated_header",[]
    if re.search(r"when this (?:evidence of coverage|document|booklet).*says.*means|when it says.*(?:plan|our plan).*means",t,re.I):
        return "retained_structure","document_pronoun_identity_definition",[]
    if re.search(r"benefits.*(?:premium|deductible|copayment).*may change on January 1,? 2027",t,re.I):
        return "retained_administration","next_year_change_notice_not_2026_benefit",[]
    if re.fullmatch(r"(?:\S+@\S+|(?:https?://|www\.)\S+|[+()\d\s.\-/]+|TTY\s*\d+)",t,re.I):
        return "retained_administration","contact_locator",[]
    if context.get("list_mode")=="document_outline" and not VERB.search(t):
        return "retained_structure","document_outline_list_member",[]
    if re.match(r"^(?:A |An |The )?(?:coverage decision|appeal|grievance|complaint|organization determination)\s+(?:is|means|refers)\b",t,re.I):
        return "retained_administration","defined_administrative_procedure",[]
    if role=="definitions" and re.match(r"^(?:Appeal|Grievance|Complaint|Coverage Decision|Enrollment Period|Election Period|Disenrollment)\b",t,re.I):
        return "retained_administration","named_procedural_definition",[]
    if re.search(r"(?:toll.free|TTY|customer service|member services|call).*\b(?:a\.m\.|p\.m\.|days? a week|oct.mar|apr.sept)|(?:hours are|M-F Apr-Sept|this call is free|the call is free)|^\(?[^A-Za-z]*This is an important legal document",t,re.I) and not re.search(r"prior author|referral|\$|coinsurance|copay|deductible|benefit limit|not covered",t,re.I):
        return "retained_administration","contact_hours_or_free_contact_call",[]
    if re.search(r"(?:this apple|apple (?:symbol|icon)|symbol (?:shows|indicates))",t,re.I)and not re.search(r"no cost|no charge|copay|coinsurance|deductible|not covered",t,re.I):
        return "retained_structure","printed_legend_symbol_definition",[]
    if re.fullmatch(r"(?:Covered services?|Benefits?|Services we cover|Coverage)\s+(?:include|includes|are|is)(?:,? but (?:are not|aren.t|is not|isn.t) limited to)?\s*:",t,re.I):
        return "retained_structure","explicit_benefit_or_condition_list_introducer",[]
    parent=clean(context.get("logical_parent",t))
    if re.match(r"(?:for example|here.s an example|example\s*\d*[:.]|as an example)\b",parent,re.I)and re.search(r"\$|copay|cost.sharing|coinsurance",parent,re.I):
        return "retained_structure","hypothetical_worked_cost_example",[]
    if re.match(r"(?:for (?:more )?(?:details|information)|to (?:find out|learn more|check)|this (?:helps|will ensure|ensures)|claim forms can be found)\b",t,re.I)and not re.search(r"prior author|referral|only if|must.*before|not covered|\$|\d+\s*%",t,re.I):
        return "retained_administration","source_navigation_or_fulfillment_instruction",[]
    families=[name for name,pattern in FAMILIES.items()if re.search(pattern,t,re.I)]
    if re.search(r"(?:this (?:booklet|chapter|section|document)|the following (?:chapter|section)|see (?:chapter|section)|refer to (?:chapter|section)).*(?:explain|describe|list|tell|detail|information)",t,re.I) and not IMMEDIATE_CONDITION.search(t):
        return "retained_structure","source_navigation_description",[]
    if ADMIN_REQUEST.match(t) and not re.search(r"prior author|preauthor|referral|required before|must.*before|only if|(?:must|need).*network|not covered|\$\s*\d|\d+\s*%",t,re.I):
        return "retained_administration","contact_or_reading_instruction",[]
    if re.search(r"alternate format|large print|braille|audio format|language assistance|interpreter|discrimina|civil rights|protected health|privacy|HIPAA|personal (?:health|medical) information",t,re.I) and not IMMEDIATE_CONDITION.search(t):
        return "retained_administration","communication_privacy_or_civil_rights",[]
    if role in {"appeals","rights","termination","contacts","payment_procedure"}:
        procedural=re.search(r"appeal|complaint|grievance|coverage decision|reconsider|organization determination|hearing|request|notice|enroll|disenroll|membership|telephone|phone|representative|address|write|bill|payment request|reimburse",t,re.I)
        direct_benefit=re.search(r"we (?:don.t |do not |will |won.t )?(?:cover|pay for)|our plan (?:covers|doesn.t cover)|you (?:will |must )?pay (?:a |an |\$|\d)|(?:services|care|treatment).*not covered|medically necessary|prior authori|network provider|covered days|benefit limit|\$\s*\d|\d+\s*%",t,re.I)
        benefit_terms=re.search(r"deductible|premium|coinsurance|copay|cost.sharing|benefit limit|not covered|coverage (?:ends|continues|starts)|covered (?:services|care|days)|medically necessary|prior author|referral|creditable|full cost|our share|your share|reimburse|refund|charges?|expenses?",t,re.I)
        if not direct_benefit and not benefit_terms:
            return "retained_administration","membership_contact_appeal_or_claims_procedure",[]
    if role=="definitions" and re.search(r"appeal|grievance|complaint|administrative law|enrollment period|election period|disenroll|privacy|Social Security|State Health Insurance Assistance",t,re.I) and not IMMEDIATE_CONDITION.search(t):
        return "retained_administration","procedural_or_other_layer_definition",[]
    if role in {"contacts","introduction","rights","termination","appeals","payment_procedure","legal","front_matter"}and not MATERIAL.search(t)and not IMMEDIATE_CONDITION.search(t):
        return "retained_administration","nonbenefit_plan_membership_or_document_context",[]
    if role=="legal" and re.search(r"legal notice|governing law|federal law|applicable law|nondiscrimination|civil rights|copyright",t,re.I) and not MATERIAL.search(t):
        return "retained_administration","legal_governance_notice",[]
    if re.search(r"OMB (?:approval|control)|paperwork reduction|^(?:this document|this booklet).*(?:written|published|printed|prepared).*in (?:English|Spanish)|^(?:Medicare|CMS).*(?:approve our plan|plan.*contract renewal)",t,re.I) and not IMMEDIATE_CONDITION.search(t):
        return "retained_administration","publication_and_contract_notice",[]
    if re.fullmatch(r"(?:yes|no|none|covered|not covered|unlimited|not applicable|n/a)[.!]?",t,re.I):
        return "claim","explicit_source_coverage_or_limit_selection",families
    if context.get("list_mode")=="condition" and unit_type=="list_item" and not VERB.search(t):
        return "condition","named_member_of_explicit_condition_list",families or ["qualification"]
    if context.get("list_mode")=="coverage" and unit_type=="list_item" and not VERB.search(t):
        return "claim","named_member_of_explicit_covered_service_list",families
    if relation in {"if","when","unless","provided that","only if","except that"}:
        return "condition","explicit_conditional_clause",families or ["qualification"]
    if re.match(r"^(?:If|When|Unless|Before|After|Once)\b",t,re.I)and not (low.startswith("once")and"frequency_quantity"in families):
        return "condition","explicit_introductory_qualification",sorted(set(families+["qualification"]))
    if families and (any(x in families for x in ["authorization","referral","qualification","exclusion","waiver_replacement"]) or not VERB.search(t)):
        return "condition","published_material_restriction_or_qualification",families
    if MONEY.search(t):return "claim","published_cost_allowance_or_limit_assertion",families
    if role=="definitions":return "claim","source_defined_term",families
    if VERB.search(t)and (MATERIAL.search(t)or families or re.search(r"means|defined|consists|involves|includes",t,re.I)):
        return "claim","source_coverage_access_or_benefit_assertion",families
    if VERB.search(t):return "retained_structure","nonmaterial_explanation_or_service_navigation",[]
    if unit_type=="list_item"and role in {"medical_benefits","medical_access","drug_costs","drug_coverage","summary","supplemental"}and len(t)>4:
        return "condition","explicit_published_list_member_with_source_intro_scope",families or["source_list_membership"]
    if role in {"medical_benefits","medical_access","drug_costs","drug_coverage","summary","supplemental"}and len(t)>4:
        return "retained_structure","named_service_subtype_setting_or_source_label",[]
    return "retained_structure","source_title_label_or_index_context",[]


def decompose(text, context, *, subject=""):
    result=[]
    context=dict(context)
    resets=iter(sorted(context.pop("scope_resets",[])));next_reset=next(resets,None)
    for a,b,unit_type in line_units(text):
        # An introducer governs its immediately following list, not every
        # later list in the chapter. Intervening prose/heading ends that scope.
        if unit_type!='list_item':
            context.pop('list_mode',None);context.pop('list_intro',None)
        while next_reset is not None and next_reset<=a:
            context.pop("list_mode",None);context.pop("list_intro",None)
            next_reset=next(resets,None)
        value,offsets=normalize_with_offsets(text[a:b])
        if not value:continue
        spans=[(0,len(value))]if unit_type=="heading"else list(sentence_spans(value))
        for begin,end in spans:
            pieces=[(begin,end,"assertion")]if unit_type=="heading"else list(independent_clause_spans(value,begin,end))
            for c,d,relation in pieces:
                while c<d and value[c].isspace():c+=1
                while d>c and value[d-1].isspace():d-=1
                if c>=d:continue
                quote=value[c:d]
                kind,rule,families=classify(quote,{**context,"logical_parent":value[begin:end]},unit_type=unit_type,relation=relation,subject=subject)
                intro=context.get("list_intro")if unit_type=="list_item"else None
                if intro and kind in {"claim","condition"}:
                    inherited=[name for name,pattern in FAMILIES.items()if re.search(pattern,intro["quote"],re.I)]
                    families=sorted(set(families+inherited))
                result.append({"quote":quote,"kind":kind,"rule":rule,"condition_families":families,
                    "relation":relation,"unit_type":unit_type,"start":a+offsets[c],"end":a+offsets[d-1]+1,
                    "parent_sentence":value[begin:end],"parent_start":a+offsets[begin],"parent_end":a+offsets[end-1]+1,
                    "list_intro":intro,
                    "logical_connectives":[m.group().lower()for m in re.finditer(r"\b(?:and|or|unless|except|if|when)\b",quote,re.I)]})
        # A paragraph can end with a new list introducer after unrelated
        # sentences. Only that sentence governs the following list.
        intro_start=spans[-1][0]
        intro_value=value[intro_start:]
        intro_record={"quote":intro_value,"start":a+offsets[intro_start],"end":a+offsets[-1]+1}
        if re.search(r"(?:covered services?|benefits?|services? we cover|coverage)\s+(?:include|includes|are|is)(?:,? but (?:are not|aren.t|is not|isn.t) limited to)?\s*:\s*$",intro_value,re.I):
            context["list_mode"]="coverage"
            context["list_intro"]=intro_record
        elif re.search(r"(?:conditions?|requirements?|exceptions?|limitations?|following circumstances|following criteria|depend.*following|depends.*factors).*:\s*$",intro_value,re.I):
            context["list_mode"]="condition"
            context["list_intro"]=intro_record
        elif re.search(r"(?:deductible|authorization|referral|limit|waiver|exception).*following.*:\s*$",intro_value,re.I):
            context["list_mode"]="condition"
            context["list_intro"]=intro_record
        elif intro_value.endswith(":")and re.search(r"not covered|excluded|must|need|qualif|eligible|restrictions?|following services",intro_value,re.I):
            context["list_mode"]="condition"
            context["list_intro"]=intro_record
        elif re.search(r"(?:use this (?:document|booklet)|this (?:document|booklet)).*(?:understand|contents|sections).*:\s*$",value,re.I):
            context["list_mode"]="document_outline"
        elif unit_type=="heading" and re.match(r"Section\s+\d",value,re.I):
            context.pop("list_mode",None);context.pop("list_intro",None)
    return result


def inherited_list_context(current_lines, line_start, previous_lines=(), column_end=None):
    """Only an explicit preceding list introducer supplies list semantics."""
    prior=list(previous_lines[-18:])+list(current_lines[:max(0,line_start-1)])
    for line in reversed(prior[-24:]):
        value=clean(line[:column_end]if column_end else line)
        if re.match(r"Section\s+\d",value,re.I):return {}
        if re.search(r"(?:deductible|authorization|referral|limit|waiver|exception).*following.*:\s*$",value,re.I):
            return {"list_mode":"condition"}
        if re.search(r"(?:conditions?|requirements?|exceptions?|limitations?|following circumstances|following criteria|depend.*following|depends.*factors).*:\s*$",value,re.I):
            return {"list_mode":"condition"}
        if re.search(r"(?:covered services?|benefits?|services? we cover|coverage)\s+(?:include|includes|are|is)(?:,? but (?:are not|aren.t|is not|isn.t) limited to)?\s*:\s*$",value,re.I):
            return {"list_mode":"coverage"}
        if re.search(r"use this (?:document|booklet).*understand.*:\s*$",value,re.I):
            return {"list_mode":"document_outline"}
    return {}


def detect_table_columns(text):
    lines=text.splitlines();chosen=None
    for n,line in enumerate(lines[:30]):
        if re.match(r"\s*(?:Chapter|2026\s+Evidence)",line,re.I):continue
        matches=list(re.finditer(r"What\s+you\s+pay",line,re.I))
        if matches and all(m.start()>25 for m in matches) and (
                len(matches)>1 or re.search(r"covered\s+service|services.*covered",line[:matches[0].start()],re.I)):
            chosen=(n,matches);break
    if chosen is None:
        for n,line in enumerate(lines[:25]):
            labels=list(re.finditer(r"(?<![A-Za-z])(?:In[- ]network|Out[- ]of[- ]network)(?![A-Za-z])",line,re.I))
            remainder=re.sub(r"(?:In[- ]network|Out[- ]of[- ]network)","",line,flags=re.I).strip(" |: ")
            if len(labels)==2 and not remainder:
                chosen=(n,labels);break
    if chosen is None:return {"boundaries":[],"roles":[],"evidence":[]}
    n,matches=chosen;boundaries=[];roles=[]
    body=[l for l in lines[n+2:]if l.strip()and not re.match(r"\s*(?:Chapter|2026\s+Evidence)",l,re.I)]
    for i,match in enumerate(matches):
        start=match.start()
        candidates=range(max(25,start-14),start+1)if start>=25 else range(0,start+1)
        scores={x:sum(bool(len(l)>x and not l[x].isspace())for l in body)for x in candidates}
        best=min(scores.values())
        minima=[x for x in candidates if scores[x]==best]
        # Use the centre of the blank gutter rather than cutting at the label's
        # first character; OCR row starts can shift a few characters.
        boundary=(minima[0]+minima[-1]+1)//2
        if boundaries and boundary<=boundaries[-1]:return {"boundaries":[],"roles":[],"evidence":[]}
        boundaries.append(boundary)
        end=matches[i+1].start()if i+1<len(matches)else max(len(l)for l in lines[n:n+3])
        label=clean(" ".join(l[start:end]for l in lines[n:n+3]))
        if re.fullmatch(r"(?:In[- ]network|Out[- ]of[- ]network)",match.group(),re.I):label=match.group()
        label=re.sub(r"-\s+","-",label)
        role="out_of_network"if re.search(r"out.of.network",label,re.I)else"in_network"if re.search(r"in.network",label,re.I)else"source_cost_column"
        roles.append(role)
    evidence=[{"line":n+1,"text":lines[n]}]
    if n+1<len(lines):
        following=clean(lines[n+1])
        remainder=re.sub(r"in[- ]?network|out[- ]of[- ]network|network|providers?|covered services?|services covered|what you pay|[|:/()-]","",following,flags=re.I).strip()
        if not remainder:evidence.append({"line":n+2,"text":lines[n+1]})
    return {"boundaries":boundaries,"roles":roles,"evidence":evidence}



def source_cells(text, column_end=None, column_roles=None, line_boundaries=None):
    """Project an observed two-column table into separate source streams.

    The split is supplied by a retained printed header; it never follows an
    expected CMS amount. Offsets preserve the original source-unit character.
    Unknown/absent column bounds keep a single source stream and its context.
    """
    boundaries=column_end if isinstance(column_end,list)else[column_end]if column_end else[]
    if not boundaries or boundaries[0]<25:
        return [{"column":"source_text","text":text,"offsets":list(range(len(text)))}]
    names=["service_column"]+[f"cost_column_{i+1}:{role}"for i,role in enumerate(column_roles or["source_cost_column"]*len(boundaries))]
    streams={name:([],[])for name in names+["page_structure","spanning_source_note"]}
    position=0;spanning_note=False
    original_lines=text.splitlines(keepends=True)
    for line_number,line in enumerate(original_lines,1):
        body=line.rstrip("\r\n")
        if re.match(r"\s*(?:2026\s+Evidence\s+of\s+Coverage|Chapter\s+\d|Y\d{4}[_ ]|©)",body,re.I):
            chars,offsets=streams["page_structure"]
            chars.extend(body);offsets.extend(range(position,position+len(body)))
            if len(line)>len(body):
                chars.append("\n");offsets.append(position+len(body))
            position+=len(line)
            continue
        if re.search(r"If\s+you\s+are\s+a\s+Qualified\s+Medicare\s+Beneficiary|^\s*[*†‡]+\s*(?:Prior authorization|Referral|If you|These services)",body,re.I):
            spanning_note=True
        if not body.strip():
            spanning_note=False
            for name in names:
                chars,offsets=streams[name]
                if chars and len(line)>len(body):
                    chars.append("\n");offsets.append(position+len(body))
            position+=len(line)
            continue
        if spanning_note or (not line_boundaries and len(body)>boundaries[0] and body[:boundaries[0]].strip() and not re.search(r"\s{2,}",body[max(0,boundaries[0]-4):boundaries[0]+5])):
            chars,offsets=streams["spanning_source_note"]
            chars.extend(body);offsets.extend(range(position,position+len(body)))
            if len(line)>len(body):chars.append("\n");offsets.append(position+len(body))
            position+=len(line);continue
        cuts=[0]
        for cut in (line_boundaries or{}).get(line_number,boundaries):
            cut=min(cut,len(body))
            if 0<cut<len(body)and not body[cut-1].isspace()and not body[cut].isspace():
                spaces=[x for x in range(max(cuts[-1],cut-4),min(len(body),cut+5))if body[x].isspace()]
                if spaces:cut=min(spaces,key=lambda x:abs(x-cut))
            cuts.append(cut)
        cuts.append(len(body))
        for name,a,b in zip(names,cuts,cuts[1:]):
            chars,offsets=streams[name]
            segment=body[a:b]
            if segment.strip():
                chars.extend(segment);offsets.extend(range(position+a,position+b))
                if len(line)>len(body):
                    chars.append("\n");offsets.append(position+len(body))
        position+=len(line)
    result=[]
    for name,(chars,offsets)in streams.items():
        if chars:
            result.append({"column":name,"text":"".join(chars),"offsets":offsets})
    return result


def required_propositions(atom):
    """Project a source clause to a claim and individual condition predicates.

    Each predicate keeps the complete quotation and logical parent. A frequency
    and an authorization in one sentence are distinct obligations, not an
    aggregate "conditions checked" flag. No numerical meaning is inferred.
    """
    if atom["kind"] not in {"claim", "condition"}:
        return []
    result=[]
    if atom["kind"]=="claim" or MONEY.search(atom["quote"]):
        result.append(("claim", "published_assertion"))
    families=atom["condition_families"]
    for family in families:
        result.append(("condition", family))
    if atom["kind"]=="condition" and not families:
        result.append(("condition", "source_explicit_condition"))
    return result


def sb_row_frames(text, geometry):
    """Name financial rows from printed labels; preserve both network questions.

    This inventories each explicitly printed network. It never binds an amount
    to a network from a merged cell; that assignment stays a later comparison
    obligation with the entire source row retained.
    """
    frames={};current=None
    if not geometry["boundaries"]:return frames
    for n,line in enumerate(text.splitlines(),1):
        amount=re.search(r"\$\s*\d|\b\d+(?:\.\d+)?\s*%",line)
        if amount:
            label=clean(line[:amount.start()]).strip(" |: ")
            if 3<len(label)<160 and re.search(r"[A-Z]",label[:3])and not VERB.search(label)and not re.match(r"(?:Section|Chapter|2026|Note|If|When|For example)\b",label,re.I):
                current=label
        if current:frames[n]=current
    return frames
