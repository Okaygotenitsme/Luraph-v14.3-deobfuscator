import sys
import json

from proto_deserializer import Deserializer
from cfg_builder import build_basic_blocks, build_cfg
from vm_opcode_table import OPCODES
from condition_table import render_condition
from expr_table import render_expr


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
        expr = render_expr(op, proto, i)
        if expr is not None:
            lines.append(f'{pad}{expr}')
        else:
            mnem = OPCODES.get(op, f'UNKNOWN_{op}')
            lines.append(f'{pad}{mnem}  -- insn {i}')
    return lines


def is_reachable_from(edges, start, target, reachable_cache=None):
    if reachable_cache is not None and start in reachable_cache:
        return target in reachable_cache[start]
    seen = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in seen:
            continue
        seen.add(node)
        for kind, tb in edges.get(node, []):
            stack.append(tb)
    return False


def find_irreducible_headers(n_blocks, edges, dom, reachable):
    preds = build_preds(n_blocks, edges)
    headers = {}
    for bi, targets in edges.items():
        if bi not in reachable:
            continue
        for kind, tb in targets:
            if tb not in reachable:
                continue
            if tb in dom.get(bi, set()):
                continue
            if not is_reachable_from(edges, tb, bi):
                continue
            if len(preds[tb]) <= 1:
                continue
            is_real_loop = any(
                bi in dom.get(p, set()) or tb in dom.get(p, set())
                for p in preds[tb] if p != bi
            )
            if is_real_loop:
                headers.setdefault(tb, set()).add(bi)
    return headers


def split_node(blocks, edges, preds, node, keep_pred, next_block_id):
    clone_id = next_block_id
    blocks.append(dict(blocks[node]))
    edges[clone_id] = list(edges.get(node, []))

    for p, targets in list(edges.items()):
        if p == keep_pred:
            new_targets = []
            for kind, tb in targets:
                if tb == node:
                    new_targets.append((kind, clone_id))
                else:
                    new_targets.append((kind, tb))
            edges[p] = new_targets

    preds[clone_id] = [keep_pred]
    preds[node] = [p for p in preds[node] if p != keep_pred]

    for kind, tb in edges[clone_id]:
        preds.setdefault(tb, [])
        if node in preds[tb] and clone_id not in preds[tb]:
            preds[tb].append(clone_id)

    return clone_id


def apply_limited_node_splitting(blocks, edges, dom, reachable, max_external_preds=2, max_total_splits=60):
    preds = build_preds(len(blocks), edges)
    next_id = len(blocks)
    total_splits = 0
    rounds = 0

    seen_targets = set()
    while total_splits < max_total_splits:
        rounds += 1
        headers = find_irreducible_headers(len(blocks), edges, dom, reachable)
        cheap = {h: eps for h, eps in headers.items() if 2 <= len(eps) <= max_external_preds and h not in seen_targets}
        if not cheap:
            break

        target, external_preds = next(iter(cheap.items()))
        seen_targets.add(target)
        external_preds = sorted(external_preds)
        for ep in external_preds[1:]:
            if total_splits >= max_total_splits:
                break
            split_node(blocks, edges, preds, target, ep, next_id)
            next_id += 1
            total_splits += 1

        n_blocks = len(blocks)
        dom, reachable = compute_dominators(n_blocks, preds, entry=0)

    return blocks, edges, dom, reachable, rounds, total_splits


def find_true_loop_header(node, preds, dom):
    candidates = [node] + [p for p in preds[node]]
    for c in candidates:
        others = [p for p in preds[node] if p != c]
        if all(c in dom.get(p, set()) or p == c for p in preds[node]):
            return c
    return node


def apply_targeted_splitting(blocks, edges, dom, reachable, max_rounds=30):
    preds = build_preds(len(blocks), edges)
    next_id = len(blocks)
    total_splits = 0

    for round_i in range(max_rounds):
        headers = find_irreducible_headers(len(blocks), edges, dom, reachable)
        if not headers:
            return blocks, edges, dom, reachable, total_splits, True

        progressed = False
        for node, external_preds in headers.items():
            true_header = find_true_loop_header(node, preds, dom)
            if true_header == node:
                for ep in external_preds:
                    split_node(blocks, edges, preds, node, ep, next_id)
                    next_id += 1
                    total_splits += 1
                progressed = True
                break

        if not progressed:
            return blocks, edges, dom, reachable, total_splits, False

        dom, reachable = compute_dominators(len(blocks), preds, entry=0)

    return blocks, edges, dom, reachable, total_splits, False


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
            cond_idx = blocks[bi]['end'] - 1
            cond_op = proto['opcodes'][cond_idx]
            cond_text = render_condition(cond_op, proto, cond_idx)
            out.append(f'    if {cond_text} then')
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


def find_loop_body(header, edges, dom, reachable):
    preds = build_preds(max(edges.keys(), default=0) + 1, edges)
    body = {header}
    stack = [p for p in preds[header] if header in dom.get(p, set())]
    while stack:
        node = stack.pop()
        if node in body:
            continue
        body.add(node)
        for p in preds[node]:
            if p not in body and header in dom.get(p, set()):
                stack.append(p)
    return body


def find_loop_exits(body, edges):
    exits = set()
    for node in body:
        for kind, tb in edges.get(node, []):
            if tb not in body:
                exits.add(tb)
    return exits


def emit_nested(proto, blocks, edges, dom, reachable, bi, indent, out, visited, stop_at=None, loop_headers_active=None):
    if loop_headers_active is None:
        loop_headers_active = set()

    while bi is not None and bi != stop_at:
        is_loop_header = any(
            tb == bi and bi in dom.get(src, set())
            for src, targets in edges.items()
            for kind, tb in targets
        )

        if is_loop_header and bi not in loop_headers_active:
            loop_headers_active = loop_headers_active | {bi}
            body = find_loop_body(bi, edges, dom, reachable)
            exits = find_loop_exits(body, edges)
            out.append('    ' * indent + f'while true do  -- B{bi}')
            body_visited = set(visited)
            emit_nested(proto, blocks, edges, dom, reachable, bi, indent + 1, out, body_visited, stop_at=None, loop_headers_active=loop_headers_active)
            visited.add(bi)
            visited |= body_visited
            out.append('    ' * indent + 'end')
            if len(exits) == 1:
                bi = next(iter(exits))
                continue
            elif len(exits) == 0:
                return None
            else:
                out.append('    ' * indent + f'-- multiple loop exits {sorted(exits)}, taking first')
                bi = sorted(exits)[0]
                continue

        if bi in visited:
            out.append('    ' * indent + f'-- already emitted B{bi} (merge point)')
            return None
        visited.add(bi)

        out.extend(render_block_body(proto, blocks[bi], indent, skip_last_jmp=True))

        targets = edges.get(bi, [])
        if not targets:
            out.append('    ' * indent + 'return')
            return None

        if len(targets) == 1:
            tb = targets[0][1]
            if tb in loop_headers_active:
                bi = None
                continue
            bi = tb
            if bi == stop_at:
                return None
            continue

        diamond = find_diamond(bi, edges)
        if diamond:
            true_b, false_b = diamond
            merge = find_merge_point(edges, true_b, false_b)
            cond_idx = blocks[bi]['end'] - 1
            cond_op = proto['opcodes'][cond_idx]
            cond_text = render_condition(cond_op, proto, cond_idx)
            out.append('    ' * indent + f'if {cond_text} then')
            emit_nested(proto, blocks, edges, dom, reachable, true_b, indent + 1, out, visited, stop_at=merge, loop_headers_active=loop_headers_active)
            out.append('    ' * indent + 'else')
            emit_nested(proto, blocks, edges, dom, reachable, false_b, indent + 1, out, visited, stop_at=merge, loop_headers_active=loop_headers_active)
            out.append('    ' * indent + 'end')
            bi = merge
            continue

        out.append('    ' * indent + f'-- unresolved multi-branch at B{bi}: {targets}')
        return None
    return bi


def find_merge_point(edges, a, b):
    def reachable_from(start):
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

    ra = reachable_from(a)
    rb = reachable_from(b)
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
    dom, reachable = compute_dominators(n_blocks, preds, entry=0)

    headers = find_irreducible_headers(n_blocks, edges, dom, reachable)
    next_id = len(blocks)
    total_splits = 0
    for h, eps in headers.items():
        for ep in eps:
            split_node(blocks, edges, preds, h, ep, next_id)
            next_id += 1
            total_splits += 1
    dom, reachable = compute_dominators(len(blocks), preds, entry=0)

    remaining = find_irreducible_headers(len(blocks), edges, dom, reachable)
    for h, eps in remaining.items():
        for ep in eps:
            split_node(blocks, edges, preds, h, ep, next_id)
            next_id += 1
            total_splits += 1
    dom, reachable = compute_dominators(len(blocks), preds, entry=0)

    print(f'node splitting: {total_splits} nodes cloned, blocks now {len(blocks)}')

    remaining = find_irreducible_headers(len(blocks), edges, dom, reachable)
    print(f'remaining irreducible headers (left as goto): {len(remaining)}')
    for h, eps in sorted(remaining.items()):
        print(f'  B{h} <- external preds {sorted(eps)}')

    loop_headers = find_natural_loop_headers(len(blocks), edges, dom, reachable)

    print(f'natural loop headers: {len(loop_headers)}')

    order = linear_order(len(blocks), entry=0)
    goto_out = emit_structured(proto, blocks, edges, loop_headers, order)
    goto_text = '\n'.join(goto_out)
    goto_count = goto_text.count('goto ')
    label_count = goto_text.count('::B')
    print(f'[goto mode] total lines: {len(goto_out)}, goto statements: {goto_count}, labels: {label_count}')

    with open('vm_structured_goto.txt', 'w') as f:
        f.write(goto_text)
    print('wrote vm_structured_goto.txt')

    nested_visited = set()
    nested_out = []
    emit_nested(proto, blocks, edges, dom, reachable, 0, 1, nested_out, nested_visited)
    nested_text = '\n'.join(nested_out)
    nested_goto_count = nested_text.count('goto ')
    print(f'[nested mode] total lines: {len(nested_out)}, remaining goto statements: {nested_goto_count}')

    with open('vm_structured_nested.txt', 'w') as f:
        f.write(nested_text)
    print('wrote vm_structured_nested.txt')

    print()
    print('--- nested preview ---')
    print(nested_text[:2000])


if __name__ == '__main__':
    main()
