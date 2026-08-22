import struct
import sys
from collections import Counter

TAG_STRING = 0x70
TAG_NUMBER = 0x0f


def find_valid_records(data):
    n = len(data)
    found = []
    i = 0
    while i < n - 9:
        tag = data[i]
        if tag == TAG_STRING:
            length = data[i + 1]
            end = i + 2 + length
            if end <= n and length < 200:
                chunk = data[i + 2:end]
                printable = sum(1 for b in chunk if 32 <= b < 127)
                if length == 0 or printable / length > 0.9:
                    found.append((i, end, 'string', chunk))
        elif tag == TAG_NUMBER:
            end = i + 9
            if end <= n:
                val = struct.unpack('<d', data[i + 1:end])[0]
                if val == val and abs(val) < 1e15:
                    found.append((i, end, 'number', val))
        i += 1
    return found


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    with open(in_path, 'rb') as f:
        data = f.read()

    found = find_valid_records(data)
    print('candidate valid records (overlap-permitting scan):', len(found))

    found_sorted = sorted(found, key=lambda x: x[0])
    non_overlapping = []
    last_end = -1
    for start, end, kind, val in found_sorted:
        if start >= last_end:
            non_overlapping.append((start, end, kind, val))
            last_end = end

    print('non-overlapping records:', len(non_overlapping))

    gaps = []
    for a, b in zip(non_overlapping, non_overlapping[1:]):
        gap = b[0] - a[1]
        gaps.append(gap)

    counter = Counter(gaps)
    print('--- gap size distribution (top 20) ---')
    for gap, count in counter.most_common(20):
        print('gap', gap, 'count', count)

    print('--- sample records with gaps ---')
    for idx in range(min(40, len(non_overlapping) - 1)):
        a = non_overlapping[idx]
        b = non_overlapping[idx + 1]
        gap = b[0] - a[1]
        gap_bytes = data[a[1]:b[0]]
        print(a[0], a[2], repr(a[3])[:30], '| gap', gap, gap_bytes.hex())


if __name__ == '__main__':
    main()
