"""Construct the offline D146 reader over the isolated local package."""
import getpass

from .part_d_estimate import PartDEstimate
from .pilot_foundation import PilotFoundation


def local_candidate(root, *, clock=None):
    package = root / 'infrastructure/daylight-data'
    socket = package / '.state/socket'
    connection = f'host={socket} port=55485 user={getpass.getuser()}'
    return PartDEstimate(PilotFoundation(
        package / '.state/pilot-foundation-2026-r1/binding.json', root=root,
        package_dsn=f'{connection} dbname=daylight_pilot_foundation_2026_r1',
        source_dsn=f'{connection} dbname=daylight_research_2026_r2',
        **({'clock': clock} if clock is not None else {}),
    ))


def fictional_report(case, choice):
    return {**{key: case[key] for key in ('period', 'prior_spending', 'assistance')},
            'medicines': [{key: value for key, value in med.items() if key != 'label'}
                          for med in case['medicines']],
            'pharmacy': choice['pharmacy'], 'offering_id': choice['offering_id']}


def hosted_readers(root, binding_path, *, package_dsn, controls_dsn):
    """D199: doctor and drug readers for the hosted invited fictional demo.

    The hosted binding declares its purpose and its STOP-ledger copy; every read still
    checks scope, the deadline, the control-file hashes and the ledger, and fails closed.
    """
    from .pilot_doctors import PilotDoctors
    from .pilot_foundation import HOSTED_PURPOSE
    def reader():
        return PilotFoundation(binding_path, root=root, package_dsn=package_dsn,
                               source_dsn=controls_dsn, served=HOSTED_PURPOSE)
    return PilotDoctors(reader()), PartDEstimate(reader())
