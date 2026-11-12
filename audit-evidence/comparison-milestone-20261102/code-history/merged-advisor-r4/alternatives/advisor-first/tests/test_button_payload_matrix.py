"""Free production-renderer button inventory; no server, browser or model calls."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server  # Registers the pinned shared engine; does not start it.
from adaptive_flow import Q
from chat import ResponsesClient
from natural_flow import NaturalConversation


def button_registry():
    def no_model(_):
        raise AssertionError('The button audit must never call a model.')

    flow = NaturalConversation(None, None,
        json.loads((HERE/'web/guide-contract.json').read_text()),
        json.loads((HERE/'web/teaching-facts.json').read_text()),
        json.loads((HERE/'web/readiness-content.json').read_text()),
        ResponsesClient(key='synthetic', model='gpt-5.4', transport=no_model),
        False, None, fixture=False)
    questions = []
    for identifier, definition in Q.items():
        entity = ('doctor-2' if identifier == 'RC21' else
                  'medicine-2' if identifier in {'RC22', 'RC23'} else 'profile')
        for fields in (None, [key for key in definition['fieldNames'] if key != 'choice']):
            question = flow.question(identifier, fields or None, entity)
            question['auditInventoryId'] = identifier
            question['auditVariant'] = 'default' if fields is None else 'all_fields'
            questions.append(question)
    # These options are created by the service's conditional scheduler rather
    # than the base question definition. Use the same reference rows.
    county = flow.question('RC02', ['county'])
    rows = next(rows for rows in flow.reference['zips'].values() if len(rows) > 1)
    county['fields'][0].update(type='select', options=[[x[0], x[1]+', '+x[2]] for x in rows])
    county.update(auditInventoryId='RC02', auditVariant='county_select')
    questions.append(county)
    for identifier, fields in [('RC11', ['jobEnd']), ('RC11', ['coverageEnd']),
                               ('RC16', ['priorMedigap']), ('RC23', ['daysSupply']),
                               ('RC23', ['channel'])]:
        question = flow.question(identifier, fields, 'medicine-2' if identifier == 'RC23' else 'profile')
        question.update(auditInventoryId=identifier, auditVariant='.'.join(fields))
        questions.append(question)
    return {'inventoryIds': list(Q), 'questions': questions,
            'baseline': json.loads((HERE/'web/baseline-content.json').read_text())}


class ButtonPayloadMatrixTests(unittest.TestCase):
    def test_every_service_owned_finite_button_uses_production_payloads(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node.js is required for the button contract audit.')
        script = Path(__file__).with_suffix('.js')
        result = subprocess.run([node, str(script)],
            input=json.dumps(button_registry()), capture_output=True, text=True,
            timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
