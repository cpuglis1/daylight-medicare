"""Requested local transcripts: full visible turns, private files, no credentials."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest
import uuid
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cms_slice as cms
from transcript_log import TranscriptLog,conversation_id
from chat import Chat,ResponsesClient
from demo_tools import DemoTools
from research_http import make_research_test_server as make_server


class TranscriptTests(unittest.TestCase):
    def test_append_is_one_private_file_and_excludes_hidden_fields_and_keys(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'OPENAI_API_KEY':'sk-fake-private-test-key'}):
            log=TranscriptLog(Path(temp)/'conversations');identifier=conversation_id()
            log.append(identifier)
            path=log.append(identifier,'Hello sk-fake-private-test-key',{'text':'Hello.','question':'How can I help?','hidden_reasoning':'never write this','state_update':{'reason':'never write this either'}})
            log.append(identifier,'Keep it brief.',{'text':'Of course.'})
            text=path.read_text()
            self.assertEqual(len(list(log.directory.glob('*.txt'))),1)
            self.assertEqual(text.count('Daylight Medicare (local welcome)'),1)
            self.assertIn('Keep it brief.',text);self.assertIn('Of course.',text)
            self.assertNotIn('sk-fake-private-test-key',text);self.assertNotIn('never write',text)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(log.directory.stat().st_mode),0o700)

    def test_filename_is_validated_and_symlinks_are_not_followed(self):
        for value in ['../secret','x'*36,{},'00000000-0000-0000-0000-00000000000Z']:
            with self.assertRaises(cms.SourceError):conversation_id(value)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);log=TranscriptLog(root/'logs');log.directory.mkdir();identifier=str(uuid.uuid4())
            target=root/'target';target.write_text('unchanged');(log.directory/(identifier+'.txt')).symlink_to(target)
            with self.assertRaises(OSError):log.append(identifier,'Hello',{'text':'Hello'})
            self.assertEqual(target.read_text(),'unchanged')


class TranscriptHTTPTests(unittest.TestCase):
    def test_opening_chat_error_and_catalog_share_a_saved_conversation(self):
        tools=DemoTools(research_mode=True)
        value={'reply':'Hello.','question':'','fact_ids':[],'quick_replies':[],'state_update':{}}
        response={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        client=ResponsesClient(key='test',model='gpt-5.4',transport=lambda payload:response)
        with tempfile.TemporaryDirectory() as temp:
            server=make_server(Chat(tools,client),0,transcript_dir=temp)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            identifier=str(uuid.uuid4());base=f'http://127.0.0.1:{server.server_port}'
            def post(path,body):
                try:
                    with urlopen(Request(base+path,data=json.dumps({'conversation_id':identifier,**body}).encode(),headers={'Content-Type':'application/json'})) as r:return r.status,json.load(r)
                except HTTPError as error:
                    with error:return error.code,json.load(error)
            try:
                self.assertTrue(post('/api/conversation-start',{})[1]['conversation_log_saved'])
                code,result=post('/api/live-chat',{'message':'Hello'})
                self.assertEqual(code,200);self.assertTrue(result['conversation_log_saved']);self.assertNotIn('debug',result)
                self.assertEqual(post('/api/catalog',{'category':'PDP','user_message':'Please show standalone drug plans.'})[0],200)
                self.assertEqual(post('/api/catalog',{'action':'plan','plan_ids':[]})[0],422)
                text=(Path(temp)/(identifier+'.txt')).read_text()
                self.assertIn('User:\n  Hello',text);self.assertIn('Daylight Medicare:\n  Hello.',text)
                self.assertIn('Wellcare',text);self.assertIn('Please show standalone drug plans.',text);self.assertIn('Error:',text)
                self.assertEqual(len(list(Path(temp).glob('*.txt'))),1)
                self.assertEqual(post('/api/conversation-start',{'conversation_id':'../escape'})[0],422)
            finally:server.shutdown();server.server_close();thread.join()

    def test_starter_answers_are_validated_logged_and_never_call_the_model(self):
        tools=DemoTools(research_mode=True)
        def forbidden(payload):raise AssertionError('Starter questions must not call the model')
        client=ResponsesClient(key='test',model='gpt-5.4',transport=forbidden)
        with tempfile.TemporaryDirectory() as temp:
            server=make_server(Chat(tools,client),0,transcript_dir=temp)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            identifier=str(uuid.uuid4());base=f'http://127.0.0.1:{server.server_port}'
            def post(body):
                try:
                    with urlopen(Request(base+'/api/intake-answer',data=json.dumps({'conversation_id':identifier,**body}).encode(),headers={'Content-Type':'application/json'})) as r:return r.status,json.load(r)
                except HTTPError as error:
                    with error:return error.code,json.load(error)
            try:
                for field,value in [('recipient','someone'),('zip','34102'),('medicare','no'),('timing','soon'),('drugs','yes'),('hearing','unsure'),('vision','no'),('dental','yes')]:
                    code,result=post({'field':field,'value':value,'recipient':'someone'})
                    self.assertEqual(code,200);self.assertTrue(result['conversation_log_saved'])
                text=(Path(temp)/(identifier+'.txt')).read_text()
                self.assertEqual(text.count('Daylight Medicare (starter question)'),8)
                self.assertNotIn('Daylight Medicare (local welcome)',text)
                request=Request(base+'/api/conversation-start',data=json.dumps({'conversation_id':identifier}).encode(),headers={'Content-Type':'application/json'})
                with urlopen(request) as started:self.assertEqual(started.status,200)
                complete=(Path(temp)/(identifier+'.txt')).read_text()
                self.assertLess(complete.index('Do they want dental benefits?'),complete.index('Daylight Medicare (local welcome)'))
                self.assertIn('What’s their ZIP code?',text);self.assertIn('34102',text)
                self.assertIn('When might they need coverage?',text);self.assertIn('Within the next 3 months',text)
                self.assertIn('Do they want hearing benefits?',text);self.assertIn('I’m not sure',text)
                for body in [{'field':'zip','value':'12'},{'field':'ssn','value':'12345'},{'field':'dental','value':'guess'},{'field':'drugs','value':'yes','recipient':{}}]:
                    self.assertEqual(post(body)[0],422)
                self.assertEqual(len(list(Path(temp).glob('*.txt'))),1)
            finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
