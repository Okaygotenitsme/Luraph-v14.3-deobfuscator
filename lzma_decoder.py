import struct
import sys

POS_SLOT_TABLE_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14]

STATE_TRANSITION_LIT = [0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 4, 5]


class RangeDecoder:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.code = 0
        self.range = 0xFFFFFFFF
        for _ in range(5):
            self.code = (self.code * 256 + self._read_byte()) & 0xFFFFFFFFFFFFFFFF

    def _read_byte(self):
        b = self.data[self.pos]
        self.pos += 1
        return b

    def decode_direct_bits(self, num):
        result = 0
        for _ in range(num):
            self.range //= 2
            result <<= 1
            if self.code >= self.range:
                self.code -= self.range
                result |= 1
            if self.range <= 0x00FFFFFF:
                self.range *= 256
                self.code = self.code * 256 + self._read_byte()
        return result

    def decode_bit(self, probs, idx):
        prob = probs[idx]
        bound = (self.range // 2048) * prob
        if self.code < bound:
            self.range = bound
            probs[idx] = prob + ((2048 - prob) >> 5)
            bit = 0
        else:
            self.range -= bound
            self.code -= bound
            probs[idx] = prob - (prob >> 5)
            bit = 1
        if self.range <= 0x00FFFFFF:
            self.range *= 256
            self.code = self.code * 256 + self._read_byte()
        return bit

    def decode_bit_tree(self, probs, num_bits):
        m = 1
        for _ in range(num_bits):
            m = (m << 1) | self.decode_bit(probs, m)
        return m - (1 << num_bits)

    def decode_bit_tree_reverse(self, probs, offset, num_bits):
        m = 1
        result = 0
        for i in range(num_bits):
            bit = self.decode_bit(probs, offset + m)
            m = (m << 1) | bit
            result |= bit << i
        return result


def make_probs(n):
    return [1024] * n


def decode_len(rd, bundle, pos_state):
    if rd.decode_bit(bundle, 0) == 0:
        return rd.decode_bit_tree(bundle[2][pos_state], 3)
    if rd.decode_bit(bundle, 1) == 0:
        return 8 + rd.decode_bit_tree(bundle[3][pos_state], 3)
    return 16 + rd.decode_bit_tree(bundle[4], 8)


def make_len_bundle():
    return [1024, 1024, [make_probs(8)], [make_probs(8)], make_probs(256)]


def lzma_decompress(compressed, out_size_hint=None):
    rd = RangeDecoder(compressed)

    lit_probs = make_probs(8 * 0x300)
    is_match = [make_probs(1) for _ in range(12)]
    is_rep = make_probs(12)
    is_rep_g0 = make_probs(12)
    is_rep_g1 = make_probs(12)
    is_rep_g2 = make_probs(12)
    is_rep0_long = [make_probs(1) for _ in range(12)]

    pos_slot_probs = [make_probs(64) for _ in range(4)]
    spec_pos_probs = make_probs(115)
    align_probs = make_probs(16)

    len_bundle = make_len_bundle()
    rep_len_bundle = make_len_bundle()

    out = bytearray()
    state = 0
    rep0 = rep1 = rep2 = rep3 = 0

    def peek_byte(dist):
        idx = len(out) - dist - 1
        if idx < 0:
            return 0
        return out[idx]

    max_out = out_size_hint if out_size_hint else (len(compressed) * 50)

    while rd.pos <= len(compressed) and len(out) < max_out:
        pos_state = len(out) & 0

        if rd.decode_bit(is_match[state], 0) == 0:
            prev_byte = peek_byte(0)
            lit_state = 0
            probs_offset = 0x300 * lit_state
            if state < 7:
                symbol = 1
                for _ in range(8):
                    bit = rd.decode_bit(lit_probs, probs_offset + symbol)
                    symbol = (symbol << 1) | bit
                out.append(symbol & 0xFF)
            else:
                match_byte = peek_byte(rep0)
                symbol = 1
                for _ in range(8):
                    match_bit = (match_byte >> 7) & 1
                    match_byte = (match_byte << 1) & 0xFF
                    bit = rd.decode_bit(lit_probs, probs_offset + ((1 + match_bit) << 8) + symbol)
                    symbol = (symbol << 1) | bit
                out.append(symbol & 0xFF)
            state = STATE_TRANSITION_LIT[state]
            continue

        if rd.decode_bit(is_rep, state) != 0:
            if len(out) == 0:
                return bytes(out)
            if rd.decode_bit(is_rep_g0, state) == 0:
                if rd.decode_bit(is_rep0_long[state], 0) == 0:
                    state = 9 if state < 7 else 11
                    length = 1
                    out.append(peek_byte(rep0))
                    continue
            else:
                if rd.decode_bit(is_rep_g1, state) == 0:
                    dist = rep1
                else:
                    if rd.decode_bit(is_rep_g2, state) == 0:
                        dist = rep2
                    else:
                        dist = rep3
                        rep3 = rep2
                    rep2 = rep1
                rep1 = rep0
                rep0 = dist
            length = 2 + decode_len(rd, rep_len_bundle, 0)
            state = 8 if state < 7 else 11
        else:
            rep3, rep2, rep1 = rep2, rep1, rep0
            length = 2 + decode_len(rd, len_bundle, 0)
            len_state = min(length - 2, 3)
            pos_slot = rd.decode_bit_tree(pos_slot_probs[len_state], 6)
            if pos_slot < 4:
                rep0 = pos_slot
            else:
                num_direct_bits = (pos_slot >> 1) - 1
                rep0 = (2 | (pos_slot & 1)) << num_direct_bits
                if pos_slot < 14:
                    rep0 += rd.decode_bit_tree_reverse(spec_pos_probs, rep0 - pos_slot - 1, num_direct_bits)
                else:
                    rep0 += rd.decode_direct_bits(num_direct_bits - 4) << 4
                    rep0 += rd.decode_bit_tree_reverse(align_probs, 0, 4)
            if rep0 == 0xFFFFFFFF:
                break
            state = 7 if state < 7 else 10

        for _ in range(length):
            out.append(peek_byte(rep0))

    return bytes(out)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'decoded_16740f094b64b837.bin'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'lzma_out.bin'

    with open(path, 'rb') as f:
        data = f.read()

    result = lzma_decompress(data)
    print(f'decompressed {len(data)} -> {len(result)} bytes')

    with open(out_path, 'wb') as f:
        f.write(result)

    print('first 100 bytes:', result[:100])


if __name__ == '__main__':
    main()
