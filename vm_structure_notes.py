DESERIALIZER_PRIMITIVES = {
    'O': 'read_u8',
    'K': 'read_varint_leb128',
    'p': 'read_double_le8',
    'kp': 'read_length_prefixed_string',
    'Gp': 'read_closure_proto_recursive',
    'M': 'read_something_special_flag',
}

CONST_TAGS = {
    0x70: 'STRING',
    0x0f: 'DOUBLE',
    0x22: 'INT64',
    0x15: 'BOOL',
}

PROTO_FIELDS = {
    1: 'num_params_or_frame_meta',
    2: 'is_vararg',
    4: 'jump_target_operand_array',
    5: 'debug_or_extra_array',
    7: 'operand_a_array',
    8: 'constant_pool_array',
    9: 'immediate_operand_array',
    10: 'instruction_opcode_array',
    11: 'operand_b_array',
    6: 'nested_proto_list',
}

CLOSURE_FACTORY_LOCALS = {
    'r': 'Fp[1]',
    'x': 'Fp[2]',
    'S': 'Fp[5]',
    'w': 'Fp[10]',
    'G': 'Fp[9]',
    'lp': 'Fp[7]',
    'l': 'Fp[8]',
    'Hp': 'Fp[11]',
    'E': 'Fp[4]',
}

CALL_CHAIN = [
    'x(source_text, 5) -> base85 blob -> decoded bytes',
    'Bp() deserializes decoded bytes into a proto table (fields per PROTO_FIELDS)',
    'i = Bp()',
    'ap(i, Jp) wraps proto i into a closure using CLOSURE_FACTORY_LOCALS field mapping',
    'inside closure T: while dispatch loop reads n = w[I] (opcode array indexed by instruction pointer I)',
    'each opcode n has a handler using operand arrays lp[I], E[I], S[I], Hp[I], G[I], l[I], d[const]',
]

NOTES = """
kp() reads an 8-byte length prefix then the string bytes -> matches TAG_STRING(0x70)
    in const_parser_v4.py (varint length there is likely this same routine at a
    different call site, or a simplified assumption in the const parser that only
    holds for short strings).
p() reads 8 raw bytes as a little-endian double -> matches TAG_DOUBLE(0x0f).
O()==jp (boolean literal comparison) -> matches TAG_BOOL(0x15).
K() is a 7-bit LEB128 varint reader, continuation bit 0x80 -> matches read_varint()
    in const_parser_v3.py / const_parser_v4.py.

Next actionable step: hook K()/O()/p()/kp() semantics directly against decoded.bin
byte offsets to walk the *real* proto tree from the binary side, instead of only
reading the Lua source of the deserializer. This lets opcode arrays (w, lp, E, S,
Hp, G, l) be recovered as concrete numbers per function, which is required before
a bytecode-to-Lua translator can run on decoded.bin directly rather than just
describing handler semantics from source.
"""
