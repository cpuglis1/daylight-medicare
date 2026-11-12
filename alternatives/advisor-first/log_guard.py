"""HP-09: operational logs stay content-free.

Daylight's log calls already carry only fixed codes, counts, byte sizes and
allowlisted diagnostics (see transport_diagnostics, controller_diagnostics and
request_packing). This filter is a last line of defense on the Daylight loggers:
if a rendered log line ever contains an SSN, Medicare number or card-number
shape, the whole line is replaced with a fixed notice. It cannot recognize
health facts such as drug names, so the content-free rule is enforced by
construction and by tests/test_content_free_logs.py, not by this filter.
"""
import logging

from identifier_guard import find_transport_identifiers

WITHHELD = 'Daylight log entry withheld: identifier pattern'
LOGGERS = ('natural_flow', 'natural_agent', 'session_recovery', 'comparison_service',
           'provider_tokens', 'advisor_budget', 'daylight.pilot.access')


class ContentFreeFilter(logging.Filter):
    def filter(self, record):
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = ''
            record.msg, record.args = 'Daylight log entry withheld: unformattable', None
        if find_transport_identifiers(rendered):
            record.msg, record.args = WITHHELD, None
            record.exc_info = record.exc_text = record.stack_info = None
        return True


def _timestamps():
    """D138: every warning line carries a UTC time, so slow turns can be matched to log entries.

    Only when nothing else configured logging; the content-free filter is unchanged.
    """
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)sZ %(message)s', '%Y-%m-%dT%H:%M:%S')
        formatter.converter = __import__('time').gmtime
        handler.setFormatter(formatter)
        root.addHandler(handler)


def install(names=LOGGERS):
    _timestamps()
    for name in names:
        logger = logging.getLogger(name)
        if not any(isinstance(item, ContentFreeFilter) for item in logger.filters):
            logger.addFilter(ContentFreeFilter())
