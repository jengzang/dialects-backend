import gc
import json
import os
import subprocess
import sys
import traceback

os.environ.setdefault('_RUN_TYPE', 'WEB')

PKGS = [
    'numpy', 'pandas', 'scipy', 'sklearn', 'numba', 'parselmouth', 'networkx', 'openpyxl', 'xlrd', 'pyxlsb', 'lxml'
]

def ps_metrics():
    pid = os.getpid()
    out = subprocess.check_output([
        'ps', '-o', 'pid=,rss=,vsz=,%mem=,comm=', '-p', str(pid)
    ], text=True).strip()
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
    loaded = {}
    for name in PKGS:
        loaded[name] = any(m == name or m.startswith(name + '.') for m in sys.modules)
    return loaded

results = []

def snap(label):
    gc.collect()
    results.append({
        'label': label,
        **ps_metrics(),
        'heavy_loaded': loaded_heavy_modules(),
        'module_count': len(sys.modules),
    })

snap('baseline')
steps = [
    ('import_app_main', "import app.main as m; globals()['app_main_mod']=m"),
    ('create_main_app', "globals()['main_app']=app_main_mod.create_main_app()"),
    ('run_main_startup', "app_main_mod.run_main_startup()"),
    ('create_cluster_app', "globals()['cluster_app']=app_main_mod.create_cluster_app()"),
    ('run_cluster_startup', "app_main_mod.run_cluster_startup()"),
    ('create_gis_app', "globals()['gis_app']=app_main_mod.create_gis_app()"),
    ('run_gis_startup', "app_main_mod.run_gis_startup()"),
]
for label, code in steps:
    try:
        exec(code, globals(), globals())
        snap(label)
    except Exception as e:
        results.append({
            'label': label,
            'error': str(e),
            'traceback': traceback.format_exc(),
            **ps_metrics(),
            'heavy_loaded': loaded_heavy_modules(),
            'module_count': len(sys.modules),
        })
print(json.dumps(results, ensure_ascii=False, indent=2))
