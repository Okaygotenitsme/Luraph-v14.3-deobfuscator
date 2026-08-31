import sys

from proto_deserializer import Deserializer, OP_BIAS as OP_BIAS_DEFAULT


def read_raw_varint(data, pos):
    result = 0
    shift = 0
    start = pos
    while True:
        b = data[pos]
        result += (b & 0x7F) << shift
        shift += 7
        pos += 1
        if b < 0x80:
            break
    return result, pos


def try_full_parse(data, sp_bias, op_bias):
    ds = Deserializer(data, sp_bias=sp_bias, op_bias=op_bias)
    try:
        pool, wrap, count = ds.read_constant_pool()
        r_count = ds.read_upvalue_section()
        return count, r_count, pool
    except Exception as e:
        return None, None, str(e)


def is_plausible_pool(pool):
    string_count = 0
    for kind, val in pool:
        if kind == 'string':
            string_count += 1
            if len(val) > 200:
                return False
            try:
                text = val.decode('utf-8')
            except UnicodeDecodeError:
                return False
            printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
            if len(text) > 0 and printable / len(text) < 0.8:
                return False
    return string_count > 0


def brute_force_full(data, count_range=(1, 400), op_bias_search_range=(0, 5000)):
    raw_sp, pos_after = read_raw_varint(data, 0)

    sp_candidates = []
    for count in range(count_range[0], count_range[1]):
        sp_bias = raw_sp - count
        ds = Deserializer(data, sp_bias=sp_bias)
        try:
            pool, wrap, c = ds.read_constant_pool()
            if is_plausible_pool(pool):
                sp_candidates.append((sp_bias, c, ds.cur.pos))
        except Exception:
            continue

    good_combos = []
    for sp_bias, c, pos_after_pool in sp_candidates:
        raw_op, _ = read_raw_varint(data, pos_after_pool)

        for op_count in range(op_bias_search_range[0], op_bias_search_range[1]):
            op_bias = raw_op - op_count
            if op_bias < 0:
                continue
            ds2 = Deserializer(data, sp_bias=sp_bias, op_bias=op_bias)
            try:
                ds2.read_constant_pool()
                r_count = ds2.read_upvalue_section()
                if 1 <= r_count <= 500:
                    proto0 = ds2.read_proto()
                    if len(proto0['opcodes']) > 0:
                        good_combos.append((sp_bias, c, op_bias, r_count, len(proto0['opcodes'])))
            except Exception:
                continue

    return raw_sp, good_combos, len(sp_candidates)


def brute_force_bias(data, search_min=0, search_max=200000, step=1):
    ds = Deserializer(data)
    pool, wrap, count = ds.read_constant_pool()
    pos = ds.cur.pos
    raw, _ = read_raw_varint(data, pos)

    candidates = []
    for bias in range(search_min, search_max, step):
        val = raw - bias
        if 1 <= val <= 2000:
            candidates.append((bias, val))
    return raw, candidates


def find_bias_from_source(source_text, param_names, param_values):
    numeric_candidates = []
    for name, val in zip(param_names, param_values):
        try:
            v = int(float(val))
            if 100 < v < 100000:
                numeric_candidates.append((name, v))
        except (ValueError, TypeError):
            continue
    return numeric_candidates


def main():
    decoded_path = sys.argv[1] if len(sys.argv) > 1 else 'decoded_v2_16740.bin'

    with open(decoded_path, 'rb') as f:
        data = f.read()

    raw_sp, candidates, num_sp_candidates = brute_force_full(data, op_bias_search_range=(0, 60000))
    print(f'raw sp varint: {raw_sp}, sp_bias candidates that parsed a valid pool: {num_sp_candidates}')
    print(f'found {len(candidates)} (sp_bias, op_bias) combos producing plausible proto0')
    for sp_bias, count, op_bias, r_count, insns in candidates[:30]:
        print(f'  sp_bias={sp_bias} ({count} consts)  op_bias={op_bias} -> {r_count} protos, proto0 insns={insns}')


if __name__ == '__main__':
    main()
