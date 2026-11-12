"""Local operator commands for the fictional pilot rehearsal."""
import argparse
import json
from pathlib import Path

import server  # Validate the pinned engine and load the local import paths.
from pilot_access import FLAGS, PilotAccess
from pilot_budget import PilotBudget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('initialize', 'issue'):
        sub.add_parser(name).add_argument('expires_at', type=int, help='UTC Unix timestamp')
    revoke = sub.add_parser('revoke')
    revoke.add_argument('participant')
    switch = sub.add_parser('switch')
    switch.add_argument('name', choices=FLAGS)
    switch.add_argument('state', choices=('on', 'off'))
    sub.add_parser('usage')
    sub.add_parser('session-costs')
    sub.add_parser('reconcile').add_argument('provider_total_nano_usd', type=int)
    sub.add_parser('complete').add_argument('participant')
    args = parser.parse_args()
    if args.command == 'initialize':
        access = PilotAccess.initialize(args.directory, ends_at=args.expires_at)
        PilotBudget.open(access, initialize=True)
        return
    access = PilotAccess(args.directory)
    if args.command == 'issue':
        key, token = access.issue(expires_at=args.expires_at)
        print(json.dumps({'participant': key, 'private_path': '/pilot/join#' + token}))
    elif args.command == 'revoke':
        access.revoke(args.participant)
    elif args.command == 'switch':
        access.set_flag(args.name, args.state == 'on')
    elif args.command == 'complete':
        access.mark_completed(args.participant)
    elif args.command == 'session-costs':
        print(json.dumps(PilotBudget.open(access).session_costs()))
    elif args.command == 'reconcile':
        report = PilotBudget.open(access).reconcile(args.provider_total_nano_usd)
        print(json.dumps(report))
        if report['status'] != 'matched':
            raise SystemExit(2)
    else:
        fields = ('participant', 'call_count', 'settled_nano_usd', 'held_nano_usd', 'input_tokens', 'output_tokens')
        print(json.dumps([dict(zip(fields, row)) for row in PilotBudget.open(access).participant_usage()]))


if __name__ == '__main__':
    main()
