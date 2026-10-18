import struct
from .errors import FormatError
ParseError = FormatError
def fstr(b, p):
    if p + 4 > len(b):
        raise ParseError(f'FString truncated at {p:x}')
    n = struct.unpack_from('<i', b, p)[0]
    p += 4
    if not -20000000 < n < 20000000:
        raise ParseError(f'FString length {n} at {p - 4:x}')
    nb = n if n >= 0 else -2 * n
    if p + nb > len(b):
        raise ParseError('FString exceeds buffer')
    r = b[p:p + nb]
    if nb and (not r.endswith(b'\x00' if n > 0 else b'\x00\x00')):
        raise ParseError('FString missing terminator')
    return (r[:-1].decode('utf-8') if n > 0 else r[:-2].decode('utf-16le') if n < 0 else '', p + nb)

def properties(b, start, end):
    p = start
    out = []
    while p < end:
        a = p
        name, p = fstr(b, p)
        if name == 'None':
            return (out, p)
        kind, p = fstr(b, p)
        szpos = p
        size, index = struct.unpack_from('<II', b, p)
        p += 8
        sub = None
        boolean = None
        if kind == 'StructProperty':
            sub, p = fstr(b, p)
            p += 16
        elif kind in ('ByteProperty', 'EnumProperty', 'ArrayProperty', 'SetProperty'):
            sub, p = fstr(b, p)
        elif kind == 'MapProperty':
            s1, p = fstr(b, p)
            s2, p = fstr(b, p)
            sub = [s1, s2]
        elif kind == 'BoolProperty':
            boolean = b[p]
            p += 1
        elif kind not in ('StrProperty', 'IntProperty', 'UInt32Property', 'Int64Property', 'UInt64Property', 'FloatProperty', 'DoubleProperty', 'NameProperty', 'ObjectProperty', 'TextProperty', 'SoftObjectProperty'):
            raise ParseError(f'Unknown kind {kind} at {a:x}')
        guid = b[p]
        p += 1
        if guid:
            p += 16
        stop = p + size
        if stop > end:
            raise ParseError(f'{name} end {stop:x} > parent {end:x}')
        d = {'name': name, 'type': kind, 'start': a, 'size_offset': szpos, 'size': size, 'index': index, 'subtype': sub, 'data_start': p, 'end': stop}
        if boolean is not None:
            d['value'] = boolean
        if kind in ('StrProperty', 'NameProperty', 'EnumProperty'):
            val, q = fstr(b, p)
            if q != stop:
                raise ParseError(f'{name} value size mismatch {q:x} {stop:x}')
            d['value'] = val
        elif kind == 'IntProperty' and size == 4:
            d['value'] = struct.unpack_from('<i', b, p)[0]
        out.append(d)
        p = stop
    raise ParseError(f'No terminator in {start:x}:{end:x}')
