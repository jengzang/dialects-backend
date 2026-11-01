"""Export isolated SQL candidates for local, resource-limited experiments.

Does not change application queries or the source database. Run with project
Python; replay the generated JSON using the adjacent stdlib-only runner.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from scripts.benchmark_vocabulary_search_candidates import load
from scripts.benchmark_vocabulary_entries import readonly

SOURCE = subprocess.check_output(['git', 'show', '29ebfa0:app/service/vocabulary/query.py'],
                                 cwd=Path(__file__).resolve().parents[1], text=True)


def candidates():
    current = load('followup_current', SOURCE)
    identity = load('followup_identity', SOURCE.replace(
        'len(location_terms) == 1 and _prefer_location_identity_scan(',
        'bool(location_terms) and _prefer_location_identity_scan('))
    prefer = identity._prefer_location_identity_scan
    identity._prefer_location_identity_scan = lambda **kw: prefer(
        **dict(kw, fields=identity.DEFAULT_SEARCH_FIELDS))
    grouped = load('followup_names', SOURCE)
    original = grouped._append_like_group

    def name_like(*, clauses, values, columns, terms):
        columns, terms = list(columns), list(terms)
        if columns != ['e.location_name']:
            return original(clauses=clauses, values=values, columns=columns, terms=terms)
        inner = []
        original(clauses=inner, values=values, columns=['scope.location_name'], terms=terms)
        clauses.append('e.location_name IN (SELECT scope.location_name FROM '
                       'vocabulary_entries scope GROUP BY scope.location_name HAVING '
                       + ' AND '.join(inner) + ')')

    grouped._append_like_group = name_like
    seeks = load('followup_name_seeks', SOURCE)
    seeks_original = seeks._append_like_group

    def seek_like(*, clauses, values, columns, terms):
        columns, terms = list(columns), list(terms)
        if columns != ['e.location_name']:
            return seeks_original(clauses=clauses, values=values, columns=columns, terms=terms)
        inner = []
        seeks_original(clauses=inner, values=values, columns=['scope.name'], terms=terms)
        clauses.append('e.location_name IN (WITH RECURSIVE names(name) AS ('
                       'SELECT MIN(location_name) FROM vocabulary_entries UNION ALL '
                       'SELECT (SELECT MIN(location_name) FROM vocabulary_entries '
                       'WHERE location_name > names.name) FROM names WHERE name IS NOT NULL) '
                       'SELECT scope.name FROM names scope WHERE ' + ' AND '.join(inner) + ')')

    seeks._append_like_group = seek_like
    before, after = SOURCE.split('def query_vocabulary_map_points(', 1)
    map_part, tail = after.split('def query_vocabulary_map_items(', 1)
    scan = load('followup_scan', before + 'def query_vocabulary_map_points('
                + map_part.replace('FROM vocabulary_entries e ',
                                   'FROM vocabulary_entries e NOT INDEXED ')
                + 'def query_vocabulary_map_items(' + tail)
    return {'current': current, 'identity': identity, 'grouped_names': grouped,
            'name_seeks': seeks, 'map_scan': scan}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=Path, default=Path('data/vocabulary.db'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    modules = candidates()
    force_page = load('followup_force_page', SOURCE.replace('if offset >= total:', 'if False:'))
    jobs = []
    with readonly(args.db) as conn:
        session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
        names = [r[0] for r in conn.execute('SELECT location_name FROM vocabulary_entries '
                    'GROUP BY location_name ORDER BY COUNT(*) DESC')]
        scopes = {'global': [], 'large': names[:1], 'small': ['天柱竹林'],
                  '22': names[:22], 'absent': ['不存在地点8f0b']}
        cases = {}
        for field in (['definition'], ['definition', 'headword'], ['headword']):
            for scope, locations in scopes.items():
                for word in ('蜘蛛', '皮', '人', '不存在词8f0b'):
                    cases[f'{"+".join(field)}:{scope}:{word}'] = dict(
                        search_fields=field, locations=locations, q=word)
        cases.update({
            'empty-single': dict(locations=names[-1:]),
            'empty-22': dict(locations=names[:22]),
            'overlap': dict(q=names[0], locations=names[:1]),
            'wildcard': dict(q='%', locations=names[-1:]),
            'location-wildcard': dict(q='人', locations=['%']),
            'province': dict(q='人', province='廣東', search_fields=['definition']),
            'region': dict(q='人', regions=['嶺南']),
        })
        for endpoint in ('items', 'standard_words', 'map_points'):
            for name, options in cases.items():
                reference = None
                for label, module in modules.items():
                    if label == 'map_scan' and endpoint != 'map_points':
                        continue
                    statements = []
                    conn.set_trace_callback(statements.append)
                    result = getattr(module, 'query_vocabulary_' + endpoint)(session=session, **options)
                    conn.set_trace_callback(None)
                    result = asdict(result)
                    if reference is None:
                        reference = result
                    assert result == reference, (endpoint, name, label)
                    jobs.append(dict(endpoint=endpoint, name=name, candidate=label,
                                     options=options, sql=statements))
                if endpoint == 'items':
                    statements = []
                    conn.set_trace_callback(statements.append)
                    result = force_page.query_vocabulary_items(session=session, **options)
                    conn.set_trace_callback(None)
                    assert asdict(result) == reference
                    assert len(statements) == 2
                    jobs.append(dict(endpoint=endpoint, name=name, candidate='cold_page_first',
                                     options=options, sql=statements, flow='cold_page_first'))
    args.output.write_text(json.dumps(jobs, ensure_ascii=False, indent=2))
    print(json.dumps({'jobs': len(jobs), 'payload_checks': len(jobs), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
