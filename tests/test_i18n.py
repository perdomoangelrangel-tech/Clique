"""El auditor de textos: cuenta en static/js/** las frases visibles escritas sin t() y las claves de t() que faltan en en.json.

Cómo cuenta (equipo/contratos/textos.md §7):
  * lee cada .js con un lexer pequeño (cadenas, plantillas con ${}, comentarios y expresiones regulares) y sabe si cada cadena va
    dentro de una llamada a t(), th() o tp();
  * en las plantillas con HTML toma los nodos de texto y los atributos que se leen (title, aria-label, placeholder, alt);
  * en las demás cadenas decide si son prosa (palabras para una persona) o código (clases, selectores, rutas, nombres de eventos);
  * una línea con el comentario `i18n: no` se salta (datos del servidor comparados, nombres propios, etc.);
  * en una línea con `i18n: claves` (o entre `i18n: claves ↓` y `i18n: fin`) las cadenas son claves que se pasan a t() desde un mapa:
    cuentan como traducidas y deben estar en en.json.

Falla si en algún archivo suben las frases sin t() respecto a BASE (un archivo nuevo empieza en cero), y si una clave usada en un
archivo de E5 no está en static/i18n/en.json. Los archivos de E4 cuentan igual para las frases; sus claves faltantes solo se avisan.

Para ver el reporte completo:  python -m tests.test_i18n  [--frases archivo.js]
"""
import html
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "static", "js")
EN = os.path.join(ROOT, "static", "i18n", "en.json")
CSS = os.path.join(ROOT, "static", "css")

E4_FILES = {"theme.js", "looks.js", "art.js", "views/diseno.js"}
I18N_CALLS = {"t", "th", "tp"}

# Frases sin t() anotadas por archivo (10-oct, al empezar la ronda 1). Solo pueden bajar: cuando migras un archivo, baja su número.
BASE = {
    "art.js": 6, "cosmetics.js": 2, "gamelist.js": 39, "games/betpanel.js": 10, "games/blackjack.js": 21, "games/chicken.js": 25,
    "games/coinflip.js": 30, "games/common.js": 9, "games/dice.js": 19, "games/hilo.js": 30, "games/limbo.js": 11, "games/mines.js": 21,
    "games/moles.js": 20, "games/roulette.js": 24, "games/rps.js": 28, "games/tower.js": 25, "games/war.js": 40, "games/wheel.js": 20,
    "views/challenges.js": 37, "views/chat.js": 81, "views/create.js": 41, "views/exchange.js": 112, "views/friends.js": 43,
    "views/game.js": 41, "views/games.js": 35, "views/loans.js": 81, "views/market.js": 126, "views/poker.js": 55, "views/pokerfmt.js": 2,
    "views/pokertable.js": 185, "views/polledit.js": 70, "views/portfolio.js": 65, "views/profile.js": 138, "views/progress.js": 49,
    "views/ranking.js": 16, "views/spread.js": 15, "views/statement.js": 58, "views/stockchart.js": 3, "views/store.js": 43,
    "views/transfers.js": 127, "views/weekly.js": 128, "views/whosin.js": 8,
}

# Lo que se queda igual en cualquier idioma (nombres propios, unidades).
NO_TRADUCIR = {
    "clique", "Clique", "XP", "x", "vs", "VS", "OK", "Aa", "ABC123", "123456", "Hi-Lo", "Blackjack", "Limbo", "Coinflip", "Plinko", "Hold'em", "Texas Hold'em",
}

# Llamadas cuyas cadenas son código, no texto: selectores, eventos, clases, rutas del servidor, nombres de íconos.
CODE_CALLS = {
    "querySelector", "querySelectorAll", "getElementById", "closest", "matches", "addEventListener", "removeEventListener",
    "add", "remove", "toggle", "contains", "replace", "setProperty", "getPropertyValue", "removeProperty", "get", "post", "del", "api", "fetch",
    "import", "icon", "sticker", "gameSticker", "poster", "awardSticker", "productArt", "Event", "CustomEvent", "getItem", "setItem",
    "removeItem", "matchMedia", "createElement", "createElementNS", "startsWith", "endsWith", "includes", "indexOf", "split", "join",
    "test", "match", "RegExp", "log", "error", "warn", "info", "debug", "has", "Set", "Map", "dispatchEvent", "getAttribute",
    "removeAttribute", "hasAttribute", "toLocaleString", "toLocaleDateString", "toLocaleTimeString", "Intl", "NumberFormat",
    "DateTimeFormat", "PluralRules", "padStart", "padEnd", "go", "remember", "recall", "saveDraft", "loadDraft", "clearDraft",
    "keepDraft", "send", "EventSource", "WebSocket", "postMessage", "scrollIntoView", "animate", "requestAnimationFrame", "setLook",
    "lookOf", "rankBadge", "logoMark", "gameById", "gameName", "drawChart", "emit", "on", "off", "once", "publish", "subscribe", "describe",
}
VISIBLE_ATTRS = ("title", "aria-label", "placeholder", "alt", "label", "aria-description", "data-tip")
WORD = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ¿¡]{2,}")


def css_classes():
    names = set()
    for n in os.listdir(CSS):
        if n.endswith(".css"):
            with open(os.path.join(CSS, n), encoding="utf-8") as f:
                names.update(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)))
    return names


CLASSES = css_classes()


# ---------------------------------------------------------------- the lexer

class Lit:
    __slots__ = ("text", "line", "in_t", "callee", "argi", "before", "after", "template", "skip", "key")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^") | {"", "return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "yield", "await"}


class Lexer:
    def __init__(self, src):
        self.s, self.n, self.i = src, len(src), 0
        self.frames = []                 # [kind, callee, argument index]
        self.lits = []
        self.prev = ""                   # last significant token (for telling a regex from a division)
        self.last_ident = None
        self.skip_lines, self.key_lines, block = set(), set(), False
        for n, line in enumerate(src.split("\n"), 1):
            if "i18n: no" in line:
                self.skip_lines.add(n)
            if "i18n: claves" in line:
                self.key_lines.add(n)
                block = block or "↓" in line
            elif block:
                self.key_lines.add(n)
                block = "i18n: fin" not in line

    def line(self, i):
        return self.s.count("\n", 0, i) + 1

    def in_t(self):
        return any(f[0] == "(" and f[1] in I18N_CALLS for f in self.frames)

    def call(self):
        for f in reversed(self.frames):
            if f[0] == "(":
                return f[1], f[2]
            if f[0] in "{[":
                return None, 0
        return None, 0

    def add(self, text, start, end, template=False):
        callee, argi = self.call()
        before = self.s[max(0, start - 60):start].rstrip()
        after = self.s[end:end + 20].lstrip()
        self.lits.append(Lit(text=text, line=self.line(start), in_t=self.in_t(), callee=callee, argi=argi, before=before, after=after,
                             template=template, skip=self.line(start) in self.skip_lines, key=self.line(start) in self.key_lines))

    def string(self, q):
        i, s, out = self.i + 1, self.s, []
        while i < self.n and s[i] != q:
            if s[i] == "\\":
                nxt = s[i + 1:i + 2]
                out.append({"n": "\n", "t": "\t"}.get(nxt, nxt))
                i += 2
                continue
            out.append(s[i])
            i += 1
        self.add("".join(out), self.i, i + 1)
        self.i = i + 1
        self.prev = "str"

    def template(self):
        start, i, s, parts = self.i, self.i + 1, self.s, []
        cur = []
        while i < self.n and s[i] != "`":
            if s[i] == "\\":
                cur.append(s[i + 1:i + 2])
                i += 2
                continue
            if s.startswith("${", i):
                parts.append("".join(cur))
                cur = []
                self.i = i + 2
                self.code(stop_brace=True)
                i = self.i
                parts.append("\x00")
                continue
            cur.append(s[i])
            i += 1
        parts.append("".join(cur))
        self.add("".join(parts), start, i + 1, template=True)
        self.i = i + 1
        self.prev = "str"

    def regex(self):
        i, s, klass = self.i + 1, self.s, False
        while i < self.n:
            c = s[i]
            if c == "\\":
                i += 2
                continue
            if c == "[":
                klass = True
            elif c == "]":
                klass = False
            elif c == "/" and not klass:
                break
            elif c == "\n":
                break
            i += 1
        i += 1
        while i < self.n and s[i].isalpha():
            i += 1
        self.i = i
        self.prev = "re"

    def code(self, stop_brace=False):
        s, depth = self.s, 0
        while self.i < self.n:
            c = s[self.i]
            if c in " \t\r\n":
                self.i += 1
                continue
            if s.startswith("//", self.i):
                j = s.find("\n", self.i)
                self.i = self.n if j < 0 else j
                continue
            if s.startswith("/*", self.i):
                j = s.find("*/", self.i + 2)
                self.i = self.n if j < 0 else j + 2
                continue
            if c in "'\"":
                self.string(c)
                continue
            if c == "`":
                self.template()
                continue
            if c == "/" and self.prev in REGEX_AFTER:
                self.regex()
                continue
            if c.isalpha() or c in "_$":
                j = self.i
                while j < self.n and (s[j].isalnum() or s[j] in "_$"):
                    j += 1
                word = s[self.i:j]
                dotted = self.i > 0 and s[self.i - 1] == "." and word in I18N_CALLS
                self.last_ident = None if dotted else word
                self.prev = word
                self.i = j
                continue
            if c.isdigit():
                j = self.i
                while j < self.n and (s[j].isalnum() or s[j] in "._"):
                    j += 1
                self.i, self.prev, self.last_ident = j, "num", None
                continue
            if c == "(":
                callee = self.last_ident if self.prev == self.last_ident else None
                self.frames.append(["(", callee, 0])
            elif c in "{[":
                if c == "{":
                    depth += 1
                self.frames.append([c, None, 0])
            elif c in ")]":
                if self.frames:
                    self.frames.pop()
            elif c == "}":
                if stop_brace and depth == 0:
                    self.i += 1
                    self.prev = "}"
                    return
                depth -= 1
                if self.frames:
                    self.frames.pop()
            elif c == "," and self.frames:
                self.frames[-1][2] += 1
            self.prev = c
            self.last_ident = None
            self.i += 1


def literals(src):
    lx = Lexer(src)
    lx.code()
    return lx.lits


# ---------------------------------------------------------------- what counts as a sentence for a person

TAG = re.compile(r"<(/?)([a-zA-Z][\w-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>")
ATTR = re.compile(r"(?<![\w-])(" + "|".join(re.escape(a) for a in VISIBLE_ATTRS) + r")\s*=\s*(\"[^\"]*\"|'[^']*')")
CODE_PROP = re.compile(r"(?:\b(?:method|type|kind|key|mode|cache|credentials|behavior|block|inline|id|cls|className|bg|tone|art|"
                       r"side|status|sort|account|acct|dir|align|code|event|action|role|cat|tab|icon|font|family|color|sel|href|src|"
                       r"path|route|state|risk|level|game|phase|stage|unit|format|style|fit|position|variant|accent|shape)\s*:)\s*$")


def plain(s):
    return html.unescape(s.replace("\x00", " ")).strip()


def is_words(s):
    """Text inside HTML: anything with a real word in it, except names that never change."""
    s = plain(s)
    if not WORD.search(s):
        return False
    core = s.strip(" .,:;!?·•—–-()[]/|%+*#@0123456789$¢")
    return s not in NO_TRADUCIR and core not in NO_TRADUCIR and bool(WORD.search(core))


def is_prose(s):
    """A string outside HTML: is it words for a person, or code?"""
    s = plain(s)
    if not WORD.search(s) or s in NO_TRADUCIR:
        return False
    if re.match(r"^(https?:|mailto:|data:|/|#|\./|\.\./)", s):
        return False
    if re.search(r"[;{}]|=>|\bfunction\b|\$\{", s):
        return False
    if not re.search(r"\s", s):
        # one word: a capitalised word or a shouted label is text; anything with code characters or lower case is an identifier
        return bool(re.fullmatch(r"[A-ZÁÉÍÓÚÑ¿¡][a-záéíóúüñ]+[.!?…]?|[A-ZÁÉÍÓÚÑ]{3,}[.!?]?|[A-ZÁÉÍÓÚÑ][a-záéíóúüñ]+'[a-z]+[.!?]?", s))
    if re.fullmatch(r"(\s*[a-zA-Z-]+\([^()]*\)\s*)+", s):
        return False                      # a CSS value: translate(...) rotate(...), url(...)
    tokens = [t for t in re.split(r"[\s,]+", s) if t]
    if all(re.fullmatch(r"[.#][\w-]+", t) for t in tokens):
        return False                      # a list of selectors
    if all(t in CLASSES or re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)+", t) or re.fullmatch(r"[a-z]+[A-Z]\w*", t) for t in tokens):
        return False                      # a list of classes, or of event names
    if re.search(r"[\[\]=>*]|:not\(|::?[a-z-]+\(", s) and not re.search(r"[A-Za-z]{3,} [a-z]{3,}", s):
        return False                      # a selector
    if re.fullmatch(r"[\d\s.,%x-]+[a-z]{0,3}", s):
        return False                      # numbers (an SVG path, a size)
    return True


def phrases(lit):
    """The sentences for a person inside one literal (empty when it is code or already goes through t())."""
    if lit.in_t or lit.skip or lit.key:
        return []
    text = lit.text
    if TAG.search(text):
        found = []
        for m in TAG.finditer(text):
            for name, val in ATTR.findall(m.group(3)):
                if is_words(val[1:-1]):
                    found.append(f"[{name}] {plain(val[1:-1])}")
        for piece in TAG.sub("\x01", text).split("\x01"):
            if is_words(piece) and not re.search(r"[{};]\s*$|^\s*[\w-]+=\"", piece.replace("\x00", "")):
                found.append(plain(piece))
        return found
    if lit.callee in CODE_CALLS and not (lit.callee == "replace" and lit.argi == 1):
        return []
    if lit.callee == "setAttribute" and lit.argi == 0:
        return []
    b, a = lit.before, lit.after
    if re.search(r"(===|!==|==|!=|\bcase|\bfrom|\bimport|\bin|\btypeof)$", b) or re.match(r"(===|!==|==|!=)", a):
        return []
    if re.match(r":(?!:)", a) and re.search(r"[{,]$", b):
        return []                         # an object key ('Content-Type': ...), not the ':' of a ternary
    if CODE_PROP.search(b):
        return []
    if re.search(r"\b(dataset\.\w+|\.(className|id|type|name|value|href|src|rel|target|method|key|lang|dir|tagName|code)|"
                 r"\.style\.\w+|\.cssText)\s*=$", b):
        return []
    joined = text.replace("\x00", "") if lit.template else text          # a ${} inside a key like `a:${b}` is not a space between words
    return [plain(text)] if is_prose(joined) else []


def t_keys(lits):
    """The keys passed straight to t(), th() and tp() as literals."""
    keys = []
    for L in lits:
        if L.key and not L.template and not L.skip and is_prose(L.text):
            keys.append(L.text)                      # a sentence in a map that goes to t() (i18n: claves); identifiers in the map are not keys
            continue
        if L.template or L.callee not in I18N_CALLS:
            continue
        if (L.callee in ("t", "th") and L.argi == 0) or (L.callee == "tp" and L.argi in (1, 2)):
            keys.append(L.text)
    return keys


# ---------------------------------------------------------------- the report

def js_files():
    out = []
    for d, _, files in os.walk(JS):
        for n in files:
            if n.endswith(".js"):
                out.append(os.path.relpath(os.path.join(d, n), JS).replace(os.sep, "/"))
    return sorted(out)


def audit():
    with open(EN, encoding="utf-8") as f:
        en = json.load(f)
    rows = {}
    for rel in js_files():
        with open(os.path.join(JS, rel), encoding="utf-8") as f:
            lits = literals(f.read())
        loose = [(L.line, p) for L in lits for p in phrases(L)]
        keys = t_keys(lits)
        missing = sorted({k for k in keys if k not in en})
        rows[rel] = {"loose": loose, "keys": len(keys), "missing": missing}
    return rows


def report(rows):
    lines = [f"{'archivo':34} {'sin t()':>8} {'con t()':>8} {'cobertura':>10} {'sin inglés':>11}"]
    tot_l = tot_k = 0
    for rel, r in rows.items():
        n_l, n_k = len(r["loose"]), r["keys"]
        tot_l, tot_k = tot_l + n_l, tot_k + n_k
        cov = 100.0 if n_l + n_k == 0 else 100.0 * n_k / (n_l + n_k)
        lines.append(f"{rel:34} {n_l:8} {n_k:8} {cov:9.1f}% {len(r['missing']):11}")
    cov = 100.0 if tot_l + tot_k == 0 else 100.0 * tot_k / (tot_l + tot_k)
    lines.append(f"{'TOTAL':34} {tot_l:8} {tot_k:8} {cov:9.1f}%")
    return "\n".join(lines)


class Textos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = audit()
        print("\n" + report(cls.rows), file=sys.stderr)

    def test_no_file_has_more_untranslated_sentences_than_before(self):
        worse = []
        for rel, r in self.rows.items():
            allowed = BASE.get(rel, 0)
            if len(r["loose"]) > allowed:
                sample = "; ".join(f"l.{ln}: {p[:50]}" for ln, p in r["loose"][:4])
                worse.append(f"{rel}: {len(r['loose'])} frases sin t() (lo anotado: {allowed}). Por ejemplo: {sample}")
        self.assertEqual(worse, [], "usa t() de static/js/i18n.js (equipo/contratos/textos.md)")

    def test_every_key_of_an_e5_file_has_its_english(self):
        missing = {rel: r["missing"] for rel, r in self.rows.items() if r["missing"] and rel not in E4_FILES}
        self.assertEqual(missing, {}, "agrega estas frases a static/i18n/en.json")

    def test_e4_keys_without_english_are_listed(self):
        for rel in E4_FILES:
            if rel in self.rows and self.rows[rel]["missing"]:
                print(f"aviso: {rel} usa {len(self.rows[rel]['missing'])} claves sin inglés (E5 las agrega a en.json)", file=sys.stderr)

    def test_the_auditor_catches_what_it_should(self):
        def count(src):
            return sum(len(phrases(L)) for L in literals(src))
        self.assertEqual(count("toast('Hello there, friend');"), 1)
        self.assertEqual(count("toast(t('Hola, amigo'));"), 0)
        self.assertEqual(count("el.innerHTML = `<h2>Markets</h2><p class=\"lede\">${t('Hola')}</p>`;"), 1)
        self.assertEqual(count("el.innerHTML = `<input placeholder=\"Search markets\">`;"), 1)
        self.assertEqual(count("el.innerHTML = `<input placeholder=\"${t('Buscar')}\">`;"), 0)
        self.assertEqual(count("document.querySelector('.btn.btn-primary').classList.add('flash-up');"), 0)
        self.assertEqual(count("if (m.name === 'Yes') go('#/market/1');"), 0)
        self.assertEqual(count("const TABS = [['trending', 'Trending'], ['new', 'New']];"), 2)
        self.assertEqual(count("x = a / b; y = 'Ending soon';"), 1)
        self.assertEqual(count("const r = /^\\/market\\/(\\w+)$/; const s = 'Settled';"), 1)
        self.assertEqual(count("toast(`${n} more notifications.`);"), 1)
        self.assertEqual(count("const s = `--s:${size}px;background:${bg}`;"), 0)
        self.assertEqual(count("toast('Gracias'); // i18n: no"), 0)
        self.assertEqual(count("el.innerHTML = `<b>${esc(name)}</b> · <span>${money(x)}</span>`;"), 0)
        self.assertEqual(count("tp(n, '{n} ficha', '{n} fichas');"), 0)
        self.assertEqual(count("const s = heads ? 'HEADS' : 'TAILS';"), 2)
        self.assertEqual(count("const h = { 'Content-Type': 'application/json' };"), 0)
        self.assertEqual(count("const PINNED = '.side-sticky, .ex-side, .pin';"), 0)
        self.assertEqual(count("el.style.transform = `translate(${x}px, ${y}px) rotate(${r}deg)`;"), 0)

    def test_the_keys_of_t_are_found(self):
        lits = literals("t('Uno'); th('Dos', { a: 1 }); tp(3, '{n} tres', '{n} treses'); obj.t('No'); t(`plantilla`);")
        self.assertEqual(t_keys(lits), ["Uno", "Dos", "{n} tres", "{n} treses"])
        lits = literals("const M = { // i18n: claves ↓\n  a: 'Primera frase',\n  b: 'Segunda',\n}; // i18n: fin\nconst c = 'Fuera';")
        self.assertEqual(t_keys(lits), ["Primera frase", "Segunda"])
        self.assertEqual(sum(len(phrases(L)) for L in lits), 1)


if __name__ == "__main__":
    rows = audit()
    if "--frases" in sys.argv:
        want = sys.argv[sys.argv.index("--frases") + 1]
        for ln, p in rows[want]["loose"]:
            print(f"{ln:5}  {p}")
        for k in rows[want]["missing"]:
            print(f"sin inglés: {k}")
    else:
        print(report(rows))
