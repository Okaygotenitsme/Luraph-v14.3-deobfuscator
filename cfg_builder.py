import sys
import json

from proto_deserializer import Deserializer
from vm_opcode_table import OPCODES


JUMP_UNCONDITIONAL = {119}
JUMP_CONDITIONAL = {2, 12, 26, 27, 28, 29, 39, 57, 73, 82, 89, 94, 98, 99, 103}


def is_control_flow(opcode):
    return opcode in JUMP_UNCONDITIONAL or opcode in JUMP_CONDITIONAL


def build_basic_blocks(proto):
    opcodes = proto['opcodes']
    n = len(opcodes)
    leaders = {0}

    for i, op in enumerate(opcodes):
        if is_control_flow(op):
            target = proto['operand_E'][i]
            if isinstance(target, int) and 0 <= target < n:
                leaders.add(target)
            if i + 1 < n:
                leaders.add(i + 1)

    sorted_leaders = sorted(leaders)
    blocks = []
    for idx, start in enumerate(sorted_leaders):
        end = sorted_leaders[idx + 1] if idx + 1 < len(sorted_leaders) else n
        blocks.append({'start': start, 'end': end})
    return blocks


def block_containing(blocks, index):
    for i, b in enumerate(blocks):
        if b['start'] <= index < b['end']:
            return i
    return -1


def build_cfg(proto, blocks):
    opcodes = proto['opcodes']
    edges = {i: [] for i in range(len(blocks))}

    for bi, b in enumerate(blocks):
        last_idx = b['end'] - 1
        if last_idx < 0 or last_idx >= len(opcodes):
            continue
        op = opcodes[last_idx]

        if op in JUMP_UNCONDITIONAL:
            target = proto['operand_E'][last_idx]
            if isinstance(target, int):
                tb = block_containing(blocks, target)
                if tb != -1:
                    edges[bi].append(('jmp', tb))
        elif op in JUMP_CONDITIONAL:
            target = proto['operand_E'][last_idx]
            if isinstance(target, int):
                tb = block_containing(blocks, target)
                if tb != -1:
                    edges[bi].append(('true', tb))
            if bi + 1 < len(blocks):
                edges[bi].append(('false', bi + 1))
        else:
            if bi + 1 < len(blocks):
                edges[bi].append(('fall', bi + 1))

    return edges


def classify_edges(blocks, edges):
    loop_edges = []
    forward_edges = []
    for bi, targets in edges.items():
        for kind, tb in targets:
            if blocks[tb]['start'] <= blocks[bi]['start']:
                loop_edges.append((bi, tb, kind))
            else:
                forward_edges.append((bi, tb, kind))
    return loop_edges, forward_edges


def render_summary(proto, blocks, edges, loop_edges, forward_edges):
    lines = []
    lines.append(f'basic blocks: {len(blocks)}')
    lines.append(f'backward edges (likely loops): {len(loop_edges)}')
    lines.append(f'forward edges (likely if/branch): {len(forward_edges)}')
    lines.append('')
    for bi, b in enumerate(blocks):
        targets = edges.get(bi, [])
        target_desc = ', '.join(f'{kind}->B{tb}' for kind, tb in targets)
        lines.append(f'B{bi:<4} [{b["start"]:>4}:{b["end"]:<4}]  {target_desc}')
    return '\n'.join(lines)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    proto_index = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    with open(path, 'rb') as f:
        data = f.read()

    ds = Deserializer(data)
    ds.read_constant_pool()
    r_count = ds.read_upvalue_section()
    protos = [ds.read_proto() for _ in range(r_count)]
    ds.apply_patches()

    proto = protos[proto_index]
    blocks = build_basic_blocks(proto)
    edges = build_cfg(proto, blocks)
    loop_edges, forward_edges = classify_edges(blocks, edges)

    print(render_summary(proto, blocks, edges, loop_edges, forward_edges))

    with open('vm_cfg.json', 'w') as f:
        json.dump({
            'blocks': blocks,
            'edges': {str(k): v for k, v in edges.items()},
            'loop_edges': loop_edges,
            'forward_edges': forward_edges,
        }, f, indent=2)
    print()
    print('wrote vm_cfg.json')


if __name__ == '__main__':
    main()
