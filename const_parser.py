import struct
import sys

TAG_STRING = 0x70
TAG_NUMBER = 0x0f


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
        elif tag == TAG_NUMBER:
            value = struct.unpack('<d', data[i + 1:i + 9])[0]
            entries.append(('number', i, value))
            i = i + 9
        else:
            entries.append(('unknown', i, tag))
            i += 1
    return entries


def dump(entries, limit=None):
    for kind, offset, value in entries[:limit] if limit else entries:
        if kind == 'string':
            try:
                text = value.decode('utf-8')
            except UnicodeDecodeError:
                text = value
            print(f'{offset:>8} STRING  {text!r}')
        elif kind == 'number':
            print(f'{offset:>8} NUMBER  {value}')
        else:
            print(f'{offset:>8} BYTE    0x{value:02x}')


if __name__ == '__main__':
    in_path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    with open(in_path, 'rb') as f:
        data = f.read()
    entries = parse_constants(data)
    strings = [e for e in entries if e[0] == 'string']
    numbers = [e for e in entries if e[0] == 'number']
    unknown = [e for e in entries if e[0] == 'unknown']
    print(f'total entries: {len(entries)}  strings: {len(strings)}  numbers: {len(numbers)}  unknown: {len(unknown)}')
    print('---')
    dump(entries)
