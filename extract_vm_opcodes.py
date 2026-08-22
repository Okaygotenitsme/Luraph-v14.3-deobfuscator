import re
import sys
from collections import Counter

from lua_lexer import find_matching_end


def normalize_number(tok):
    tok = tok.replace('_', '')
    if re.match(r'^0[xX]', tok):
        return int(tok, 16)
    if re.match(r'^0[bB]', tok):
        return int(tok, 2)
    return int(tok)


def find_vm_body(src, marker='local Z,Rp,C,dp=B(function()'):
    start = src.index(marker)
    open_pos = start + len(marker)
    end_pos = find_matching_end(src, open_pos)
    if end_pos == -1:
        raise ValueError('could not find matching end for VM function')
    return src[open_pos:end_pos], open_pos, end_pos


def extract_opcode_comparisons(body, varname='n'):
    pat = re.compile(
        r'\b' + re.escape(varname) + r'(==|~=|<=|>=|<|>)(0[xXbB][0-9a-fA-F_]+|[0-9][0-9_]*)\b'
    )
    results = []
    for m in pat.finditer(body):
        op, tok = m.group(1), m.group(2)
        val = normalize_number(tok)
        results.append((m.start(), op, val))
    return results


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else 'sunjingwoo.lua'
    with open(src_path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        src = f.read()

    body, open_pos, end_pos = find_vm_body(src)
    print(f'VM body: [{open_pos}, {end_pos}) length={len(body)}')

    comparisons = extract_opcode_comparisons(body, 'n')
    print(f'total n-comparisons: {len(comparisons)}')

    op_counter = Counter(op for _, op, _ in comparisons)
    print('by operator:', dict(op_counter))

    eq_values = sorted(set(v for _, op, v in comparisons if op == '=='))
    ne_values = sorted(set(v for _, op, v in comparisons if op == '~='))
    range_values = sorted(set(v for _, op, v in comparisons if op in ('<', '>', '<=', '>=')))

    print(f'\n== leaf opcode values (direct handlers): {len(eq_values)}')
    print(eq_values)

    print(f'\n~= values (negative-match handlers): {len(ne_values)}')
    print(ne_values)

    print(f'\ncomparison-tree boundary values (range splits): {len(range_values)}')
    print(range_values)

    all_opcode_values = sorted(set(eq_values) | set(ne_values))
    print(f'\ntotal distinct opcode values referenced: {len(all_opcode_values)}')
    print(all_opcode_values)

    out_path = 'vm_opcode_comparisons.txt'
    with open(out_path, 'w') as f:
        for pos, op, val in comparisons:
            f.write(f'{pos}\t{op}\t{val}\n')
    print(f'\nwrote {len(comparisons)} raw comparisons to {out_path}')


if __name__ == '__main__':
    main()
