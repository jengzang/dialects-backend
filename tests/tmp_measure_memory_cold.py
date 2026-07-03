import json
import os
import subprocess
import sys

TARGET = sys.argv[1]
os.environ.setdefault('_RUN_TYPE', 'WEB')
PKGS = ['numpy','pandas','scipy','sklearn','numba','parselmouth','networkx','openpyxl','xlrd','pyxlsb','lxml']

def ps_metrics():
    pid = os.getpid()
    out = subprocess.check_output(['ps','-o','pid=,rss=,vsz=,%mem=,comm=','-p',str(pid)], text=True).strip()
    parts = out.split(None, 4)
    return {
        'pid': int(parts[0]),
        'rss_kb': int(parts[1]),
        'rss_mb': round(int(parts[1]) / 1024, 2),
        'vsz_kb': int(parts[2]),
        'vsz_mb': round(int(parts[2]) / 1024, 2),
        'mem_percent': float(parts[3]),
        'comm': parts[4] if len(parts) > 4 else '',
    }

def loaded_heavy_modules():
    return {name: any(m == name or m.startswith(name + '.') for m in sys.modules) for name in PKGS}

import app.main as m
result = {'target': TARGET, 'after_import': {**ps_metrics(), 'heavy_loaded': loaded_heavy_modules(), 'module_count': len(sys.modules)}}
if TARGET == 'main_create':
    m.create_main_app()
elif TARGET == 'main_startup':
    m.run_main_startup()
elif TARGET == 'cluster_create':
    m.create_cluster_app()
elif TARGET == 'cluster_startup':
    m.run_cluster_startup()
elif TARGET == 'gis_create':
    m.create_gis_app()
elif TARGET == 'gis_startup':
    m.run_gis_startup()
else:
    raise SystemExit(f'unknown target: {TARGET}')
result['after_target'] = {**ps_metrics(), 'heavy_loaded': loaded_heavy_modules(), 'module_count': len(sys.modules)}
print(json.dumps(result, ensure_ascii=False))
