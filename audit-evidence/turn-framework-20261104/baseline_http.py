import sys,types,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'alternatives/advisor-first/tests'),str(ROOT/'alternatives/advisor-first')]
import server
before=Path(__file__).with_name('before')/'alternatives/advisor-first'
for name in ['natural_state','composition_recovery','advisor_memory','natural_agent','natural_flow']:
 m=types.ModuleType(name);m.__file__=str(ROOT/'alternatives/advisor-first'/f'{name}.py');sys.modules[name]=m
 exec(compile((before/f'{name}.py').read_text(),m.__file__,'exec'),m.__dict__)
server.NaturalConversation=sys.modules['natural_flow'].NaturalConversation
server.NaturalAgent=sys.modules['natural_agent'].NaturalAgent
names=['test_education_lifecycle', 'test_understanding_http']
result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(names))
Path(__file__).with_name('baseline-http-result.json').write_text(json.dumps({'run':result.testsRun,'failures':[t.id() for t,_ in result.failures],'errors':[t.id() for t,_ in result.errors]},indent=2)+'\n')
