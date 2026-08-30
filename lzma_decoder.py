import sys

E = [1] + [0] * 33
for _i in range(1, 34):
    E[_i] = E[_i - 1] * 2


class Ctx:
    def __init__(self, data):
        self.L = data
        self.i = 0
        self.s = len(data)

    def C(self):
        self.i += 1
        return self.L[self.i - 1]


def make_h(n):
    return [1024] * n


def make_z(rows, cols):
    return [[1024] * cols for _ in range(rows)]


def make_bundle():
    return [1024, 1024, make_z(1, 8), make_z(1, 8), make_h(256)]


def run(data, max_out=None):
    ctx = Ctx(data)

    F_ = 0
    for _ in range(5):
        F_ = F_ * 256 + ctx.C()
    G_ = 0xFFFFFFFF

    def U(N, Q):
        nonlocal F_, G_
        o = N[Q]
        I = G_ // 2048
        T_ = I * o
        if F_ < T_:
            G_ = T_
            I2 = (2048 - o) // 32
            o = o + I2
            M = 0
        else:
            G_ = G_ - T_
            F_ = F_ - T_
            I2 = o // 32
            o = o - I2
            M = 1
        N[Q] = o
        if G_ <= 0x00FFFFFF:
            G_ = G_ * 256
            F_ = F_ * 256 + ctx.C()
        return M

    def H(Q):
        nonlocal F_, G_
        o = 0
        for _ in range(Q):
            G_ = G_ // 2
            o = o * 2
            if not (F_ < G_):
                F_ = F_ - G_
                o = o + 1
            if G_ <= 0x00FFFFFF:
                G_ = G_ * 256
                F_ = F_ * 256 + ctx.C()
        return o

    def S(Q, G, o):
        I = 1
        for _ in range(G):
            I = I * 2 + U(Q, I)
        return I - o

    def Y(F, Q, I):
        G = 0
        N = 1
        for o in range(I):
            bit = U(F, Q + N)
            N = N * 2 + bit
            G = G + bit * E[o]
        return G

    def m(G, I):
        o = 1
        for Q in range(7, -1, -1):
            N = (I // E[Q]) % 2
            bit = U(G, o + (N * 256) + 256)
            o = o * 2 + bit
            if N != bit:
                while o < 0x100:
                    o = o * 2 + U(G, o)
                break
        return o % 256

    def T(Q, I):
        if U(Q, 0) == 0:
            return S(Q[2][I], 3, 8)
        elif U(Q, 1) == 0:
            return 8 + S(Q[3][I], 3, 8)
        return S(Q[4], 8, 256) + 16

    o_pos = 0
    w = bytearray()
    M_state = 0
    C_table = [0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 4, 5]

    d = make_z(8, 0x300)
    Fm = make_z(12, 1)
    Nrep = make_h(12)
    Krep0 = make_h(12)
    Wrep1 = make_h(12)
    Vrep2 = make_h(12)
    Ishort = make_z(12, 1)
    A_slot = make_z(4, 64)
    R_spec = make_h(115)
    g_align = make_h(16)
    t_bundle = make_bundle()
    L_bundle = make_bundle()
    p_dist = 0
    f_rep1 = 0
    G_rep2 = 0
    D_rep3 = 0

    limit = max_out if max_out else len(data) * 60
    iterations = 0
    max_iterations = limit * 4 + 1000

    while ctx.i <= ctx.s:
        iterations += 1
        if iterations > max_iterations:
            break
        if len(w) > limit:
            break

        z_pos = o_pos % 1

        if U(Fm[M_state], z_pos) == 0:
            prev = w[o_pos - 1] if o_pos >= 1 else 0
            s_ctx = prev // E[5]
            Fd = d[s_ctx]
            o_pos = o_pos + 1
            if M_state < 7:
                val = S(Fd, 8, 256)
            else:
                match_byte = w[o_pos - 1 - p_dist - 1] if (o_pos - 1 - p_dist - 1) >= 0 else 0
                val = m(Fd, match_byte)
            if len(w) < o_pos:
                w.append(val & 0xFF)
            else:
                w[o_pos - 1] = val & 0xFF
            M_state = C_table[M_state]
            continue

        F_len = None
        if U(Nrep, M_state) != 0:
            if U(Krep0, M_state) == 0:
                if U(Ishort[M_state], z_pos) == 0:
                    M_state = 9 if M_state < 7 else 11
                    F_len = 1
            else:
                if U(Wrep1, M_state) == 0:
                    I_dist = f_rep1
                else:
                    if U(Vrep2, M_state) == 0:
                        I_dist = G_rep2
                    else:
                        I_dist = D_rep3
                        D_rep3 = G_rep2
                    G_rep2 = f_rep1
                f_rep1 = p_dist
                p_dist = I_dist

            if F_len is None:
                M_state = 8 if M_state < 7 else 11
                F_len = 2 + T(L_bundle, z_pos)
        else:
            D_rep3 = G_rep2
            G_rep2 = f_rep1
            f_rep1 = p_dist
            F_len = 2 + T(t_bundle, z_pos)
            I_len = F_len - 2
            if I_len >= 4:
                I_len = 3
            p_dist = S(A_slot[I_len], 6, 64)
            if p_dist >= 4:
                s_val = p_dist
                I_shift = s_val // 2 - 1
                p_dist = (2 + s_val % 2) * E[I_shift]
                if s_val < 14:
                    p_dist = p_dist + Y(R_spec, p_dist - s_val - 1, I_shift)
                else:
                    p_dist = p_dist + (H(I_shift - 4) * 16) + Y(g_align, 0, 4)
                    if p_dist == 0xFFFFFFFF:
                        return bytes(w), F_len == 2
            M_state = 7 if M_state < 7 else 10
            if p_dist >= o_pos:
                return bytes(w), False

        s_end = o_pos + F_len
        for _ in range(o_pos, s_end):
            src_idx = len(w) - p_dist - 1
            val = w[src_idx] if 0 <= src_idx < len(w) else 0
            w.append(val)
        o_pos = s_end

    return bytes(w), False


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'decoded_16740f094b64b837.bin'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'lzma_out.bin'

    with open(path, 'rb') as f:
        data = f.read()

    result, flag = run(data)
    print(f'input {len(data)} bytes -> output {len(result)} bytes, terminated_flag={flag}')
    print('first 80 bytes:', result[:80])

    with open(out_path, 'wb') as f:
        f.write(result)


if __name__ == '__main__':
    main()
