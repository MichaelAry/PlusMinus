"""Process-isolated PlusMinus runner with optional sampled resource telemetry."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


def find_runner():
    if getattr(sys, 'frozen', False):
        roots = (Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)),
                 Path(sys.executable).resolve().parent)
        folders = tuple(folder for root in roots
                        for folder in (root, root / 'build' / 'Release',
                                       root / 'build', root / 'build' / 'Debug'))
    else:
        root = Path(__file__).resolve().parent
        folders = (root / 'build' / 'Release', root / 'build', root / 'build' / 'Debug', root)
    for folder in folders:
        for name in ('plusminus_runner.exe', 'plusminus_runner'):
            path = folder / name
            if path.is_file():
                return path
    return None


def execute(path, source, mode='run', timeout=5.0, cancel=None):
    """Run the VM. Sampled RSS is not a guaranteed instantaneous peak."""
    start = time.perf_counter()
    cancel = cancel or threading.Event()
    report = dict(ok=False, output='', result='', variables='', bytecode='', error='', diagnostics=[])
    metrics = dict(wall_ms=0.0, cpu_ms=None, peak_rss_mb=None,
                   peak_threads=None, samples=[], sample_interval_ms=40)
    process = None
    proc = None
    try:
        if cancel.is_set():
            raise RuntimeError('Stopped by user')
        if mode not in ('run', 'compile', 'profile'):
            raise ValueError('Unsupported execution mode')
        process = subprocess.Popen([str(Path(path).resolve()), mode], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if psutil is not None:
            try:
                proc = psutil.Process(process.pid)
            except (psutil.Error, OSError):
                proc = None
        data = source.encode('utf-8')
        last_sample = 0.0
        while True:
            elapsed = time.perf_counter() - start
            remaining = timeout - elapsed
            if cancel.is_set() or remaining <= 0:
                process.kill()
                process.communicate()
                raise RuntimeError('Stopped by user' if cancel.is_set() else 'Execution timed out')
            if proc is not None and elapsed - last_sample >= 0.035:
                try:
                    info = proc.memory_info()
                    cpu = proc.cpu_times()
                    rss = round(info.rss / (1024 * 1024), 3)
                    threads = proc.num_threads()
                    cpu_ms = round((cpu.user + cpu.system) * 1000, 3)
                    metrics['peak_rss_mb'] = max(metrics['peak_rss_mb'] or 0, rss)
                    metrics['peak_threads'] = max(metrics['peak_threads'] or 0, threads)
                    metrics['cpu_ms'] = cpu_ms
                    if len(metrics['samples']) < 5000:
                        metrics['samples'].append([round(elapsed*1000, 2), rss, threads, cpu_ms])
                except (psutil.Error, OSError):
                    proc = None
                last_sample = elapsed
            try:
                stdout, stderr = process.communicate(input=data, timeout=min(0.04, remaining))
                break
            except subprocess.TimeoutExpired:
                data = None
        try:
            decoded = json.loads(stdout.decode('utf-8', errors='replace'))
            if not isinstance(decoded, dict) or not isinstance(decoded.get('ok'), bool):
                raise ValueError('Invalid runner report')
            report.update({k: decoded[k] for k in report if k in decoded})
            if isinstance(decoded.get('metrics'), dict):
                metrics.update({k: v for k,v in decoded['metrics'].items()
                                if k in ('compile_ms','execute_ms','program_instructions',
                                         'executed_instructions','opcode_hits')
                                and (isinstance(v,(int,float)) or
                                     (k=='opcode_hits' and isinstance(v,dict)))})
            if process.returncode and report['ok']:
                report.update(ok=False,error=f'Runner exited with code {process.returncode}')
        except (ValueError, UnicodeError):
            report['error'] = f'Runner exited with code {process.returncode}; invalid response.'
        if stderr:
            report['error'] += ('\n' if report['error'] else '') + stderr.decode('utf-8', errors='replace')
    except (OSError, RuntimeError, ValueError) as exc:
        report['error'] = str(exc)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
    report['ms'] = round((time.perf_counter() - start) * 1000, 2)
    metrics['wall_ms'] = report['ms']
    report['metrics'] = metrics
    return report


def check(case, report):
    normalize = lambda s: s.replace('\r\n','\n')
    return report['ok'] and normalize(report[case['kind']]) == normalize(case['expected'])
