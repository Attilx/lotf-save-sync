import struct
from .format import children, fstr
from .properties import properties
from .errors import FormatError
def parse_records(b, p):
    pos = p['data_start']
    removed, count = struct.unpack_from('<II', b, pos)
    if not removed == 0:
        raise FormatError('Unexpected save structure')
    pos += 8
    records = []
    for i in range(count):
        start = pos
        keyprops, pos = properties(b, pos, p['end'])
        key = {x['name']: x for x in keyprops}
        guid = b[key['Guid']['data_start']:key['Guid']['end']].hex()
        value_start = pos
        valueprops, pos = properties(b, pos, p['end'])
        value = {x['name']: x for x in valueprops}
        details = children(b, value['ObjectRecordDetails'])
        record = {'guid': guid, 'start': start, 'value_start': value_start, 'end': pos, 'class': details['ClassName']['value'], 'name': details['Name']['value'], 'path': details['PathName']['value'], 'properties': value, 'details': details}
        records.append(record)
    if not (pos == p['end'] and len({r['guid'] for r in records}) == len(records)):
        raise FormatError('Unexpected save structure')
    return records
