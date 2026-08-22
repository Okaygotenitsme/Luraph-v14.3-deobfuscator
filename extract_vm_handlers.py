import re
import sys
import json

from lua_lexer import tokenize, find_matching_end
from extract_vm_opcodes import find_vm_body, extract_opcode_comparisons


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


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else 'sunjingwoo.lua'
    with open(src_path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        src = f.read()

    body, open_pos, end_pos = find_vm_body(src)
    comparisons = extract_opcode_comparisons(body, 'n')

    eq_comparisons = [(pos, val) for pos, op, val in comparisons if op == '==']
    ne_comparisons = [(pos, val) for pos, op, val in comparisons if op == '~=']

    handlers = []
    for pos, val in eq_comparisons:
        then_pos = find_then_pos(body, pos)
        if then_pos == -1:
            continue
        block_end = find_block_end(body, then_pos)
        if block_end == -1:
            continue
        snippet = body[then_pos:block_end]
        handlers.append({
            'opcode': val,
            'kind': 'eq',
            'source_offset': open_pos + then_pos,
            'length': len(snippet),
            'preview': snippet[:120]
        })

    for pos, val in ne_comparisons:
        then_pos = find_then_pos(body, pos)
        if then_pos == -1:
            continue
        block_end = find_block_end(body, then_pos)
        if block_end == -1:
            continue
        snippet = body[then_pos:block_end]
        handlers.append({
            'opcode': val,
            'kind': 'ne',
            'source_offset': open_pos + then_pos,
            'length': len(snippet),
            'preview': snippet[:120]
        })

    handlers.sort(key=lambda h: h['opcode'])

    print(f'extracted {len(handlers)} handler blocks')
    for h in handlers:
        print(h['opcode'], h['kind'], h['length'], repr(h['preview']))

    with open('vm_handlers.json', 'w') as f:
        json.dump(handlers, f, indent=2)
    print('wrote vm_handlers.json')


if __name__ == '__main__':
    main()
