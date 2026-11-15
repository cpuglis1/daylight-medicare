#!/usr/bin/env python3
"""Run the shared-profile D146 rehearsal on loopback port 8897."""

from pathlib import Path
from tempfile import TemporaryDirectory

from demo_server import REPO, build_demo
from part_d_preview import attach
from part_d_visit_http import install_profile_preview


def main():
    with TemporaryDirectory(prefix='daylight-d146-profile-') as temp:
        with build_demo(8897, fixture=True, database=Path(temp) / 'fictional.sqlite3') as demo:
            from daylight_data.serving.part_d_local import local_candidate
            attach(demo, REPO)
            install_profile_preview(demo, local_candidate(REPO))
            print('D146 shared-profile rehearsal: http://localhost:8897/', flush=True)
            try:
                demo.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == '__main__':
    main()
