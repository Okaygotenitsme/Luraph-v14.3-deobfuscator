import sys
from collections import Counter


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
            raise ValueError('varint too long')
    return result, pos


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 4065
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 5000

    with open(path, 'rb') as f:
        data = f.read()

    region = data[start:]
    vals = []
    lens = []
    i = 0
    n = len(region)
    while i < n and len(vals) < count:
        val, newpos = read_varint(region, i)
        vals.append(val)
        lens.append(newpos - i)
        i = newpos

    print('total varints parsed:', len(vals))
    print('total bytes consumed:', i)
    print('avg bytes/varint:', round(i / len(vals), 3))

    len_counter = Counter(lens)
    print('--- varint byte-length distribution ---')
    for length, cnt in sorted(len_counter.items()):
        print('length', length, 'count', cnt, 'pct', round(100 * cnt / len(lens), 1))

    val_counter = Counter(vals)
    print('--- top 20 most common values ---')
    for v, cnt in val_counter.most_common(20):
        print('value', v, 'count', cnt)

    print('--- first 40 values ---')
    print(vals[:40])


if __name__ == '__main__':
    main()
