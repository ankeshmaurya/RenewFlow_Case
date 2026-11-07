"""Text normalization and masked comparison helpers (pure functions)."""
from __future__ import annotations

import unicodedata

# Cyrillic and Greek letters that look like Latin letters. Written as escapes so the source stays unambiguous.
_HOMOGLYPHS = {
    "\u0410": "A", "\u0430": "a", "\u0412": "B", "\u0415": "E", "\u0435": "e", "\u041a": "K",
    "\u041c": "M", "\u041d": "H", "\u041e": "O", "\u043e": "o", "\u0420": "P", "\u0440": "p",
    "\u0421": "C", "\u0441": "c", "\u0422": "T", "\u0423": "Y", "\u0443": "y", "\u0425": "X",
    "\u0445": "x", "\u0406": "I", "\u0456": "i", "\u0408": "J", "\u0455": "s",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0396": "Z", "\u0397": "H", "\u0399": "I",
    "\u039a": "K", "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u03a1": "P", "\u03a4": "T",
    "\u03a5": "Y", "\u03a7": "X", "\u03bf": "o",
}


def fold_homoglyphs(text):
    """NFKC normalize and map Cyrillic/Greek lookalikes to Latin. Case is preserved."""
    if text is None:
        return None
    t = unicodedata.normalize("NFKC", text)
    return "".join(_HOMOGLYPHS.get(c, c) for c in t)


def was_folded(text) -> bool:
    return text is not None and fold_homoglyphs(text) != text


def _canon(text):
    if text is None:
        return None
    return fold_homoglyphs(text).strip().lower()


def masked_equal(a, b, mask_chars: str) -> bool:
    """Compare two possibly masked strings. Visible prefixes and suffixes must agree."""
    if a is None or b is None:
        return False
    ma = any(c in mask_chars for c in a)
    mb = any(c in mask_chars for c in b)
    if not ma and not mb:
        return a == b

    def prefix(s):
        for i, c in enumerate(s):
            if c in mask_chars:
                return s[:i]
        return s

    def suffix(s):
        for i in range(len(s) - 1, -1, -1):
            if s[i] in mask_chars:
                return s[i + 1:]
        return s

    pa, pb, sa, sb = prefix(a), prefix(b), suffix(a), suffix(b)
    return (pa.startswith(pb) or pb.startswith(pa)) and (sa.endswith(sb) or sb.endswith(sa))


def name_match(a, b) -> bool:
    ca, cb = _canon(a), _canon(b)
    if ca is None or cb is None:
        return False
    ta, tb = ca.split(), cb.split()
    if len(ta) != len(tb):
        return False
    return all(masked_equal(x, y, "*") for x, y in zip(ta, tb))


def email_match(a, b) -> bool:
    ca, cb = _canon(a), _canon(b)
    if ca is None or cb is None or "@" not in ca or "@" not in cb:
        return False
    la, da = ca.rsplit("@", 1)
    lb, db = cb.rsplit("@", 1)
    return da == db and masked_equal(la, lb, "*")


def phone_match(a, b) -> bool:
    def canon(p):
        c = _canon(p)
        if c is None:
            return None
        return "".join(ch for ch in c if ch not in " -()")

    ca, cb = canon(a), canon(b)
    if ca is None or cb is None:
        return False
    return masked_equal(ca, cb, "x*")


def damerau_levenshtein(a: str, b: str) -> int:
    """Optimal string alignment distance (insert, delete, substitute, adjacent transposition)."""
    a, b = a or "", b or ""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def days_set(days) -> frozenset:
    if not days:
        return frozenset()
    return frozenset(p.strip()[:3].title() for p in days.split(",") if p.strip())


def hhmm(t) -> str:
    return (t or "")[:5]
