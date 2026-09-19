"""Hide fake-bold overprint copies from the text layer.

The source PDFs simulate bold by drawing the same string 2-5 times with
tiny offsets.  Every copy after the first is wrapped in
``/Span <</ActualText ()>> BDC ... EMC`` so it still renders but
contributes nothing to text extraction, search or copy/paste.
"""
from pypdf.generic import (ArrayObject, ContentStream, DictionaryObject,
                           NameObject, TextStringObject)

SHOW_OPS = {b"Tj", b"TJ", b"'", b'"'}
# Ops that may sit between two copies without breaking the overprint run.
STATE_OPS = {b"Tr", b"w", b"g", b"G", b"rg", b"RG", b"k", b"K", b"cs", b"CS",
             b"sc", b"SC", b"scn", b"SCN", b"gs", b"Tc", b"Tw", b"Tz", b"Ts",
             b"Tf", b"TL", b"BT", b"ET", b"q", b"Q", b"J", b"j", b"M", b"d"}
MAX_OFFSET = 0.25  # text-space units (fraction of font size)
MAX_TM_SHIFT = 1.5  # points, for copies positioned with absolute Tm


def _raw(s):
    if hasattr(s, "get_original_bytes"):
        return s.get_original_bytes()
    if isinstance(s, bytes):
        return bytes(s)
    return b""


def _key(op, operands):
    if op in (b"Tj", b"'"):
        return _raw(operands[0])
    if op == b'"':
        return _raw(operands[2])
    return b"".join(_raw(x) for x in operands[0])


def _span_start():
    return ([NameObject("/Span"),
             DictionaryObject({NameObject("/ActualText"): TextStringObject("")})],
            b"BDC")


def dedup_operations(ops):
    """Return (new_ops, hidden_count).

    Within a run of overprinted copies all but the LAST copy are hidden:
    the final copy is often merged with the text that follows it
    (``(1-2)Tj`` x4 then ``(1-2 = No effect)Tj``), so keeping the last one
    is what yields a clean single line.
    """
    out = []
    last_key = None     # key of the last shown string still eligible for a run
    last_idx = None     # index in `out` of that show op
    last_tm = None
    tm = None
    leading = 0.0
    hide = set()
    for operands, op in ops:
        if op in SHOW_OPS:
            key = _key(op, operands)
            if op in (b"'", b'"') and abs(leading) > MAX_OFFSET:
                last_key = None
            if last_key and last_key.strip() and key.startswith(last_key):
                hide.add(last_idx)
            last_key, last_idx, last_tm = key, len(out), tm
            out.append((operands, op))
            continue
        if op in (b"Td", b"TD"):
            tx, ty = float(operands[0]), float(operands[1])
            if op == b"TD":
                leading = -ty
            if abs(tx) > MAX_OFFSET or abs(ty) > MAX_OFFSET:
                last_key = None
        elif op == b"T*":
            if abs(leading) > MAX_OFFSET:
                last_key = None
        elif op == b"TL":
            leading = float(operands[0])
        elif op == b"Tm":
            tm = [float(x) for x in operands]
            if last_tm is None or max(abs(tm[4] - last_tm[4]), abs(tm[5] - last_tm[5])) > MAX_TM_SHIFT                     or any(abs(a - b) > 1e-3 for a, b in zip(tm[:4], last_tm[:4])):
                last_key = None
        elif op not in STATE_OPS:
            last_key = None
        out.append((operands, op))
    if not hide:
        return out, 0
    result = []
    for i, item in enumerate(out):
        if i in hide:
            result.append(_span_start())
            result.append(item)
            result.append(([], b"EMC"))
        else:
            result.append(item)
    return result, len(hide)


def dedup_page(page, reader):
    contents = page.get_contents()
    if contents is None:
        return 0
    cs = ContentStream(contents, reader)
    new_ops, hidden = dedup_operations(cs.operations)
    if hidden:
        cs.operations = new_ops
        page.replace_contents(cs)
    return hidden
