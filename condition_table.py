import re

CONDITION_SPECS = {
    2: {'op': '<', 'lhs': ('reg', 'lp'), 'rhs': ('reg', 'S'), 'invert': False},
    12: {'op': 'truthy', 'lhs': ('reg', 'E'), 'rhs': None, 'invert': True},
    26: {'op': '<', 'lhs': ('reg', 'S'), 'rhs': ('reg', 'E'), 'invert': True},
    27: {'op': '~=', 'lhs': ('reg', 'S'), 'rhs': ('field', 'Hp'), 'invert': False},
    28: {'op': '~=', 'lhs': ('reg', 'lp'), 'rhs': ('reg', 'E'), 'invert': True},
    29: {'op': '<', 'lhs': ('field', 'Hp'), 'rhs': ('reg', 'S'), 'invert': False},
    39: {'op': '<=', 'lhs': ('reg', 'lp'), 'rhs': ('const', 'l'), 'invert': False},
    57: {'op': '~=', 'lhs': ('reg', 'lp'), 'rhs': ('reg', 'E'), 'invert': False},
    73: {'op': '<', 'lhs': ('field', 'G'), 'rhs': ('reg', 'lp'), 'invert': True},
    82: {'op': '<=', 'lhs': ('field', 'G'), 'rhs': ('reg', 'E'), 'invert': True},
    89: {'op': '<', 'lhs': ('reg', 'lp'), 'rhs': ('const', 'l'), 'invert': True},
    94: {'op': '==', 'lhs': ('reg', 'S'), 'rhs': ('field', 'Hp'), 'invert': False},
    99: {'op': 'truthy', 'lhs': ('reg', 'lp'), 'rhs': None, 'invert': False},
    103: {'op': '<=', 'lhs': ('reg', 'S'), 'rhs': ('reg', 'E'), 'invert': True},
}

OP_SYMBOLS = {
    '<': '<',
    '<=': '<=',
    '==': '==',
    '~=': '~=',
}


def describe_operand(kind, value):
    if kind == 'reg':
        return f'r{value}' if isinstance(value, int) else str(value)
    if kind == 'field':
        return f'imm({value})'
    if kind == 'const':
        return f'k({value})'
    return str(value)


def render_condition(opcode, proto, insn_idx):
    spec = CONDITION_SPECS.get(opcode)
    if spec is None:
        return f'<cond opcode={opcode}>'

    operand_map = {
        'lp': proto['operand_lp'][insn_idx],
        'S': proto['operand_S'][insn_idx],
        'E': proto['operand_E'][insn_idx],
        'Hp': proto['operand_Hp'][insn_idx],
        'G': proto['operand_G'][insn_idx],
        'l': proto['operand_l'][insn_idx],
    }

    lhs_kind, lhs_field = spec['lhs']
    lhs_val = operand_map.get(lhs_field)
    lhs_text = describe_operand(lhs_kind, lhs_val)

    if spec['op'] == 'truthy':
        text = lhs_text
        if spec['invert']:
            text = f'not {text}'
        return text

    rhs_kind, rhs_field = spec['rhs']
    rhs_val = operand_map.get(rhs_field)
    rhs_text = describe_operand(rhs_kind, rhs_val)

    op_symbol = OP_SYMBOLS.get(spec['op'], spec['op'])
    text = f'{lhs_text} {op_symbol} {rhs_text}'
    if spec['invert']:
        text = f'not ({text})'
    return text
