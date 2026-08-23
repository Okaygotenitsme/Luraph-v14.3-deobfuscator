import struct
import sys

SP_BIAS = 0xD97D
OP_BIAS = 0x3C3A

TYPE_CONST = 4
TYPE_RAW = 3
TYPE_PATCH = 5


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


class Deserializer:
    def __init__(self, data):
        self.cur = Cursor(data)
        self.D = None
        self.wrap = False
        self.Pp = []
        self.H = {}

    def qp(self):
        return self.cur.uleb128()

    def read_constant_pool(self):
        raw = self.cur.uleb128()
        a = raw - SP_BIAS
        if a < 0 or a > 200000:
            raise ValueError(f'implausible constant count {a} (raw={raw}) at pos {self.cur.pos}')
        self.wrap = self.cur.u8() != 0
        pool = []
        for _ in range(a):
            tag = self.cur.u8()
            if tag > 0x15:
                if tag > 0x22:
                    val = self.cur.length_prefixed_string()
                    kind = 'string'
                else:
                    val = self.cur.i64()
                    kind = 'int'
            elif tag == 0x15:
                val = self.cur.u8() == 1
                kind = 'bool'
            else:
                val = self.cur.double()
                kind = 'number'
            pool.append((kind, val))
        self.D = pool
        return pool, self.wrap, a

    def _resolve(self, idx):
        if idx < len(self.D):
            return self.D[idx]
        return ('unresolved_const', idx)

    def read_upvalue_section(self):
        r_count = self.qp() - 0x2680
        if r_count < 0 or r_count > 200000:
            raise ValueError(f'implausible r-count {r_count} at pos {self.cur.pos}')
        return r_count

    def read_proto(self):
        numparams = self.qp()

        head_count = self.qp()
        x_head = [None] * head_count
        for o in range(head_count):
            w_id = self.qp()
            if w_id in self.H:
                x_head[o] = self.H[w_id]
            else:
                entry = (w_id // 4, w_id % 4)
                self.H[w_id] = entry
                x_head[o] = entry

        insn_count = self.qp() - OP_BIAS

        op = [None] * insn_count
        Q = [None] * insn_count
        x = [None] * insn_count
        s = [None] * insn_count
        U = [None] * insn_count
        o_arr = [None] * insn_count
        w_arr = [None] * insn_count

        for b in range(insn_count):
            l_val = self.qp()
            s_val = self.qp()
            z_val = self.qp()
            rp_val = self.qp()

            y_mod = z_val % 8
            d_val = l_val % 8
            c_val = rp_val % 8
            e_val = (rp_val - c_val) // 8
            a_val = (z_val - y_mod) // 8
            rp_final = (l_val - d_val) // 8

            o_arr[b] = e_val
            w_arr[b] = rp_final
            op[b] = s_val
            U[b] = a_val

            if c_val == TYPE_CONST:
                Q[b] = self._resolve(e_val)
            elif c_val == TYPE_RAW:
                o_arr[b] = e_val
            elif c_val == TYPE_PATCH:
                self.Pp.append((Q, b, e_val))

            if y_mod == TYPE_CONST:
                x[b] = self._resolve(a_val)
            elif y_mod == TYPE_RAW:
                U[b] = a_val
            elif y_mod == TYPE_PATCH:
                self.Pp.append((x, b, a_val))

            if d_val == TYPE_CONST:
                s[b] = self._resolve(rp_final)
            elif d_val == TYPE_RAW:
                w_arr[b] = rp_final
            elif d_val == TYPE_PATCH:
                self.Pp.append((s, b, rp_final))

        z = self._read_jump_table()

        proto = {
            'numparams': numparams,
            'opcodes': op,
            'operand_G': Q,
            'operand_l': x,
            'operand_Hp': s,
            'operand_E': U,
            'operand_S': o_arr,
            'operand_lp': w_arr,
            'jump_table': z,
            'nested_x_head': x_head,
        }
        return proto

    def apply_patches(self):
        applied = 0
        for target_array, index, const_idx in self.Pp:
            target_array[index] = self._resolve(const_idx)
            applied += 1
        self.Pp = []
        return applied

    def _read_jump_table(self):
        z = {}
        n = 0
        count = self.qp()
        for _ in range(count):
            w = self.qp()
            op = w // 2
            n += 1
            if w % 2 == 0:
                z[n] = op - op % 1
            else:
                s_val = self.qp()
                end_idx = self.qp()
                for o in range(op - op % 1, end_idx + 1):
                    z[o] = s_val
        return z


def dump_pool(pool, limit=None):
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

    ds = Deserializer(data)
    pool, wrap, count = ds.read_constant_pool()

    print(f'constant count: {count}  wrap-mode: {wrap}')
    print(f'cursor after const pool: byte {ds.cur.pos} of {len(data)}')
    print('--- constants (first 20) ---')
    dump_pool(pool, limit=20)

    print()
    print('--- upvalue/proto-count section ---')
    r_count = ds.read_upvalue_section()
    print('r_count (number of top-level protos):', r_count)
    print('cursor after r-count header:', ds.cur.pos)

    print()
    print('--- reading all top-level protos ---')
    protos = []
    for i in range(r_count):
        pos_before = ds.cur.pos
        try:
            proto = ds.read_proto()
            protos.append(proto)
            print(i, 'ok insns', len(proto['opcodes']), 'pos', pos_before, '->', ds.cur.pos)
        except Exception as ex:
            print(i, 'failed at', pos_before, ':', ex)
            break

    applied = ds.apply_patches()
    print()
    print('patches applied:', applied)

    if protos:
        first = protos[0]
        unresolved = sum(1 for v in first['operand_Q'] if isinstance(v, tuple) and v[0] == 'unresolved_const')
        unresolved += sum(1 for v in first['operand_x'] if isinstance(v, tuple) and v[0] == 'unresolved_const')
        unresolved += sum(1 for v in first['operand_s'] if isinstance(v, tuple) and v[0] == 'unresolved_const')
        print('proto0 remaining unresolved operand refs:', unresolved)


if __name__ == '__main__':
    main()
