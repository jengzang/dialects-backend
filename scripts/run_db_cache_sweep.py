"""Run the cache sweep sequentially against explicit local read-only inputs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from benchmark_db_cache import FILES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=args.data_dir.resolve(strict=True)
    if args.output.exists():
        parser.error('output already exists; choose a new output filename')
    for file in FILES.values():
        (root/file).resolve(strict=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    records=[]
    started=time.monotonic()
    for repeat in range(3):
        for index,db in enumerate(FILES):
            base=[2000,16000,4096,8192]
            offset=(repeat+index)%4
            for cache in base[offset:]+base[:offset]:
                command=[sys.executable,str(Path(__file__).with_name('benchmark_db_cache.py')),
                         '--data-dir',str(root),'--db',db,'--cache-kib',str(cache),'--runs','4']
                child=subprocess.run(command,capture_output=True,text=True,timeout=100,check=True)
                row=json.loads(child.stdout)
                row['round']=repeat+1
                records.append(row)
                # Only the newly created output belongs to this invocation.
                args.output.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
                bad=[s['error'] for case in row['results'] for s in case['samples'] if 'error'in s]
                if any('interrupted' not in error for error in bad):
                    raise RuntimeError(f'{db}: SQL failure; inspect {args.output}')
            print(f'round {repeat+1}: {db}, {len(records)}/156 groups, {time.monotonic()-started:.1f}s',flush=True)


if __name__=='__main__':main()
