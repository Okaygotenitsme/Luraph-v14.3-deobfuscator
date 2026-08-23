import re
import sys

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
    return src[open_pos:end_pos], open_pos, end_pos


def extract_all_comparisons(body, varname='n'):
    pat = re.compile(
        r'\b' + re.escape(varname) + r'(==|~=|<=|>=|<|>)(0[xXbB][0-9a-fA-F_]+|[0-9][0-9_]*)\b'
    )
    results = []
    for m in pat.finditer(body):
        results.append((m.start(), m.group(1), normalize_number(m.group(2))))
    return results


def infer_leaf_opcodes(comparisons, opcode_min=0, opcode_max=200):
    known = set(v for _, op, v in comparisons if op in ('==', '~='))
    boundaries = sorted(set(v for _, op, v in comparisons))
    candidate = opcode_min
    inferred = set()
    all_boundary_set = set(boundaries)
    for v in range(opcode_min, opcode_max + 1):
        if v in known:
            continue
        lo_present = (v - 1) in all_boundary_set or (v - 1) in known
        hi_present = (v + 1) in all_boundary_set or (v + 1) in known
        if lo_present and hi_present:
            inferred.add(v)
    return known, inferred


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else 'sunjingwoo.lua'
    with open(src_path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        src = f.read()

    body, open_pos, end_pos = find_vm_body(src)
    comparisons = extract_all_comparisons(body, 'n')

    known, inferred = infer_leaf_opcodes(comparisons)

    print('explicit ==/~= opcode values:', len(known))
    print(sorted(known))
    print()
    print('inferred single-value leaves from tight boundaries:', len(inferred))
    print(sorted(inferred))
    print()
    combined = sorted(known | inferred)
    print('combined candidate opcode set:', len(combined))
    print(combined)


if __name__ == '__main__':
    main()
