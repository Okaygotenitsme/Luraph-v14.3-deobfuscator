import struct
import sys

TAG_STRING = 0x70
TAG_NUMBER = 0x0f
TAG_INT64 = 0x22
TAG_BOOL = 0x15


def read_varint(data, pos):
    result = 0
    shift = 0
    start = pos
    n = len(data)
    while pos < n:
        b = data[pos]
        result |= (b & 0x7f) << shift
        pos += 1
        if b & 0x80 == 0:
            break
        shift += 7
        if pos - start > 10:
            raise ValueError('varint too long at %d' % start)
    return result, pos


def parse_constants(data, start=4):
    entries = []
    i = start
    n = len(data)
    while i < n:
        tag = data[i]
        tag_start = i
        if tag == TAG_STRING:
            length, after_len = read_varint(data, i + 1)
            end = after_len + length
            if end > n:
                return entries, tag_start, 'string overrun'
            value = data[after_len:end]
            entries.append(('string', tag_start, value))
            i = end
        elif tag == TAG_NUMBER:
            end = i + 9
            if end > n:
                return entries, tag_start, 'number overrun'
            value = struct.unpack('<d', data[i + 1:end])[0]
            entries.append(('number', tag_start, value))
            i = end
        elif tag == TAG_INT64:
            end = i + 9
            if end > n:
                return entries, tag_start, 'int64 overrun'
            value = struct.unpack('<q', data[i + 1:end])[0]
            entries.append(('int64', tag_start, value))
            i = end
        elif tag == TAG_BOOL:
            end = i + 2
            if end > n:
                return entries, tag_start, 'bool overrun'
            value = bool(data[i + 1])
            entries.append(('bool', tag_start, value))
            i = end
        else:
            return entries, tag_start, 'unknown tag 0x%02x' % tag
    return entries, i, None


def dump(entries, limit=None):
    for kind, offset, value in (entries[:limit] if limit else entries):
        if kind == 'string':
            try:
                text = value.decode('utf-8')
            except UnicodeDecodeError:
                text = value
            if isinstance(text, str) and len(text) > 80:
                text = text[:80] + '...(%d bytes)' % len(value)
            print(f'{offset:>8} STRING  {text!r}')
        elif kind == 'number':
            print(f'{offset:>8} NUMBER  {value}')
        elif kind == 'int64':
            print(f'{offset:>8} INT64   {value}')
        elif kind == 'bool':
            print(f'{offset:>8} BOOL    {value}')


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    with open(in_path, 'rb') as f:
        data = f.read()

    entries, stop_offset, err = parse_constants(data)

    strings = [e for e in entries if e[0] == 'string']
    numbers = [e for e in entries if e[0] == 'number']
    int64s = [e for e in entries if e[0] == 'int64']
    bools = [e for e in entries if e[0] == 'bool']

    print(f'entries parsed: {len(entries)}  strings: {len(strings)}  numbers: {len(numbers)}  int64s: {len(int64s)}  bools: {len(bools)}')
    print(f'stopped at offset {stop_offset} of {len(data)}  reason: {err}')
    if err:
        print('context around stop:', data[max(0, stop_offset - 16):stop_offset + 32].hex())
    print('---')
    dump(entries, limit=60)
    print('--- last 20 ---')
    dump(entries[-20:])


if __name__ == '__main__':
    main()
