import struct, zlib, re, hashlib
from .properties import properties, fstr
from .errors import FormatError
CHUNK_MAGIC = bytes.fromhex('c1832a9e22222222')
CHUNK_BYTES = 131072
PREFIX = 'HexGameplayModifier.'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def strict_read(data):
    if not 100 <= len(data) <= 64*1024*1024:
        raise FormatError('Save file size outside supported limits')
    if not data[:4] == b'GVAS':
        raise FormatError('Unexpected save structure')
    m = re.search(b'/Script/LOTF2\\.[A-Za-z0-9_]+\\x00', data[:65536])
    if not m:
        raise FormatError('Unexpected save structure')
    header = data[:m.end()]
    size = struct.unpack_from('<I', data, len(header))[0]
    start = len(header) + 4
    end = start + size
    if not end + 4 == len(data):
        raise FormatError('File body length mismatch')
    if not zlib.crc32(data[:-4]) == struct.unpack_from('<I', data, end)[0]:
        raise FormatError('CRC mismatch')
    pos = start
    chunks = []
    while pos < end:
        begin = pos
        if pos + 49 > end or len(chunks) >= 2048:
            raise FormatError('Chunk limits exceeded')
        if not data[pos:pos + 8] == CHUNK_MAGIC:
            raise FormatError('Unexpected save structure')
        pos += 8
        if not data[pos:pos + 9] == struct.pack('<HIHB', 0, 2, 0, 3):
            raise FormatError('Unexpected chunk metadata')
        cs, rs, cs2, rs2 = struct.unpack_from('<QQQQ', data, pos + 9)
        if not (cs == cs2 and rs == rs2):
            raise FormatError('Unexpected save structure')
        pos += 41
        if not (0 < rs <= CHUNK_BYTES and 0 < cs <= CHUNK_BYTES + 1024 and pos + cs <= end):
            raise FormatError('Invalid compressed chunk size')
        comp = data[pos:pos + cs]
        if not len(comp) == cs:
            raise FormatError('Unexpected save structure')
        dec = zlib.decompressobj()
        raw = dec.decompress(comp, rs + 1)
        if not (dec.eof and (not dec.unused_data) and (not dec.unconsumed_tail)):
            raise FormatError('Unexpected save structure')
        if not (len(raw) == rs and 0 < rs <= CHUNK_BYTES):
            raise FormatError('Unexpected save structure')
        pos += cs
        if not pos <= end:
            raise FormatError('Unexpected save structure')
        chunks.append({'raw': raw, 'blob': data[begin:pos]})
    if not (pos == end and chunks and all((len(c['raw']) == CHUNK_BYTES for c in chunks[:-1]))):
        raise FormatError('Unexpected save structure')
    payload = b''.join((c['raw'] for c in chunks))
    if not struct.unpack_from('<I', payload)[0] == len(payload) - 4:
        raise FormatError('Payload length prefix mismatch')
    return (header, chunks, payload)

def rebuild(header, chunks, payload):
    blobs = []
    copied = 0
    for i, pos in enumerate(range(0, len(payload), CHUNK_BYTES)):
        raw = payload[pos:pos + CHUNK_BYTES]
        if i < len(chunks) and chunks[i]['raw'] == raw:
            blobs.append(chunks[i]['blob'])
            copied += 1
        else:
            comp = zlib.compress(raw, 6)
            pair = struct.pack('<QQ', len(comp), len(raw))
            blobs.append(CHUNK_MAGIC + struct.pack('<HIHB', 0, 2, 0, 3) + pair + pair + comp)
    body = b''.join(blobs)
    data = header + struct.pack('<I', len(body)) + body
    return (data + struct.pack('<I', zlib.crc32(data)), copied)

def root_properties(b):
    pp, end = properties(b, 4, len(b))
    if not (end == len(b) - 4 and b[end:] == b'\x00' * 4):
        raise FormatError('Unexpected save structure')
    if not len({x['name'] for x in pp}) == len(pp):
        raise FormatError('Unexpected save structure')
    return {x['name']: x for x in pp}

def children(b, parent):
    pp, end = properties(b, parent['data_start'], parent['end'])
    if not end == parent['end']:
        raise FormatError('Unexpected save structure')
    if not len({x['name'] for x in pp}) == len(pp):
        raise FormatError('Unexpected save structure')
    return {x['name']: x for x in pp}

def tag_entries(b, p):
    pos = p['data_start']
    count = struct.unpack_from('<I', b, pos)[0]
    pos += 4
    entries = []
    for _ in range(count):
        start = pos
        s, pos = fstr(b, pos)
        entries.append((s, b[start:pos]))
    if not (pos == p['end'] and len({s for s, _ in entries}) == len(entries)):
        raise FormatError('Unexpected save structure')
    return entries

def locate(b):
    r = root_properties(b)
    w = children(b, r['WorldState'])['WorldStateSavedData']
    q = children(b, r['QuestDirectorSaveData'])['QuestsTags']
    g = children(b, q)['GeneralTags']
    if not (w['type'] == 'StrProperty' and g['subtype'] == 'GameplayTagContainer'):
        raise FormatError('Unexpected save structure')
    return (r, w, q, g)

def data_blob(b, p, new_data):
    header = bytearray(b[p['start']:p['data_start']])
    offset = p['size_offset'] - p['start']
    if not struct.unpack_from('<I', header, offset)[0] == p['size']:
        raise FormatError('Unexpected save structure')
    struct.pack_into('<I', header, offset, len(new_data))
    return bytes(header) + new_data

def nested_replacement(b, chain, new_data):
    current = data_blob(b, chain[-1], new_data)
    for parent, child in reversed(list(zip(chain[:-1], chain[1:]))):
        if not parent['data_start'] <= child['start'] <= child['end'] <= parent['end']:
            raise FormatError('Unexpected save structure')
        parent_data = b[parent['data_start']:child['start']] + current + b[child['end']:parent['end']]
        current = data_blob(b, parent, parent_data)
    return current

def encode_fstr(s):
    if s.isascii():
        v = s.encode('ascii') + b'\0'
        return struct.pack('<i', len(v)) + v
    v = s.encode('utf-16le') + b'\0\0'
    return struct.pack('<i', -len(v)//2) + v
