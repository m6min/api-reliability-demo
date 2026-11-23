import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--dataset', choices=['verification', 'products-500'], default='verification')
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'data' / args.dataset
OUT.mkdir(parents=True, exist_ok=True)
if (OUT / 'results.json').exists():
    raise RuntimeError('Results already exist; archive them before rerunning')
env = dict(os.environ, REDIS_DB='15', PRODUCTS_CACHE_TTL_SECONDS='300', RATE_LIMIT_REQUESTS='1000000', SQL_ECHO='false')
records = []
for index, enabled in enumerate([False, True, True, False, False, True], 1):
    label = f'{index:02d}-cache-{"on" if enabled else "off"}'
    env['PRODUCTS_CACHE_ENABLED'] = str(enabled).lower()
    with (OUT / f'{label}-server.log').open('w') as server_log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--port', '8017', '--workers', '1', '--no-access-log'], cwd=ROOT, env=env, stdout=server_log, stderr=subprocess.STDOUT)
        try:
            for attempt in range(100):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8017/api/products/', timeout=3) as response:
                        payload = response.read()
                    break
                except Exception:
                    if server.poll() is not None:
                        raise RuntimeError('API exited; inspect server log')
                    time.sleep(0.2)
            else:
                raise RuntimeError('API did not become ready')
            expected_count = 500 if args.dataset == 'products-500' else 2
            if len(json.loads(payload)) != expected_count:
                raise RuntimeError('Unexpected product count; check data and cache')
            for _ in range(20):
                urllib.request.urlopen('http://127.0.0.1:8017/api/products/', timeout=10).close()
            prefix = str(OUT / label)
            with (OUT / f'{label}-locust.log').open('w') as log:
                run = subprocess.run([sys.executable, '-m', 'locust', '--headless', '--host', 'http://127.0.0.1:8017', '--users', '50', '--spawn-rate', '50', '--run-time', '60s', '--only-summary', '--csv', prefix], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            with open(prefix + '_stats.csv', newline='') as stream:
                row = list(csv.DictReader(stream))[-1]
            log_text = (OUT / f'{label}-locust.log').read_text()
            record = dict(id=label, cache=enabled, users=50, workers=1, requests=int(row['Request Count']), failures=int(row['Failure Count']), avg=float(row['Average Response Time']), p95=float(row['95%']), p99=float(row['99%']), rps=float(row['Requests/s']), exit_code=run.returncode, cpu_warning='CPU usage' in log_text, product_count=len(json.loads(payload)), payload_sha256=hashlib.sha256(payload).hexdigest())
            records.append(record)
            (OUT / 'results.json').write_text(json.dumps(records, indent=2))
            print(json.dumps(record), flush=True)
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
