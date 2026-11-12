"""Legacy UI/protocol regressions over explicitly synthetic/research evidence.

Production admission is tested without this double in test_consumer_acceptance.
There is deliberately no equivalent switch in the runtime or CLI.
"""
from unittest.mock import patch
from demo import make_server as runtime_server


class ResearchAdmissionDouble:
    def __init__(self, *args, **kwargs):
        pass

    def require_release(self):
        pass

    def require_output(self, value):
        return value

    def status(self):
        return {"consumer_ready": True, "validation_status": "synthetic_test_double"}


def make_research_test_server(*args, **kwargs):
    with patch("demo.ConsumerAcceptance", ResearchAdmissionDouble):
        return runtime_server(*args, **kwargs)
