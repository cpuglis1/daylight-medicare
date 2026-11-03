"""Deterministic reply screening; never asks another model to grade a reply."""
from decimal import Decimal, InvalidOperation
import re

WORDS={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
BANNED=re.compile(r'\bbest plan for (?:you|your|her|him|them)\b|\byou should enroll\b|\bi (?:recommend|would recommend)\b',re.I)

def numbers(text):
    values=set()
    for token in re.findall(r'(?<!\w)\d+(?:,\d{3})*(?:\.\d+)?(?!\w)',text):
        try:values.add(str(Decimal(token.replace(',','')).normalize()))
        except InvalidOperation:pass
    for word in re.findall(r'\b(?:'+ '|'.join(WORDS) +r')\b',text.casefold()):values.add(str(Decimal(WORDS[word]).normalize()))
    return values

def validate_reply(value,facts):
    reply=value['reply'];question=value['question'];text=reply+' '+question
    if '?' in reply or question.count('?')>1:raise ValueError('Use only one question, in question.')
    if question.strip() and not question.strip().endswith('?'):raise ValueError('Use a single question or leave question empty.')
    if re.search(r'\b(?:just|only) (?:the )?(?:first|top) (?:few|\d+)\b',text,re.I):raise ValueError('Do not offer a hidden shortlist; all results must stay reachable.')
    if BANNED.search(text):raise ValueError('Recommendation phrasing is not allowed.')
    if re.search(r"\b(?:you|your (?:mom|dad|mother|father|spouse|parent))\s+(?:(?:are|is|would be)\s+(?:eligible|ineligible)|(?:do |does |don't |doesn't |do not |does not )?qualif(?:y|ies))\b",text,re.I):
        raise ValueError('Personal eligibility must remain undetermined.')
    evidence=' '.join(facts[fid]['text'] for fid in value['fact_ids'])
    # Ordinary discourse such as 'one step at a time' is not a numeric claim.
    claim_text=re.sub(r'\bone (?:step|question|thing|at a time)\b','',text,flags=re.I)
    if re.search(r'\b(?:Original Medicare|Medigap|Medicare Supplement|Medicare Advantage|Part [ABD])\s+(?:is|are|covers?|includes?|helps?|works?|replaces?|means?)\b',text,re.I) and not value['fact_ids']:
        raise ValueError('Coverage explanations need cited facts from this turn.')
    if numbers(claim_text)-numbers(evidence):raise ValueError('Numbers must be present in cited facts from this turn.')
    return text

def detail_requested(message,state):
    return state.get('pace')=='explain' or bool(re.search(r'more (?:depth|detail)|in depth|in-depth|explain.{0,15}(?:more|fully)|detailed|thorough',message,re.I))
