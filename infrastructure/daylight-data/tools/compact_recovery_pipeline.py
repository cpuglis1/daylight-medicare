"""Wait for the owned full copy, then finalize/backup/restore/verify sequentially.

This supervisor never retires a database or changes the active evidence schema.
"""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

import compact_database_r2 as c


def record(value):
    with (c.RUN/'recovery-pipeline.jsonl').open('a') as log:
        json.dump({'at':c.now(),**value},log);log.write('\n');log.flush()
    print(json.dumps(value),flush=True)


if __name__=='__main__':
    with (c.RUN/'LOCK').open('a') as lock:
        record({'phase':'waiting_for_full_copy'})
        while True:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                if not (c.RUN/'full-load.json').exists():raise RuntimeError('Copy stopped before full completion; original remains active')
                break
            except BlockingIOError:time.sleep(1)
        for phase in ('finalize','backup','restore','verify_restore'):
            record({'phase':phase,'status':'started','free_bytes':c.guard()})
            with (c.RUN/('pipeline-'+phase+'.log')).open('x') as log:
                result=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('compact_recovery.py')),phase],stdout=log,stderr=subprocess.STDOUT)
            record({'phase':phase,'exit_code':result.returncode,'free_bytes':c.guard()})
            if result.returncode:raise RuntimeError('Recovery pipeline stopped at '+phase+'; inspect preserved log')
        record({'phase':'recovery_complete','passed':True,'no_live_cutover_or_retirement_executed':True})
