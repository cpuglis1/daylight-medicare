"""Local plain-text visible conversation logs, explicitly requested by the owner.

Logs never become model context and never contain API payloads or hidden reasoning.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import threading
import uuid

import cms_slice as cms

DEFAULT_DIR = cms.ROOT / 'reports/conversations'
WELCOME = "Hi, I'm Daylight Medicare, an automated guide to Medicare in Naples. I can explain how Medicare works or help you look through 2027 plans. I'm not a person or an insurance agent, and I'll never ask for ID numbers. How familiar are you with Medicare so far?"


def conversation_id(value=None):
    if value is None:
        return str(uuid.uuid4())
    if not isinstance(value,str) or len(value)!=36:
        raise cms.SourceError('Invalid conversation identifier')
    try:
        parsed=uuid.UUID(value)
    except ValueError:
        raise cms.SourceError('Invalid conversation identifier') from None
    if str(parsed)!=value:
        raise cms.SourceError('Invalid conversation identifier')
    return value


def redact(value):
    text=str(value)
    key=os.environ.get('OPENAI_API_KEY')
    if key:text=text.replace(key,'[API key redacted]')
    return re.sub(r'\bsk-[A-Za-z0-9_-]{8,}', '[API key redacted]',text)


def visible_text(result):
    lines=[]
    if result.get('text'):lines.append(result['text'])
    if result.get('question'):lines.append(result['question'])
    if result.get('error'):lines.append('Error: '+result['error'])
    for fact in result.get('facts',[]):
        lines.append('Cited source fact: '+fact['text'])
        evidence=fact.get('evidence',[])
        if isinstance(evidence,dict):evidence=[evidence]
        for source in evidence:
            url=source.get('requested_url') or source.get('url')
            if url:lines.append('Source: '+url)
    views=result.get('catalogs',[]) or ([result] if result.get('kind') in {'catalog','comparison','plan'} else [])
    for view in views:
        lines.extend([view.get('title','Published plans'),view.get('ordering',''),view.get('cost_scope','')])
        for plan in view.get('plans',[]):
            values=[]
            for name,metric in plan.get('metrics',{}).items():
                amount=f"${metric['value_cents']/100:,.2f}" if metric['state']=='value' else metric['state'].replace('_',' ')
                values.append(name.replace('_',' ')+': '+amount)
            lines.append(f"{plan['name']} ({plan['id']}; {plan['category']}): "+'; '.join(values))
            lines.extend(plan.get('notes',[]))
    for kind,candidates in result.get('choices',{}).items():
        for candidate in candidates:
            lines.append('Choice — '+kind+': '+str(candidate.get('synonym') or candidate.get('name') or candidate.get('organization') or candidate.get('npi','')))
    quick=result.get('quick_replies',result.get('suggestions',[]))
    if quick:lines.append('Quick replies: '+' | '.join(quick))
    return '\n'.join(line for line in lines if line)


class TranscriptLog:
    def __init__(self,directory=DEFAULT_DIR):
        self.directory=Path(directory)
        self.lock=threading.Lock()

    def append(self,identifier,message=None,result=None,starter_question=None,opening=False):
        identifier=conversation_id(identifier)
        with self.lock:
            self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.chmod(self.directory,0o700)
            path=self.directory/(identifier+'.txt')
            flags=os.O_WRONLY|os.O_APPEND|os.O_CREAT|getattr(os,'O_NOFOLLOW',0)
            descriptor=os.open(path,flags,0o600)
            with os.fdopen(descriptor,'a',encoding='utf-8') as handle:
                os.fchmod(handle.fileno(),0o600)
                created=os.fstat(handle.fileno()).st_size==0
                if created:
                    handle.write('Daylight Medicare conversation\nConversation: '+identifier+'\nStarted (UTC): '+datetime.now(timezone.utc).isoformat()+'\n')
                if opening or (created and starter_question is None):
                    handle.write('\nDaylight Medicare (local welcome):\n  '+WELCOME+'\n')
                if starter_question is not None:
                    handle.write('\n['+datetime.now(timezone.utc).isoformat()+']\nDaylight Medicare (starter question):\n  '+redact(starter_question).replace('\n','\n  ')+'\n')
                if message is not None:
                    handle.write('\n['+datetime.now(timezone.utc).isoformat()+']\nUser:\n  '+redact(message or '[No message]').replace('\n','\n  ')+'\n')
                if result is not None:
                    handle.write('Daylight Medicare:\n  '+redact(visible_text(result)).replace('\n','\n  ')+'\n')
                handle.flush()
                os.fsync(handle.fileno())
        return path
