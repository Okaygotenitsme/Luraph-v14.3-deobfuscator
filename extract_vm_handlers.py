import re
import sys
import json

from lua_lexer import tokenize, find_matching_end
from extract_vm_opcodes import find_vm_body, extract_opcode_comparisons
from extract_all_opcodes import extract_all_comparisons, infer_leaf_opcodes


def find_then_pos(body, cmp_pos):
    m = re.compile(r'\bthen\b').search(body, cmp_pos)
    if not m:
        return -1
    return m.end()


def find_block_end(body, then_pos):
    depth = 1
    for kind, text, pos in tokenize(body, then_pos):
        if kind != 'name':
            continue
        if text in ('function', 'for', 'while'):
            depth += 1
        elif text == 'if':
            depth += 1
        elif text in ('elseif', 'else'):
            if depth == 1:
                return pos
        elif text == 'end':
            depth -= 1
            if depth == 0:
                return pos
    return -1


def extract_eq_handlers(body, open_pos, comparisons):
    eq_comparisons = [(pos, val) for pos, op, val in comparisons if op == '==']
    ne_comparisons = [(pos, val) for pos, op, val in comparisons if op == '~=']

    handlers = []
    for pos, val in eq_comparisons + ne_comparisons:
        kind = 'eq'
        then_pos = find_then_pos(body, pos)
        if then_pos == -1:
            continue
        block_end = find_block_end(body, then_pos)
        if block_end == -1:
            continue
        snippet = body[then_pos:block_end]
        handlers.append({
            'opcode': val,
            'kind': kind,
            'source_offset': open_pos + then_pos,
            'length': len(snippet),
            'preview': snippet[:160]
        })
    return handlers


def extract_inferred_handlers(body, open_pos, comparisons, inferred):
    range_pat = re.compile(r'\bn(<|>=|<=|>)(0[xXbB][0-9a-fA-F_]+|[0-9][0-9_]*)\b')
    range_matches = []
    for m in range_pat.finditer(body):
        tok = m.group(2).replace('_', '')
        if re.match(r'^0[xX]', tok):
            v = int(tok, 16)
        elif re.match(r'^0[bB]', tok):
            v = int(tok, 2)
        else:
            v = int(tok)
        range_matches.append((m.start(), m.group(1), v))

    handlers = []
    for val in sorted(inferred):
        best = None
        for pos, op, v in range_matches:
            if op in ('>=', '>') and abs(v - val) <= 1 and v <= val:
                if best is None or pos > best[0]:
                    best = (pos, op, v)
        if best is None:
            continue
        pos = best[0]
        then_pos = find_then_pos(body, pos)
        if then_pos == -1:
            continue
        block_end = find_block_end(body, then_pos)
        if block_end == -1:
            continue
        snippet = body[then_pos:block_end]
        handlers.append({
            'opcode': val,
            'kind': 'inferred_range',
            'source_offset': open_pos + then_pos,
            'length': len(snippet),
            'preview': snippet[:160]
        })
    return handlers


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else 'sunjingwoo.lua'
    with open(src_path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        src = f.read()

    body, open_pos, end_pos = find_vm_body(src)
    comparisons = extract_opcode_comparisons(body, 'n')
    all_comparisons = extract_all_comparisons(body, 'n')
    known, inferred = infer_leaf_opcodes(all_comparisons)

    handlers = extract_eq_handlers(body, open_pos, comparisons)
    handlers += extract_inferred_handlers(body, open_pos, all_comparisons, inferred)

    handlers.sort(key=lambda h: h['opcode'])

    print(f'extracted {len(handlers)} handler blocks')
    for h in handlers:
        print(h['opcode'], h['kind'], h['length'], repr(h['preview']))

    with open('vm_handlers.json', 'w') as f:
        json.dump(handlers, f, indent=2)
    print('wrote vm_handlers.json')


if __name__ == '__main__':
    main()
