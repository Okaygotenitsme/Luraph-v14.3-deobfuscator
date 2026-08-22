import struct
import sys

TAG_STRING = 0x70
TAG_DOUBLE = 0x0f
TAG_INT64 = 0x22
TAG_BOOL = 0x15


def read_varint(data, pos):
    result = 0
    shift = 0
    start = pos
    while True:
        b = data[pos]
        result |= (b & 0x7f) << shift
        pos += 1
        if b & 0x80 == 0:
            break
        shift += 7
        if pos - start > 10:
            raise ValueError('varint too long at %d' % start)
    return result, pos


def parse_constants(data):
    entries = []
    i = 0
    n = len(data)
    while i < n:
        tag = data[i]
        if tag == TAG_STRING:
            length, after_len = read_varint(data, i + 1)
            value = data[after_len:after_len + length]
            entries.append(('string', i, value))
            i = after_len + length
        elif tag == TAG_DOUBLE:
            value = struct.unpack('<d', data[i + 1:i + 9])[0]
            entries.append(('double', i, value))
            i = i + 9
        elif tag == TAG_INT64:
            value = struct.unpack('<q', data[i + 1:i + 9])[0]
            entries.append(('int64', i, value))
            i = i + 9
        elif tag == TAG_BOOL:
            value = data[i + 1]
            entries.append(('bool', i, bool(value)))
            i = i + 2
        else:
            entries.append(('unknown', i, tag))
            i += 1
    return entries


def dump(entries, limit=None):
    for entry in (entries[:limit] if limit else entries):
        kind, offset, value = entry
        if kind == 'string':
            try:
                text = value.decode('utf-8')
            except UnicodeDecodeError:
                text = value
            if len(repr(text)) > 120:
                text = text[:100] if isinstance(text, str) else text[:100]
                print(f'{offset:>8} STRING  {text!r}... (truncated)')
            else:
                print(f'{offset:>8} STRING  {text!r}')
        elif kind == 'double':
            print(f'{offset:>8} DOUBLE  {value}')
        elif kind == 'int64':
            print(f'{offset:>8} INT64   {value}')
        elif kind == 'bool':
            print(f'{offset:>8} BOOL    {value}')
        else:
            print(f'{offset:>8} BYTE    0x{value:02x}')


def parse_header(data):
    magic = data[0:4]
    return {
        'raw': magic,
        'byte0': magic[0],
        'byte1': magic[1],
        'byte2': magic[2],
        'byte3': magic[3],
    }


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    with open(in_path, 'rb') as f:
        data = f.read()

    header = parse_header(data)
    print('header (4 bytes):', header['raw'].hex())

    body = data[4:]
    entries = parse_constants(body)

    strings = [e for e in entries if e[0] == 'string']
    doubles = [e for e in entries if e[0] == 'double']
    int64s = [e for e in entries if e[0] == 'int64']
    bools = [e for e in entries if e[0] == 'bool']
    unknown = [e for e in entries if e[0] == 'unknown']

    print(f'total entries: {len(entries)}  strings: {len(strings)}  doubles: {len(doubles)}  int64s: {len(int64s)}  bools: {len(bools)}  unknown: {len(unknown)}')

    if unknown:
        first_unknown_offset = unknown[0][1]
        print('first unknown byte at body offset:', first_unknown_offset, '-> absolute offset:', first_unknown_offset + 4)
        print('constant pool ends here; remainder is likely instruction stream')

    print('---')
    dump(entries, limit=300)


if __name__ == '__main__':
    main()
