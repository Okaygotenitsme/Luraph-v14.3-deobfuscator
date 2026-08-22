import struct
import sys

TAG_STRING = 0x70
TAG_DOUBLE = 0x0f
TAG_INT64 = 0x22
TAG_BOOL = 0x15


def parse_constants(data):
    entries = []
    i = 0
    n = len(data)
    while i < n:
        tag = data[i]
        if tag == TAG_STRING:
            length = data[i + 1]
            value = data[i + 2:i + 2 + length]
            entries.append(('string', i, value))
            i = i + 2 + length
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
            print(f'{offset:>8} STRING  {text!r}')
        elif kind == 'double':
            print(f'{offset:>8} DOUBLE  {value}')
        elif kind == 'int64':
            print(f'{offset:>8} INT64   {value}')
        elif kind == 'bool':
            print(f'{offset:>8} BOOL    {value}')
        else:
            print(f'{offset:>8} BYTE    0x{value:02x}')


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    with open(in_path, 'rb') as f:
        data = f.read()
    entries = parse_constants(data)
    strings = [e for e in entries if e[0] == 'string']
    doubles = [e for e in entries if e[0] == 'double']
    int64s = [e for e in entries if e[0] == 'int64']
    bools = [e for e in entries if e[0] == 'bool']
    unknown = [e for e in entries if e[0] == 'unknown']
    print(f'total entries: {len(entries)}  strings: {len(strings)}  doubles: {len(doubles)}  int64s: {len(int64s)}  bools: {len(bools)}  unknown: {len(unknown)}')
    print('---')
    dump(entries, limit=200)


if __name__ == '__main__':
    main()
