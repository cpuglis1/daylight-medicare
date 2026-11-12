"""Reserve monitoring for owned pg_restore backends, including index build time."""
from contextlib import contextmanager
import os
import shutil
import threading


def environment(label):
    result={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
    result['PGAPPNAME']=label
    return result


@contextmanager
def reserve_watch(c,process,database,label):
    finished=threading.Event();breached=[]
    def watch():
        while not finished.wait(.25):
            if shutil.disk_usage(c.ROOT).free<c.RESERVE+256*1024**2:
                breached.append(True)
                try:
                    with c.connect('postgres') as admin:
                        admin.execute('''SELECT pg_cancel_backend(pid) FROM pg_stat_activity
                            WHERE datname=%s AND application_name=%s AND pid<>pg_backend_pid()''',(database,label))
                finally:
                    process.terminate()
                return
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    try:
        yield
        if breached:raise RuntimeError('Owned restore canceled at required disk reserve')
    finally:finished.set();thread.join(timeout=10)
