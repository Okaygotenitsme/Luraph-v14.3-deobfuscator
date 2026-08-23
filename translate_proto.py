import sys

from proto_deserializer import Deserializer
from vm_opcode_table import OPCODES


def fmt_const(val):
    if val is None:
        return None
    if isinstance(val, tuple):
        kind, v = val
        if kind == 'string':
            try:
                return repr(v.decode('utf-8', errors='replace'))
            except Exception:
                return repr(v)
        if kind == 'unresolved_const':
            return f'<unresolved#{v}>'
        return repr(v)
    return repr(val)


def fmt_operand(label, val):
    if val is None:
        return None
    c = fmt_const(val) if isinstance(val, tuple) else None
    if c is not None:
        return f'{label}={c}'
    return f'{label}=r{val}'


def render_instruction(idx, opcode, Q, x, s, U, o, w):
    mnem = OPCODES.get(opcode, f'UNKNOWN_{opcode}')
    parts = []
    for label, val in (('Q', Q), ('x', x), ('s', s), ('U', U), ('o', o), ('w', w)):
        f = fmt_operand(label, val)
        if f is not None:
            parts.append(f)
    operand_str = ' '.join(parts)
    return f'{idx:>5}  {mnem:<20} {operand_str}'


def render_proto(proto, index=0):
    lines = [f'-- proto {index}  params={proto["numparams"]}  insns={len(proto["opcodes"])}']
    for i in range(len(proto['opcodes'])):
        line = render_instruction(
            i,
            proto['opcodes'][i],
            proto['operand_Q'][i],
            proto['operand_x'][i],
            proto['operand_s'][i],
            proto['operand_U'][i],
            proto['operand_o'][i],
            proto['operand_w'][i],
        )
        lines.append(line)
    return '\n'.join(lines)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    proto_index = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    with open(path, 'rb') as f:
        data = f.read()

    ds = Deserializer(data)
    ds.read_constant_pool()
    r_count = ds.read_upvalue_section()

    protos = []
    for i in range(r_count):
        protos.append(ds.read_proto())
    ds.apply_patches()

    if proto_index >= len(protos):
        print(f'proto index {proto_index} out of range (0..{len(protos)-1})')
        return

    print(render_proto(protos[proto_index], proto_index))


if __name__ == '__main__':
    main()
