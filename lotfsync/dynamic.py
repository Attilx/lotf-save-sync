import struct
from .properties import properties, fstr
from .records import parse_records
from .errors import FormatError
def dynamic_records(b, p):
    pos = p['data_start']
    removed, count = struct.unpack_from('<II', b, pos)
    if not removed == 0:
        raise FormatError('Unexpected save structure')
    pos += 8
    arr = []
    for i in range(count):
        start = pos
        name, pos = fstr(b, pos)
        vs = pos
        pp, pos = properties(b, pos, p['end'])
        if not (len(pp) == 1 and pp[0]['name'] == 'Map'):
            raise FormatError('Unexpected save structure')
        rec = parse_records(b, pp[0])
        arr.append({'name': name, 'start': start, 'value_start': vs, 'end': pos, 'map': pp[0], 'records': rec})
    if not pos == p['end']:
        raise FormatError('Unexpected save structure')
    return arr

def dynamic_registry(b, p):
    pos = p['data_start']
    removed, count = struct.unpack_from('<II', b, pos)
    if not removed == 0:
        raise FormatError('Unexpected save structure')
    pos += 8
    arr = []
    for i in range(count):
        start = pos
        pp, pos = properties(b, pos, p['end'])
        keys = {x['name']: x for x in pp}
        gp = keys['Guid']
        g = b[gp['data_start']:gp['end']].hex()
        vs = pos
        name, pos = fstr(b, pos)
        arr.append({'guid': g, 'name': name, 'start': start, 'end': pos, 'value_start': vs})
    if not pos == p['end']:
        raise FormatError('Unexpected save structure')
    return arr
