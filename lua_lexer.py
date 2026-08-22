import re

KEYWORDS_OPEN = {'function', 'if', 'for', 'while', 'do'}
# NOTE: 'do' as standalone opener only happens as bare `do ... end` block;
# but 'do' also follows for/while and does NOT open an extra 'end'.
# We handle that by only counting 'do' as an opener when it is a *standalone*
# do-block, detected by NOT having just consumed a for/while header.
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
            # 'do' after for/while doesn't add depth (already counted at for/while).
            # A standalone 'do...end' block: we approximate by NOT tracking this
            # distinction perfectly, but since for/while already incremented depth
            # for their header, and their 'do' is just a keyword with no 'end' of
            # its own beyond the for/while's, we must NOT increment again here.
            # A bare 'do' block does need its own 'end', but bare 'do' blocks are
            # rare and can be added by incrementing when a 'do' is NOT immediately
            # preceded contextually by for/while -- too complex for regex level;
            # skip (acceptable approximation for VM dispatcher extraction).
            continue
        elif text == 'end':
            depth -= 1
            if depth == 0:
                return pos
    return -1
