import sys
import os

from proto_deserializer import Deserializer
from cfg_builder import build_basic_blocks, build_cfg
from vm_opcode_table import OPCODES
from expr_table import EXPR_TEMPLATES
from structure_cfg import (
    build_preds,
    compute_dominators,
    find_irreducible_headers,
    split_node,
    find_natural_loop_headers,
    linear_order,
    emit_structured,
    emit_nested,
)


def process_proto(proto, index, out_dir):
    blocks = build_basic_blocks(proto)
    edges = build_cfg(proto, blocks)
    n_blocks = len(blocks)

    if n_blocks == 0 or len(proto['opcodes']) == 0:
        return {
            'index': index, 'insns': 0, 'blocks': 0, 'skipped': True,
        }

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
    remaining = find_irreducible_headers(len(blocks), edges, dom, reachable)

    loop_headers = find_natural_loop_headers(len(blocks), edges, dom, reachable)

    order = linear_order(len(blocks), entry=0)
    goto_out = emit_structured(proto, blocks, edges, loop_headers, order)
    goto_text = '\n'.join(goto_out)

    nested_out = []
    emit_nested(proto, blocks, edges, dom, reachable, 0, 1, nested_out, set())
    nested_text = '\n'.join(nested_out)

    with open(os.path.join(out_dir, f'proto_{index}_goto.txt'), 'w') as f:
        f.write(goto_text)
    with open(os.path.join(out_dir, f'proto_{index}_nested.txt'), 'w') as f:
        f.write(nested_text)

    covered = sum(1 for op in proto['opcodes'] if op in EXPR_TEMPLATES or OPCODES.get(op, '').startswith(('JMP', 'TEST', 'LE', 'EQ', 'LT', 'CMP')))
    total_insns = len(proto['opcodes'])
    coverage_pct = (100 * covered / total_insns) if total_insns else 100.0

    return {
        'index': index,
        'insns': total_insns,
        'blocks': n_blocks,
        'blocks_after_split': len(blocks),
        'splits': total_splits,
        'remaining_irreducible': len(remaining),
        'goto_count': goto_text.count('goto '),
        'nested_goto_count': nested_text.count('goto '),
        'expr_coverage_pct': round(coverage_pct, 1),
        'skipped': False,
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'decoded.bin'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'proto_output'
    os.makedirs(out_dir, exist_ok=True)

    with open(path, 'rb') as f:
        data = f.read()

    ds = Deserializer(data)
    ds.read_constant_pool()
    r_count = ds.read_upvalue_section()
    protos = [ds.read_proto() for _ in range(r_count)]
    ds.apply_patches()

    print(f'processing {len(protos)} top-level protos')
    print()

    results = []
    for i, proto in enumerate(protos):
        try:
            r = process_proto(proto, i, out_dir)
        except Exception as e:
            r = {'index': i, 'insns': len(proto['opcodes']), 'error': str(e), 'skipped': True}
        results.append(r)
        if r.get('skipped') and 'error' not in r:
            print(f'proto {i}: empty, skipped')
        elif 'error' in r:
            print(f'proto {i}: ERROR - {r["error"]}')
        else:
            print(f'proto {i}: {r["insns"]} insns, {r["blocks"]}->{r["blocks_after_split"]} blocks, '
                  f'{r["splits"]} splits, {r["remaining_irreducible"]} irreducible left, '
                  f'goto={r["goto_count"]}, nested_goto={r["nested_goto_count"]}, '
                  f'expr_coverage={r["expr_coverage_pct"]}%')

    print()
    non_empty = [r for r in results if not r.get('skipped') and 'error' not in r]
    total_insns = sum(r['insns'] for r in non_empty)
    total_irreducible = sum(r['remaining_irreducible'] for r in non_empty)
    total_nested_goto = sum(r['nested_goto_count'] for r in non_empty)
    errors = sum(1 for r in results if 'error' in r)
    avg_coverage = sum(r['expr_coverage_pct'] for r in non_empty) / len(non_empty) if non_empty else 0

    print(f'summary: {len(non_empty)} non-empty protos, {total_insns} total instructions')
    print(f'remaining irreducible headers across all protos: {total_irreducible}')
    print(f'remaining goto in nested mode across all protos: {total_nested_goto}')
    print(f'average expression coverage: {avg_coverage:.1f}%')
    print(f'protos with errors: {errors}')


if __name__ == '__main__':
    main()
