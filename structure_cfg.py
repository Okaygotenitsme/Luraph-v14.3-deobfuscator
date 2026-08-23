import sys
import json

from proto_deserializer import Deserializer
from cfg_builder import build_basic_blocks, build_cfg
from vm_opcode_table import OPCODES


def build_preds(n_blocks, edges):
    preds = {i: [] for i in range(n_blocks)}
    for bi, targets in edges.items():
        for kind, tb in targets:
            preds[tb].append(bi)
    return preds


def compute_dominators(n_blocks, preds, entry=0):
    succ = {i: [] for i in range(n_blocks)}
    for b in range(n_blocks):
        for p in preds[b]:
            succ[p].append(b)

    reachable = {entry}
    stack = [entry]
    while stack:
        node = stack.pop()
        for nxt in succ[node]:
            if nxt not in reachable:
                reachable.add(nxt)
                stack.append(nxt)

    dom = {}
    for b in range(n_blocks):
        dom[b] = set(reachable) if b in reachable else set()
    dom[entry] = {entry}

    changed = True
    while changed:
        changed = False
        for b in reachable:
            if b == entry:
                continue
            real_preds = [p for p in preds[b] if p in reachable]
            if not real_preds:
                continue
            new_dom = None
            for p in real_preds:
                if new_dom is None:
                    new_dom = set(dom[p])
                else:
                    new_dom &= dom[p]
            if new_dom is None:
                new_dom = set()
            new_dom.add(b)
            if new_dom != dom[b]:
                dom[b] = new_dom
                changed = True
    return dom, reachable


def find_natural_loop_headers(n_blocks, edges, dom, reachable):
    preds = build_preds(n_blocks, edges)
    headers = set()
    for bi, targets in edges.items():
        if bi not in reachable:
            continue
        for kind, tb in targets:
            if tb not in reachable:
                continue
            if tb in dom[bi]:
                headers.add(tb)
    return headers


def find_diamond(bi, edges):
    targets = edges.get(bi, [])
    if len(targets) != 2:
        return None
    kinds = {k for k, _ in targets}
    if kinds != {'true', 'false'}:
        return None
    true_b = next(tb for k, tb in targets if k == 'true')
    false_b = next(tb for k, tb in targets if k == 'false')
    return true_b, false_b


def render_block_body(proto, block, indent, skip_last_jmp=False):
    lines = []
    pad = '    ' * indent
    end = block['end']
    if skip_last_jmp and end > block['start']:
        last_op = proto['opcodes'][end - 1]
        if OPCODES.get(last_op) in ('JMP',) or 'JMP' in OPCODES.get(last_op, '') or 'TEST' in OPCODES.get(last_op, ''):
            end -= 1
    for i in range(block['start'], end):
        op = proto['opcodes'][i]
        mnem = OPCODES.get(op, f'UNKNOWN_{op}')
        lines.append(f'{pad}{mnem}  -- insn {i}')
    return lines


def linear_order(n_blocks, entry=0):
    return list(range(n_blocks))


def emit_structured(proto, blocks, edges, loop_headers, order):
    out = []
    emitted = set()
    labels_needed = set()

    for bi, targets in edges.items():
        for kind, tb in targets:
            idx_bi = order.index(bi) if bi in order else -1
            idx_tb = order.index(tb) if tb in order else -1
            if idx_tb <= idx_bi:
                labels_needed.add(tb)
            elif kind in ('true', 'false') and idx_tb != idx_bi + 1:
                labels_needed.add(tb)

    for pos, bi in enumerate(order):
        if bi in loop_headers:
            out.append(f'::B{bi}::  -- loop header')
        elif bi in labels_needed:
            out.append(f'::B{bi}::')

        out.extend(render_block_body(proto, blocks[bi], 1, skip_last_jmp=True))

        targets = edges.get(bi, [])
        if not targets:
            out.append('    return')
            continue

        if len(targets) == 1:
            kind, tb = targets[0]
            next_bi = order[pos + 1] if pos + 1 < len(order) else None
            if tb != next_bi:
                out.append(f'    goto B{tb}')
            continue

        diamond = find_diamond(bi, edges)
        if diamond:
            true_b, false_b = diamond
            next_bi = order[pos + 1] if pos + 1 < len(order) else None
            out.append(f'    if <cond from B{bi}> then')
            if true_b != next_bi:
                out.append(f'        goto B{true_b}')
            else:
                out.append(f'        -- falls through to B{true_b}')
            out.append('    else')
            if false_b != next_bi:
                out.append(f'        goto B{false_b}')
            else:
                out.append(f'        -- falls through to B{false_b}')
            out.append('    end')
            continue

        out.append(f'    -- unresolved multi-branch at B{bi}: {targets}')

    return out


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
    n_blocks = len(blocks)

    preds = build_preds(n_blocks, edges)
    dom, reachable = compute_dominators(n_blocks, preds, entry=0)
    loop_headers = find_natural_loop_headers(n_blocks, edges, dom, reachable)

    print(f'blocks: {n_blocks}, reachable: {len(reachable)}')
    print(f'natural loop headers: {len(loop_headers)}')

    order = linear_order(n_blocks, entry=0)
    out = emit_structured(proto, blocks, edges, loop_headers, order)

    text = '\n'.join(out)
    goto_count = text.count('goto ')
    label_count = text.count('::B')
    print(f'total lines: {len(out)}, goto statements: {goto_count}, labels: {label_count}')

    with open('vm_structured.txt', 'w') as f:
        f.write(text)
    print('wrote vm_structured.txt')
    print()
    print(text[:2000])


if __name__ == '__main__':
    main()
