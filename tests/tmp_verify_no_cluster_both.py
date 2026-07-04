import json
import os
os.environ.setdefault('_RUN_TYPE', 'WEB')
from serve import app
paths = sorted({getattr(r, 'path', None) for r in app.routes if getattr(r, 'path', None)})
print(json.dumps({
  'has_cluster': any(p.startswith('/api/tools/cluster') for p in paths),
  'cluster_paths': [p for p in paths if p.startswith('/api/tools/cluster')],
  'has_gis': any(p.startswith('/api/gis') for p in paths),
  'route_count': len(paths)
}, ensure_ascii=False, indent=2))
