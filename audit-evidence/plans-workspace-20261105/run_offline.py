"""No non-loopback sockets or real provider curl processes in verification."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'alternatives/advisor-first/tests'), str(ROOT/'alternatives/advisor-first'),
               str(ROOT/'alternatives/chat-first/cms-slice/scripts')]

def guard(event, args):
    if event == 'socket.connect' and isinstance(args[1], tuple) and args[1][0] not in {'127.0.0.1','localhost','::1'}:
        raise AssertionError('Outbound network forbidden in offline verification')
    if event == 'subprocess.Popen' and Path(str(args[0])).name == 'curl':
        raise AssertionError('Provider transport forbidden in offline verification')

sys.addaudithook(guard)
loader=unittest.defaultTestLoader
suite=(loader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv)>1
       else loader.discover(str(ROOT/'alternatives/advisor-first/tests'),pattern='test_*.py'))
result=unittest.TextTestRunner(verbosity=1).run(suite)
Path(__file__).with_name('focused-result.json' if len(sys.argv)>1 else 'full-result.json').write_text(json.dumps({
    'tests_run':result.testsRun,'failures':[str(t) for t,_ in result.failures],
    'errors':[str(t) for t,_ in result.errors],'skipped':[str(t) for t,_ in result.skipped]},indent=2)+'\n')
sys.exit(not result.wasSuccessful())
