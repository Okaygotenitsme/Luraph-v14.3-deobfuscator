import re
import struct
import sys


def lua_unescape(s):
    out = bytearray()
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '\\':
            i += 1
            nxt = s[i]
            if nxt == 'x':
                out.append(int(s[i+1:i+3], 16))
                i += 3
            elif nxt.isdigit():
                j = i
                while j < len(s) and j < i + 3 and s[j].isdigit():
                    j += 1
                out.append(int(s[i:j]))
                i = j
            elif nxt == 'z':
                i += 1
                while i < len(s) and s[i] in ' \t\r\n':
                    i += 1
            elif nxt == '\\':
                out.append(0x5c)
                i += 1
            elif nxt == '"':
                out.append(0x22)
                i += 1
            elif nxt == 'n':
                out.append(0x0a)
                i += 1
            elif nxt == 't':
                out.append(0x09)
                i += 1
            elif nxt == 'r':
                out.append(0x0d)
                i += 1
            else:
                out.append(ord(nxt))
                i += 1
        else:
            out.append(ord(ch))
            i += 1
    return bytes(out)


def extract_blob(source_text):
    m = re.search(r'x\("((?:[^"\\]|\\.)*)",\s*0[xX]5\)', source_text)
    if m:
        return lua_unescape(m.group(1))

    lph_start = source_text.find('"LPH')
    if lph_start != -1:
        pos = lph_start + 1
        n = len(source_text)
        while pos < n:
            ch = source_text[pos]
            if ch == chr(92):
                pos += 2
                continue
            if ch == '"':
                candidate = source_text[lph_start + 1:pos]
                return lua_unescape(candidate)
            pos += 1

    for m in re.finditer(r'\[(=*)\[(LPH.*?)\]\1\]', source_text, re.DOTALL):
        return m.group(2).encode('latin-1', errors='ignore')

    raise ValueError("blob literal not found")


def decode_b85_chunk(chunk):
    w, l, M, p, K = chunk[0], chunk[1], chunk[2], chunk[3], chunk[4]
    val = (K - 0x21) + (p - 0x21) * 85 + (M - 0x21) * 85 ** 2 + (l - 0x21) * 85 ** 3 + (w - 0x21) * 85 ** 4
    return val & 0xFFFFFFFF


def decode_payload(blob_bytes):
    sub = blob_bytes[4:]
    sub = sub.replace(b'z', b'!' * 5)
    n = len(sub) - (len(sub) % 5)
    out = bytearray()
    for i in range(0, n, 5):
        val = decode_b85_chunk(sub[i:i + 5])
        out += struct.pack('>I', val)
    return bytes(out)


def decode_from_source(path):
    with open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        text = f.read()
    blob = extract_blob(text)
    return decode_payload(blob)


if __name__ == '__main__':
    src_path = sys.argv[1] if len(sys.argv) > 1 else 'sample.lua'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'decoded.bin'
    data = decode_from_source(src_path)
    with open(out_path, 'wb') as f:
        f.write(data)
    print(len(data), 'bytes ->', out_path)
