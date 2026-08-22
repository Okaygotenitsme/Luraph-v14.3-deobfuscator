import re
import sys
from collections import defaultdict


NUM_RE = re.compile(r'^0[xX][0-9a-fA-F_]+$|^0[bB][01_]+$|^[0-9][0-9_]*$')


def normalize_number(tok):
    tok = tok.replace('_', '')
    if re.match(r'^0[xX]', tok):
        return int(tok, 16)
    if re.match(r'^0[bB]', tok):
        return int(tok, 2)
    return int(tok)


def find_state_var(source):
    counts = defaultdict(int)
    for m in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)(==|~=)(0[xXbB][0-9a-fA-F_]+|[0-9][0-9_]*)\b', source):
        counts[m.group(1)] += 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def extract_comparisons(source, varname):
    pattern = re.compile(
        r'\b' + re.escape(varname) + r'(==|~=)([0-9a-zA-Z_]+)\b'
    )
    results = []
    for m in pattern.finditer(source):
        op, tok = m.group(1), m.group(2)
        if NUM_RE.match(tok):
            try:
                val = normalize_number(tok)
            except ValueError:
                continue
            results.append((m.start(), op, val))
    return results


def extract_table_index_writes(source, varname):
    pattern = re.compile(
        r'\(?' + re.escape(varname) + r'\)?\[([0-9a-zA-Z_]+)\]\s*=\s*'
    )
    results = []
    for m in pattern.finditer(source):
        tok = m.group(1)
        if NUM_RE.match(tok):
            try:
                val = normalize_number(tok)
            except ValueError:
                continue
            results.append((m.start(), val))
    return results


def extract_method_calls(source, prefix):
    pattern = re.compile(r'\b' + re.escape(prefix) + r'\.([A-Za-z_][A-Za-z0-9_]*)\s*\(')
    counts = defaultdict(int)
    for m in pattern.finditer(source):
        counts[m.group(1)] += 1
    return counts


def find_helper_table_prefix(source):
    counts = defaultdict(int)
    for m in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)\.[A-Za-z_][A-Za-z0-9_]*\s*\(', source):
        counts[m.group(1)] += 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return ranked[:10]


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else 'sunjingwoo.lua'
    with open(src_path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        source = f.read()

    state_var = find_state_var(source)
    print('detected state variable:', state_var)

    comparisons = extract_comparisons(source, state_var)
    values = sorted(set(v for _, _, v in comparisons))
    print('unique compared state values:', len(values))
    print('sample values:', values[:30])

    cache_var_candidates = defaultdict(int)
    for m in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)\[[0-9a-zA-Z_]+\]\s*=', source):
        cache_var_candidates[m.group(1)] += 1
    ranked_cache = sorted(cache_var_candidates.items(), key=lambda kv: -kv[1])[:10]
    print('candidate cache/table variables (writes):', ranked_cache)

    helper_ranked = find_helper_table_prefix(source)
    print('candidate helper method-call tables:', helper_ranked)

    if helper_ranked:
        top_prefix = helper_ranked[0][0]
        method_counts = extract_method_calls(source, top_prefix)
        print(f'methods called on {top_prefix}:', dict(sorted(method_counts.items(), key=lambda kv: -kv[1])))

    print('total state==/~=  comparisons found:', len(comparisons))


if __name__ == '__main__':
    main()
  
