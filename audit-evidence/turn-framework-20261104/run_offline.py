"""Run technical checks with outbound sockets and real curl processes forbidden."""
import sys, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'alternatives/advisor-first/tests'), str(ROOT/'alternatives/advisor-first')]
def guard(event, args):
    if event == 'socket.connect':
        address = args[1]
        if isinstance(address, tuple) and address[0] not in {'127.0.0.1', 'localhost', '::1'}:
            raise AssertionError('Outbound network forbidden in offline verification')
    if event == 'subprocess.Popen' and Path(str(args[0])).name == 'curl':
        raise AssertionError('Real provider transport forbidden in offline verification')
sys.addaudithook(guard)
loader = unittest.defaultTestLoader
suite = loader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv)>1 else loader.discover(str(ROOT/'alternatives/advisor-first/tests'), pattern='test_*.py')
result = unittest.TextTestRunner(verbosity=1).run(suite)
Path(__file__).with_name('test-result.json').write_text(json.dumps({
 'tests_run': result.testsRun, 'failures': [str(t) for t,_ in result.failures],
 'errors': [str(t) for t,_ in result.errors], 'skipped': [str(t) for t,_ in result.skipped]
}, indent=2)+'\n')
sys.exit(not result.wasSuccessful())
