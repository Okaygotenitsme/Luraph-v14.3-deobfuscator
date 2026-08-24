import re

REG = 'reg'
FLD = 'field'
CST = 'const'

EXPR_TEMPLATES = {
    0: '{lp} = {S} / {E}',
    1: '{E} = {S} .. {lp}',
    3: 'call r{S}..r{lp} (varargs)',
    4: 'call r{lp} (varargs)',
    5: '{lp} = self',
    6: '{E} = {lp} * {S}',
    7: '{lp} = {S} - {E}',
    8: '{lp} = lp',
    9: '{S} = {lp} ^ {E}',
    10: 'const_table[{l}] = imm({Hp})',
    13: '{S} = concat_or_len({lp}, {E})',
    14: 'unpack r{S} count r{lp}',
    15: '{E} = const[{lp}][k1][k2]',
    16: '{E}[{S}] = imm({Hp})',
    17: 'const_table[{lp}][{l}] = {S}',
    20: 'const_table[{S}][{l}] = imm({Hp})',
    21: '{S} = const[{lp}]',
    22: 'r{S}, r{S}+1 = table_unpack({lp}, {l})',
    23: '{E} = imm({Hp}) + {S}',
    24: 'for r={E},{S} do r[i] = nil end',
    25: '{lp} = k({l})',
    30: 'r{lp}, ok, err = pcall(); if ok then jump_to {S}',
    31: '{lp} = {S} >= {E}',
    32: 'const[{S}][k1][k2][{lp}] = k({l})',
    33: '{S} = k({l}) * {lp}',
    34: '{E} = imm({Hp}) ^ {S}',
    36: '{S} = {lp} .. k({l})',
    37: '{lp} = {E} + imm({G})',
    40: '{lp} = imm({G}) - {E}',
    41: '{E} = const[{lp}][{S}]',
    42: '{lp} = r{lp}(r{lp}+1, r{lp}+2)',
    43: '{lp}[{E}] = {S}',
    44: 'const[{S}][{lp}] = k({l})',
    47: '{E} = const[{lp}][imm({G})]',
    48: '{lp} = s[{Y}]',
    49: 'const[{E}][k1][k2][imm({G})] = imm({Hp})',
    50: '{E} = r{E}(varargs)',
    51: '{S} = k({l}) .. {lp}',
    52: 'const[{S}][{lp}] = {E}',
    54: 'for r=1,{E} do r[i] = s[i] end',
    55: '{S} = const[{lp}][k1][k2][{E}]',
    56: '{E} = {S} % {lp}',
    57: 'if {lp} ~= {E} then jump {S}',
    58: '{lp} = Q[{l}]',
    59: '{E} = {S} / imm({Hp})',
    60: '{S} = {lp} == {E}',
    61: '{lp} = k({l}) / {S}',
    62: '{S} = {lp} + {E}',
    63: 'zp = {S}; copy s[1..zp] to z; Y = zp+1',
    64: '{lp} = {E} ^ imm({G})',
    65: '{lp} = r{E}(varargs)',
    66: 'const[{E}][k1][k2][imm({G})] = {lp}',
    67: 'const[{E}][k1][k2] = imm({Hp})',
    68: '{lp} = not {E}',
    72: '{lp}() (call, 0 args)',
    73: 'if imm({G}) < {lp} then jump {E}',
    74: '{lp}[imm({G})] = {E}',
    75: '{E} = {lp}',
    76: 'upvals[{E}] = {lp}',
    78: 'r{lp}..r{S}+{E} = copy({lp}) (table.move-like)',
    79: 'closure {S} = make_closure(imm({Hp}))',
    80: '{E} = {S} * imm({Hp})',
    81: '{E} = {S} <= {lp}',
    84: '{S} = {lp} - k({l})',
    85: 'restore call frame from upvals',
    86: 'call r{lp}()',
    88: '{S} = #{lp}',
    90: '{E} = nil',
    93: 'const[{G}] = {lp}',
    95: '{S} = {lp}[{E}]',
    97: '{S}[{l}] = imm({Hp})',
    100: '{E} = upvals[{lp}]',
    101: '{lp} = w',
    104: '{S} = -{E}',
    105: '{S} = closure_ref',
    106: 'r{S}(r{S}+1)',
    107: 'r{E} = r{E}()',
    108: 'r{E}(r{E}+1, r{E}+2)',
    109: 'const[{E}][k1][imm(k2)] = {S}',
    110: '{S} = new_table(size={lp})',
    111: '{lp} = {E} < {S}',
    112: '{S} = const[{E}][k1][k2][imm({Hp})]',
    113: '{S} = imm({Hp}) / k({l})',
    114: '{lp} = {E} == imm({G})',
    115: '{E} = S_upval',
    116: '{lp} = {S}[k({l})]',
    117: '{lp} = E_upval',
    118: '{S} = {{}}',
    120: '{lp} = {S} % k({l})',
    121: 'nop',
}

FIELD_NAMES = {
    'lp': 'operand_lp',
    'S': 'operand_S',
    'E': 'operand_E',
    'Hp': 'operand_Hp',
    'G': 'operand_G',
    'l': 'operand_l',
}

PLACEHOLDER_RE = re.compile(r'\{(lp|S|E|Hp|G|l|Y)\}')


def resolve_placeholder(name, proto, insn_idx):
    if name == 'Y':
        return 'Y'
    field = FIELD_NAMES.get(name)
    if field is None:
        return name
    val = proto[field][insn_idx]
    if isinstance(val, tuple):
        kind, v = val
        if kind == 'string':
            try:
                return repr(v.decode('utf-8', errors='replace'))
            except Exception:
                return repr(v)
        return repr(v)
    if val is None:
        return f'{name}?'
    if name in ('lp', 'S', 'E'):
        return f'r{val}'
    return str(val)


def render_expr(opcode, proto, insn_idx):
    template = EXPR_TEMPLATES.get(opcode)
    if template is None:
        return None

    def replace(m):
        return resolve_placeholder(m.group(1), proto, insn_idx)

    return PLACEHOLDER_RE.sub(replace, template)
