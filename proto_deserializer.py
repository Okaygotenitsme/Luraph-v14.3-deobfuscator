import struct
import sys

SP_BIAS = 0xD97D


class Cursor:
    def __init__(self, data, pos=0):
        self.data = data
        self.pos = pos

    def u8(self):
        b = self.data[self.pos]
        self.pos += 1
        return b

    def uleb128(self):
        result = 0
        shift = 0
        while True:
            b = self.data[self.pos]
            self.pos += 1
            result |= (b & 0x7F) << shift
            if b & 0x80 == 0:
                break
            shift += 7
        return result

    def double(self):
        val = struct.unpack_from('<d', self.data, self.pos)[0]
        self.pos += 8
        return val

    def i64(self):
        val = struct.unpack_from('<q', self.data, self.pos)[0]
        self.pos += 8
        return val

    def length_prefixed_string(self):
        n = self.uleb128()
        s = self.data[self.pos:self.pos + n]
        self.pos += n
        return s


def read_constant_pool(cur):
    raw = cur.uleb128()
    a = raw - SP_BIAS
    if a < 0 or a > 200000:
        raise ValueError(f'implausible constant count {a} (raw={raw}) at pos {cur.pos}')
    wrap = cur.u8() != 0
    pool = []
    for _ in range(a):
        tag = cur.u8()
        if tag > 0x15:
            if tag > 0x22:
                val = cur.length_prefixed_string()
                kind = 'string'
            else:
                val = cur.i64()
                kind = 'int'
        elif tag == 0x15:
            val = cur.u8() == 1
            kind = 'bool'
        else:
            val = cur.double()
            kind = 'number'
        pool.append((kind, val))
    return pool, wrap, a


def dump(pool, limit=None):
    for i, (kind, val) in enumerate(pool[:limit] if limit else pool):
        if kind == 'string':
            try:
                text = val.decode('utf-8')
            except UnicodeDecodeError:
                text = val
            if isinstance(text, str) and len(text) > 90:
                text = text[:90] + f'...({len(val)}b)'
            print(f'{i:>4} STRING  {text!r}')
        else:
            print(f'{i:>4} {kind.upper():<7} {val}')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    with open(path, 'rb') as f:
        data = f.read()

    cur = Cursor(data)
    pool, wrap, count = read_constant_pool(cur)

    print(f'constant count: {count}  wrap-mode: {wrap}')
    print(f'cursor after const pool: byte {cur.pos} of {len(data)}')
    print('--- constants ---')
    dump(pool)

    print('--- next 64 bytes after const pool ---')
    print(data[cur.pos:cur.pos + 64].hex())


if __name__ == '__main__':
    main()
