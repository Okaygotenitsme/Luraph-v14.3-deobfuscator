import re
import sys
import json

from lua_lexer import tokenize, find_matching_end
from extract_vm_opcodes import find_vm_body


NUM_RE = re.compile(r'^(0[xX][0-9a-fA-F_]+|0[bB][01_]+|[0-9][0-9_]*)$')


def parse_num(tok):
    tok = tok.replace('_', '')
    if re.match(r'^0[xX]', tok):
        return int(tok, 16)
    if re.match(r'^0[bB]', tok):
        return int(tok, 2)
    return int(tok)


def find_matching_control(body, pos, open_kw):
    depth = 1
    branches = []
    for kind, text, tpos in tokenize(body, pos):
        if kind != 'name':
            continue
        if text in ('function', 'for', 'while', 'if'):
            depth += 1
        elif text == 'end':
            depth -= 1
            if depth == 0:
                return branches, tpos
        elif text in ('elseif', 'else') and depth == 1:
            branches.append(tpos)
    return branches, -1


def parse_condition(cond_text):
    m = re.match(r'^\s*n(==|~=|<=|>=|<|>)(0[xXbB][0-9a-fA-F_]+|[0-9][0-9_]*)\s*$', cond_text)
    if m:
        return m.group(1), parse_num(m.group(2))
    m = re.match(r'^\s*not\(n(==|~=|<=|>=|<|>)(0[xXbB][0-9a-fA-F_]+|[0-9][0-9_]*)\)\s*$', cond_text)
    if m:
        op = m.group(1)
        inv = {'==': '~=', '~=': '==', '<': '>=', '>=': '<', '<=': '>', '>': '<='}
        return inv[op], parse_num(m.group(2))
    return None, None


def apply_constraint(range_set, op, val):
    if op == '==':
        return range_set & {val}
    if op == '~=':
        return range_set - {val}
    if op == '<':
        return {v for v in range_set if v < val}
    if op == '<=':
        return {v for v in range_set if v <= val}
    if op == '>':
        return {v for v in range_set if v > val}
    if op == '>=':
        return {v for v in range_set if v >= val}
    return range_set


def walk(body, if_pos, then_pos, live_range, results, opcode_min=0, opcode_max=130):
    cond_text = body[if_pos:then_pos].rsplit('then', 1)[0].strip()
    if cond_text.startswith('elseif'):
        cond_text = cond_text[6:]
    elif cond_text.startswith('if'):
        cond_text = cond_text[2:]
    op, val = parse_condition(cond_text.strip())

    if op is not None:
        true_range = apply_constraint(set(live_range), op, val)
    else:
        true_range = set(live_range)

    branches, end_pos = find_matching_control(body, then_pos, 'if')

    segment_starts = [then_pos] + branches
    segment_ends = branches + [end_pos]

    remaining = set(live_range)

    for seg_i, (seg_start, seg_end) in enumerate(zip(segment_starts, segment_ends)):
        if seg_i == 0:
            seg_range = true_range
            remaining -= true_range
        else:
            kw_match = re.match(r'\s*(elseif|else)\s*', body[seg_start:seg_start + 20])
            kw = kw_match.group(1) if kw_match else None
            if kw == 'else':
                seg_range = remaining
                inner_then = seg_start + kw_match.end() - kw_match.end() + len('else')
                process_segment(body, seg_start + len('else'), seg_end, seg_range, results, opcode_min, opcode_max)
                continue
            else:
                cond_start = seg_start + len('elseif')
                then_m = re.compile(r'\bthen\b').search(body, cond_start)
                if not then_m:
                    continue
                sub_cond = body[cond_start:then_m.start()].strip()
                sop, sval = parse_condition(sub_cond)
                if sop is not None:
                    seg_range = apply_constraint(remaining, sop, sval)
                else:
                    seg_range = set(remaining)
                remaining -= seg_range
                process_segment(body, then_m.end(), seg_end, seg_range, results, opcode_min, opcode_max)
                continue

        process_segment(body, seg_start, seg_end, seg_range, results, opcode_min, opcode_max)


def process_segment(body, start, end, live_range, results, opcode_min, opcode_max):
    if not live_range:
        return
    segment = body[start:end]
    m = re.match(r'\s*if\b', segment)
    if m:
        if_pos = start + m.start()
        if_kw_end = start + m.end()
        then_m = re.compile(r'\bthen\b').search(body, if_pos)
        if then_m and then_m.start() < end:
            cond_text = body[if_kw_end:then_m.start()].strip()
            op, val = parse_condition(cond_text)
            if op is not None:
                walk(body, if_pos, then_m.end(), live_range, results, opcode_min, opcode_max)
                return
    live_range = {v for v in live_range if opcode_min <= v <= opcode_max}
    if not live_range:
        return
    results.append({
        'values': sorted(live_range),
        'source_offset': start,
        'length': end - start,
        'preview': segment.strip()[:160],
    })


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else 'sunjingwoo.lua'
    with open(src_path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        src = f.read()

    body, open_pos, end_pos = find_vm_body(src)

    top_if = body.index('if n<0X3D then')
    then_m = re.compile(r'\bthen\b').search(body, top_if)

    results = []
    full_range = set(range(0, 130))
    walk(body, top_if, then_m.end(), full_range, results)

    value_to_result = {}
    for r in results:
        for v in r['values']:
            if v not in value_to_result:
                value_to_result[v] = r

    covered = sorted(value_to_result.keys())
    print('total leaf segments:', len(results))
    print('total distinct opcode values covered:', len(covered))
    print(covered)

    with open('vm_full_dispatch.json', 'w') as f:
        json.dump({
            'segments': results,
            'value_to_offset': {str(v): value_to_result[v]['source_offset'] for v in value_to_result},
        }, f, indent=2)
    print('wrote vm_full_dispatch.json')


if __name__ == '__main__':
    main()
