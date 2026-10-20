"""Secret-free transport only; the unchanged Phase-3N writer owns all semantics."""
import base64
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('phase3o_actual_writer', ROOT/'scripts/phase3n/writer_plan.py')
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


def transport(value):
    if type(value) is bytes:
        return {'$bytes': base64.b64encode(value).decode('ascii')}
    if type(value) in (tuple, list):
        return [transport(v) for v in value]
    if type(value) is dict:
        return {k: transport(v) for k, v in value.items()}
    return value


def restore(value):
    if type(value) is dict:
        if set(value) == {'$bytes'}:
            return base64.b64decode(value['$bytes'], validate=True)
        return {k: restore(v) for k, v in value.items()}
    if type(value) is list:
        return [restore(v) for v in value]
    return value


def plans(request):
    writer.require(type(request) is dict and set(request) == {
        'routes','observations','existing','created_at','format_version','intent','representation'}, 'request fields')
    writer.require(type(request['observations']) is list and 1 <= len(request['observations']) <= 4, 'bounded observations')
    catalog = writer.observation.catalog_module.normative_catalog()
    planner = writer.WriterPlanner(catalog, request['routes'], restore(request['existing']))
    return [transport(planner.plan(row, format_version=request['format_version'], intent=request['intent'],
                                   representation=request['representation'], created_at=request['created_at']))
            for row in request['observations']]


def main():
    try:
        request = json.loads(sys.stdin.read(), object_pairs_hook=writer.observation.units.unique_object)
        result = {'ok': True, 'plans': plans(request)}
    except ValueError as error:
        result = {'ok': False, 'failure': 'PLAN_REJECTED', 'reason': str(error)}
    except Exception as error:
        result = {'ok': False, 'failure': 'RUNTIME_GAP', 'exception': type(error).__name__, 'reason': str(error)}
    print(writer.observation.units.compact(result))


if __name__ == '__main__':
    main()
