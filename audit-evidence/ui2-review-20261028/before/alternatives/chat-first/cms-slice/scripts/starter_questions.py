"""Original starter questions and validation for the local answer log."""
import re
import cms_slice as cms
from conversation import PROFILE


def starter_answer(field,value,recipient='self'):
    if not isinstance(field,str) or field not in {'recipient','zip','medicare','timing','drugs','hearing','vision','dental'}:
        raise cms.SourceError('Unknown starter question')
    if not isinstance(recipient,str) or recipient not in {'self','someone'} or not isinstance(value,str):
        raise cms.SourceError('Invalid starter answer')
    if field=='zip':
        if not re.fullmatch(r'\d{5}',value):raise cms.SourceError('Enter a five-digit ZIP code')
    elif value not in PROFILE[field]:
        raise cms.SourceError('Invalid starter answer')
    other=recipient=='someone'
    subject='they' if other else 'you'
    questions={
        'recipient':'Who are we looking at coverage for?',
        'zip':'What’s their ZIP code?' if other else 'What’s your ZIP code?',
        'medicare':f'Do {subject} have Medicare coverage?',
        'timing':f'When might {subject} need coverage?',
        'drugs':f'Do {subject} need prescription drug coverage?',
        'hearing':f'Do {subject} want hearing benefits?',
        'vision':f'Do {subject} want vision benefits?',
        'dental':f'Do {subject} want dental benefits?',
    }
    labels={'self':'Myself','someone':'Someone else','yes':'Yes','no':'No','unsure':'I’m not sure','soon':'Within the next 3 months','later':'Later on'}
    return questions[field],labels.get(value,value)
