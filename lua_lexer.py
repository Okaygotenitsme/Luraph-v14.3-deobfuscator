import re

KEYWORDS_OPEN = {'function', 'if', 'for', 'while', 'do'}
KEYWORDS_CLOSE = {'end'}
KEYWORDS_REPEAT = {'repeat'}
KEYWORDS_UNTIL = {'until'}

TOKEN_RE = re.compile(r'''
    (?P<ws>\s+)
  | (?P<long_comment>--\[(?P<eq1>=*)\[.*?\]\1\])
  | (?P<line_comment>--[^\n]*)
  | (?P<long_string>\[(?P<eq2>=*)\[.*?\]\2\])
  | (?P<string>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<number>0[xX][0-9a-fA-F_]+|0[bB][01_]+|[0-9][0-9_]*\.?[0-9_]*(?:[eE][+-]?[0-9]+)?)
  | (?P<op>[^\s])
''', re.VERBOSE | re.DOTALL)


def tokenize(src, start=0, end=None):
    """Yield (kind, text, pos) tuples. kind is 'name','string','number','op', or None for skipped ws/comments."""
    if end is None:
        end = len(src)
    pos = start
    while pos < end:
        m = TOKEN_RE.match(src, pos)
        if not m:
            pos += 1
            continue
        kind = m.lastgroup
        text = m.group(0)
        if kind in ('ws', 'long_comment', 'line_comment'):
            pos = m.end()
            continue
        yield (kind, text, m.start())
        pos = m.end()


def find_matching_end(src, open_pos):
    """
    Given the position right after a 'function(' or similar block opener's
    header, scan tokens and find the index (in src) of the matching 'end'
    keyword that closes this block. Assumes open_pos is positioned so the
    very next relevant keyword tokens are the block's body content.
    Returns position of 'end' (start index) or -1.
    """
    depth = 1
    for kind, text, pos in tokenize(src, open_pos):
        if kind != 'name':
            continue
        if text in ('function', 'if', 'for', 'while'):
            depth += 1
        elif text == 'do':
            continue
        elif text == 'end':
            depth -= 1
            if depth == 0:
                return pos
    return -1
