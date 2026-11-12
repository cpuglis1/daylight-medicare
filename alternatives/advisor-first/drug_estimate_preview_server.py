#!/usr/bin/env python3
"""Run the D146 fictional estimate preview with a separate loopback demo."""
from pathlib import Path
from tempfile import TemporaryDirectory

from demo_server import REPO, build_demo
from part_d_preview import attach


def main():
    with TemporaryDirectory(prefix='daylight-d146-') as temp:
        with build_demo(8897, fixture=True, database=Path(temp) / 'fictional.sqlite3') as demo:
            attach(demo, REPO)
            print('Fictional D146 preview: http://localhost:8897/drug-estimate-preview', flush=True)
            try:
                demo.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == '__main__':
    main()
