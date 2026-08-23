import sys
import json

from proto_deserializer import Deserializer
from cfg_builder import build_basic_blocks, build_cfg
from vm_opcode_table import OPCODES


def compute_dominators(n_blocks, preds, entry=0):
    reachable = {entry}
    stack = [entry]
    succ = {i: [] for i in range(n_blocks)}
    for b in range(n_blocks):
        for p in preds[b]:
            succ[p].append(b)
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
    return dom


def build_preds(n_blocks, edges):
    preds = {i: [] for i in range(n_blocks)}
    for bi, targets in edges.items():
        for kind, tb in targets:
            preds[tb].append(bi)
    return preds


def find_natural_loops(n_blocks, edges, dom):
    loops = {}
    for bi, targets in edges.items():
        for kind, tb in targets:
            if tb in dom[bi] and kind in ('jmp', 'true'):
                header = tb
                body = set()
                stack = [bi]
                body.add(header)
                while stack:
                    node = stack.pop()
                    if node in body:
                        continue
                    body.add(node)
                    for p in build_preds(n_blocks, edges)[node]:
                        if p not in body:
                            stack.append(p)
                if header not in loops:
                    loops[header] = set()
                loops[header] |= body
    return loops


def find_diamond(bi, edges, blocks):
    targets = edges.get(bi, [])
    if len(targets) != 2:
        return None
    kinds = {k for k, _ in targets}
    if kinds != {'true', 'false'}:
        return None
    true_b = next(tb for k, tb in targets if k == 'true')
    false_b = next(tb for k, tb in targets if k == 'false')
    return true_b, false_b


def render_block_body(proto, block, indent):
    lines = []
    pad = '    ' * indent
    for i in range(block['start'], block['end']):
        op = proto['opcodes'][i]
        mnem = OPCODES.get(op, f'UNKNOWN_{op}')
        lines.append(f'{pad}{mnem}  -- insn {i}')
    return lines


def structure(proto, blocks, edges, loops, visited, bi, indent, out, stop_at=None):
    n_blocks = len(blocks)
    while bi is not None and bi != stop_at and bi < n_blocks:
        if bi in visited:
            out.append('    ' * indent + f'goto B{bi}')
            return
        if bi in loops:
            visited.add(bi)
            body_set = loops[bi]
            exit_targets = set()
            for node in body_set:
                for kind, tb in edges.get(node, []):
                    if tb not in body_set:
                        exit_targets.add(tb)
            out.append('    ' * indent + f'while true do  -- loop header B{bi}')
            structure(proto, blocks, edges, loops, visited, bi, indent + 1, out, stop_at=None)
            out.append('    ' * indent + 'end')
            if len(exit_targets) == 1:
                bi = next(iter(exit_targets))
                continue
            else:
                return
        visited.add(bi)
        out.extend(render_block_body(proto, blocks[bi], indent))

        diamond = find_diamond(bi, edges, blocks)
        if diamond:
            true_b, false_b = diamond
            out.append('    ' * indent + f'if <cond from B{bi}> then')
            merge = find_merge_point(edges, true_b, false_b, n_blocks)
            structure(proto, blocks, edges, loops, visited, true_b, indent + 1, out, stop_at=merge)
            out.append('    ' * indent + 'else')
            structure(proto, blocks, edges, loops, visited, false_b, indent + 1, out, stop_at=merge)
            out.append('    ' * indent + 'end')
            bi = merge
            continue

        targets = edges.get(bi, [])
        if len(targets) == 1:
            bi = targets[0][1]
            continue
        elif len(targets) == 0:
            return
        else:
            out.append('    ' * indent + f'-- unresolved branch at B{bi}: {targets}')
            return


def find_merge_point(edges, a, b, n_blocks):
    def reachable(start):
        seen = set()
        stack = [start]
        order = []
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            order.append(node)
            for kind, tb in edges.get(node, []):
                stack.append(tb)
        return seen

    ra = reachable(a)
    rb = reachable(b)
    common = ra & rb
    if not common:
        return None
    return min(common)


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
    dom = compute_dominators(n_blocks, preds, entry=0)
    loops = find_natural_loops(n_blocks, edges, dom)

    print(f'detected {len(loops)} natural loop headers')
    print(sorted(loops.keys())[:20])
    print()

    out = []
    visited = set()
    structure(proto, blocks, edges, loops, visited, 0, 0, out)

    text = '\n'.join(out)
    print(text[:3000])

    with open('vm_structured.txt', 'w') as f:
        f.write(text)
    print()
    print('wrote vm_structured.txt, total lines:', len(out))
    print('blocks visited:', len(visited), 'of', n_blocks)


if __name__ == '__main__':
    main()
