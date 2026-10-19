"""Reads a contacts file (.vcf) exported from Google Contacts or the phone's Contacts app.

Handles vCard 2.1 (Android export: quoted-printable names, soft line breaks), 3.0 (Google export) and 4.0,
folded lines, grouped properties (item1.TEL), and the usual birthday formats. Photos are skipped."""
import quopri
import re
import unicodedata

import ranking

MAX_CONTACTS = 5000


def _unfold(text):
    """Joins continuation lines: a quoted-printable soft break (line ends with '=') or a folded line
    (next line starts with a space or tab)."""
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if out and out[-1].endswith("=") and "QUOTED-PRINTABLE" in _head(out[-1]).upper():
            out[-1] = out[-1][:-1] + line
        elif out and line[:1] in (" ", "\t"):
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _head(line):
    """The part before the first ':' that is not inside double quotes (property name and parameters)."""
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == ":" and not quoted:
            return line[:i]
    return line


def _split_unescaped(value, sep):
    return [p for p in re.split(r"(?<!\\)" + re.escape(sep), value)]


def _unescape(v):
    return re.sub(r"\\([nN,;\\])", lambda m: " " if m.group(1) in "nN" else m.group(1), v).strip()


def _prop(line):
    head = _head(line)
    if len(head) == len(line):
        return None
    value = line[len(head) + 1:]
    parts = _split_unescaped(head, ";")
    name = parts[0].split(".")[-1].strip().upper()        # item1.TEL -> TEL
    types, params = set(), {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            k, v = k.strip().upper(), v.strip().strip('"')
            params[k] = v
            if k == "TYPE":
                types.update(t.strip().upper() for t in v.split(",") if t.strip())
        elif p.strip():
            types.add(p.strip().upper())                    # vCard 2.1 bare types: TEL;CELL;PREF
    encoding = params.get("ENCODING", "").upper()
    if encoding in ("B", "BASE64") or "BASE64" in types:
        return None                                         # photos and other binary data
    if encoding == "QUOTED-PRINTABLE" or "QUOTED-PRINTABLE" in types:
        charset = params.get("CHARSET") or "utf-8"
        try:
            value = quopri.decodestring(value.encode("latin-1", "replace")).decode(charset, "replace")
        except LookupError:
            value = quopri.decodestring(value.encode("latin-1", "replace")).decode("utf-8", "replace")
    return name, types, params, value


def _birthday(value, params):
    """'1988-03-14', '19880314', '--03-14', '--0314' (time part ignored) -> 'YYYY-MM-DD' or 'MM-DD'."""
    v = value.strip()
    m = re.match(r"^(\d{4})-?(\d{2})-?(\d{2})", v)
    if m:
        y, mo, d = m.groups()
        # Apple marks "no year" with X-APPLE-OMIT-YEAR (and a placeholder year like 1604)
        out = f"{mo}-{d}" if "X-APPLE-OMIT-YEAR" in params or int(y) < 1900 else f"{y}-{mo}-{d}"
    else:
        m = re.match(r"^--(\d{2})-?(\d{2})", v)
        if not m:
            return None
        out = f"{m.group(1)}-{m.group(2)}"
    if not ranking.parse_birthday(out):
        if len(out) > 5 and ranking.parse_birthday(out[5:]):   # e.g. a Feb 29 with a non-leap year
            return out[5:]
        return None
    return out


def _card(props):
    fn = n = None
    phones, emails, birthday = [], [], None
    for name, types, params, value in props:
        if name == "FN":
            fn = _unescape(value)
        elif name == "N":
            f = [_unescape(x) for x in _split_unescaped(value, ";")] + [""] * 5
            n = " ".join(x for x in (f[3], f[1], f[2], f[0], f[4]) if x)    # prefix given middle family suffix
        elif name == "TEL":
            num = re.sub(r"^tel:", "", value.strip(), flags=re.I).strip()
            if num:
                rank = 0 if types & {"CELL", "MOBILE"} else 1 if "PREF" in types or "PREF" in params else 2
                phones.append((rank, len(phones), num))
        elif name == "EMAIL":
            addr = value.strip()
            if addr:
                emails.append((0 if "PREF" in types or "PREF" in params else 1, len(emails), addr))
        elif name == "BDAY" and birthday is None:
            birthday = _birthday(value, params)
    name = (fn or n or "").strip()
    if not name:
        return None
    return {
        "name": name[:80],
        "phone": min(phones)[2][:40] if phones else None,
        "email": min(emails)[2][:120] if emails else None,
        "birthday": birthday,
    }


def _sort_key(name):
    """Alphabetical ignoring case and accents, so Élodie sorts with the E's."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch)).casefold()


def parse(text):
    """Contacts in the file, sorted by name, without exact duplicates. Cards without a name are skipped."""
    contacts, props, inside = [], [], False
    for line in _unfold(text or ""):
        upper = line.strip().upper()
        if upper == "BEGIN:VCARD":
            inside, props = True, []
        elif upper == "END:VCARD":
            if inside:
                c = _card(props)
                if c:
                    contacts.append(c)
            inside = False
        elif inside:
            p = _prop(line)
            if p:
                props.append(p)
    seen, out = set(), []
    for c in contacts:
        key = (c["name"].casefold(), re.sub(r"\D", "", c["phone"] or "")[-10:])
        if key not in seen:
            seen.add(key)
            out.append(c)
    out.sort(key=lambda c: _sort_key(c["name"]))
    return out[:MAX_CONTACTS]
