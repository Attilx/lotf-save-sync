import struct
from .schema import *
from .records import parse_records
from .dynamic import dynamic_records, dynamic_registry
from .errors import FormatError
NATIVE_TAILS = []

def deps_groups(b, p):
    pos = p['data_start']
    removed, count = struct.unpack_from('<II', b, pos)
    if not removed == 0:
        raise FormatError('Unexpected save structure')
    pos += 8
    groups = []
    for _ in range(count):
        owner = b[pos:pos + 16].hex()
        pos += 16
        vp, pos = properties(b, pos, p['end'])
        if not (len(vp) == 1 and vp[0]['name'] == 'DependenciesValues'):
            raise FormatError('Unexpected save structure')
        mp = vp[0]
        ii = mp['data_start']
        rm, nn = struct.unpack_from('<II', b, ii)
        if not rm == 0:
            raise FormatError('Unexpected save structure')
        ii += 8
        refs = []
        for j in range(nn):
            key, ii = fstr(b, ii)
            vals, ii = properties(b, ii, mp['end'])
            refs.append({'key': key, 'details': {x['name']: x for x in vals}})
        if not ii == mp['end']:
            raise FormatError('Unexpected save structure')
        groups.append({'owner': owner, 'refs': refs})
    if not pos == p['end']:
        raise FormatError('Unexpected save structure')
    if not len({x['owner'] for x in groups}) == len(groups):
        raise FormatError('Unexpected save structure')
    return groups

def strs(b, p):
    pos = p['data_start']
    n = struct.unpack_from('<I', b, pos)[0]
    pos += 4
    out = []
    for _ in range(n):
        v, pos = fstr(b, pos)
        out.append(v)
    if not pos == p['end']:
        raise FormatError('Unexpected save structure')
    return out

def datalist(b, p):
    if not p['subtype'] == 'ByteProperty':
        raise FormatError('Unexpected save structure')
    n = struct.unpack_from('<I', b, p['data_start'])[0]
    if not n == p['size'] - 4:
        raise FormatError('Unexpected save structure')
    if n == 0:
        return []
    pp, end = properties(b, p['data_start'] + 4, p['end'])
    tail = b[end:p['end']]
    if any(tail):
        NATIVE_TAILS.append({'offset': end, 'bytes': len(tail), 'sha256': sha(tail)})
    return pp

def all_records(b):
    root = root_properties(b)
    s = children(b, root['SerializationData'])
    out = []
    for cat in ('ObjectRecords', 'ManualManagementObjectRecords'):
        for rr in parse_records(b, children(b, s[cat])['Map']):
            out.append((cat + '/' + rr['guid'], rr['properties']))
    for m in dynamic_records(b, s['DynamicObjectRecords']):
        for rr in m['records']:
            out.append(('Dynamic/' + m['name'] + '/' + rr['guid'], rr['properties']))
    for name, p in root.items():
        if p['type'] == 'StructProperty' and p['subtype'] == 'ObjectRecord':
            out.append(('Root/' + name, children(b, p)))
    return out

def check_record(b, label, record):
    de = children(b, record['ObjectRecordDetails'])
    oid = contents(b, de['ID']).hex()
    groups = deps_groups(b, record['DependenciesValues']) if 'DependenciesValues' in record else []
    issues = []
    group_owners = [g['owner'] for g in groups]
    if groups and oid not in group_owners:
        issues.append({'type': 'owner_ID_missing_in_dependency_groups', 'record': label, 'class': de['ClassName'].get('value'), 'object_ID': oid, 'group_owners': group_owners})
    keys = []
    handles = []
    bytearrays = 0
    component_count = 0
    for g in groups:
        for ref in g['refs']:
            rd = ref['details']
            keys.append(ref['key'])
            if not rd['PathName']['value'] == ref['key']:
                raise FormatError('Unexpected save structure')
            if 'Data' in rd:
                vals = datalist(b, rd['Data'])
                bytearrays += 1
                if rd['ClassName']['value'] == '/Script/LOTF2.SerializableActorHandle':
                    dd = {x['name']: x for x in vals}
                    sid = children(b, dd['ID'])
                    handles.append({'path': ref['key'], 'guid': contents(b, sid['Guid']).hex(), 'manual_override': sid.get('bManualOverrideIdValue', {}).get('value'), 'friendly_name': sid.get('FriendlyName', {}).get('value')})
    if 'Dependencies' in de:
        declared = strs(b, de['Dependencies'])
        if not set(declared) <= set(keys):
            issues.append({'type': 'declared_dependency_not_serialized', 'record': label, 'missing': sorted(set(declared) - set(keys))})
    if 'Data' in de:
        vals = datalist(b, de['Data'])
        bytearrays += 1
        for p in vals:
            if p['type'] == 'ObjectProperty':
                ref, end = fstr(b, p['data_start'])
                if not end == p['end']:
                    raise FormatError('Unexpected save structure')
                if 'SerializableActorHandle_' in ref and ref not in keys:
                    issues.append({'type': 'handle_reference_not_serialized', 'record': label, 'property': p['name'], 'path': ref})
    if 'Components' in de:
        p = de['Components']
        pos = p['data_start']
        removed, n = struct.unpack_from('<II', b, pos)
        if not removed == 0:
            raise FormatError('Unexpected save structure')
        pos += 8
        names = []
        for _ in range(n):
            key, pos = fstr(b, pos)
            names.append(key)
            pp, pos = properties(b, pos, p['end'])
            dd = {x['name']: x for x in pp}
            component_count += 1
            if not dd['Name']['value'] == key:
                raise FormatError('Unexpected save structure')
            if 'Data' in dd:
                datalist(b, dd['Data'])
                bytearrays += 1
        if not (pos == p['end'] and len(names) == len(set(names))):
            raise FormatError('Unexpected save structure')
    return {'object_id': oid, 'record': label, 'issues': issues, 'groups': len(groups), 'dependencies': len(keys), 'handles': handles, 'bytearrays': bytearrays, 'components': component_count}
