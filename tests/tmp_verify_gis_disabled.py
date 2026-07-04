import json
import os
os.environ.setdefault('_RUN_TYPE', 'WEB')
from serve import app as serve_app
from app.main import create_gis_app

def route_paths(a):
    return sorted({getattr(r, 'path', None) for r in a.routes if getattr(r, 'path', None)})

serve_paths = route_paths(serve_app)
gis_paths = route_paths(create_gis_app())
print(json.dumps({
    'serve_has_gis': any(p.startswith('/api/gis') for p in serve_paths),
    'gis_app_has_gis': any(p.startswith('/api/gis') for p in gis_paths),
    'serve_gis_paths': [p for p in serve_paths if p.startswith('/api/gis')],
    'gis_app_gis_paths': [p for p in gis_paths if p.startswith('/api/gis')],
    'serve_route_count': len(serve_paths),
    'gis_route_count': len(gis_paths),
}, ensure_ascii=False, indent=2))
