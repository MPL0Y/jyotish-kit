"""Layer 2 DSL: parse rule expressions (Lark) and evaluate them against a FactGraph.

Every evaluation returns (value, fact_ids): the facts that decided the value. `and`, `or` and the
quantifiers keep only the operands that decided the result: the witness when true, the failing part when
false. Names resolve in this order: bound variables (predicate parameters, quantifier variables), timing
context (dasha_lord, ...), constants (planets, signs, house and planet groups). Calls resolve to
<school>.<name> predicate, then common.<name> predicate, then a primitive.
"""

import inspect
from functools import lru_cache
from pathlib import Path

import yaml
from lark import Lark, Token, Transformer
from lark.exceptions import LarkError

from jyotish_kit.facts.builders.dignity import EXALTATION
from jyotish_kit.facts.graph import FactGraph
from jyotish_kit.models import PLANETS, SEVEN, SIGN_LORDS, SIGNS

HERE = Path(__file__).parent
PARSER = Lark((HERE / "grammar.lark").read_text(), parser="lalr")
SCHOOLS = ("parashari", "jaimini", "kp", "tajika", "nadi", "lalkitab")
TIMING_VARS = ("dasha_lord", "antardasha_lord", "pratyantardasha_lord")

CONSTANTS: dict[str, object] = {
    **{p: p for p in (*PLANETS, "Lagna")}, **{s: s for s in SIGNS},
    "kendra": [1, 4, 7, 10], "trikona": [1, 5, 9], "dusthana": [6, 8, 12], "upachaya": [3, 6, 10, 11],
    "panaphara": [2, 5, 8, 11], "apoklima": [3, 6, 9, 12], "houses": list(range(1, 13)),
    "planets": list(PLANETS), "seven": list(SEVEN), "nodes": ["Rahu", "Ketu"],
    "natural_benefics": ["Moon", "Mercury", "Jupiter", "Venus"],
    "natural_malefics": ["Sun", "Mars", "Saturn", "Rahu", "Ketu"],
    "movable_signs": list(SIGNS[0::3]), "fixed_signs": list(SIGNS[1::3]), "dual_signs": list(SIGNS[2::3]),
    "odd_signs": list(SIGNS[0::2]), "even_signs": list(SIGNS[1::2]),
    "true": True, "false": False, "none": None,
}


class DSLError(ValueError):
    pass


# ---------------------------------------------------------------- parsing

class _ToAst(Transformer):
    def num(self, t):
        return ("lit", float(t[0]) if "." in t[0] else int(t[0]))

    def string(self, t):
        return ("lit", t[0][1:-1])

    def name(self, t):
        return ("name", str(t[0]))

    def list(self, items):
        return ("list", [i for i in items if i is not None])

    def call(self, t):
        return ("call", str(t[0]), [a for a in t[1:] if a is not None])

    def varga(self, t):
        return ("varga", t[0][1:-1], t[1])

    def quant(self, t):
        return ("quant", str(t[0]), str(t[1]), t[2], t[3])

    def or_(self, t):
        return ("or", t)

    def and_(self, t):
        return ("and", t)

    def not_(self, t):
        return ("not", t[0])

    def cmp(self, t):
        return ("cmp", str(t[1]), t[0], t[2])

    def in_(self, t):
        return ("cmp", "in", t[0], t[1])

    def not_in(self, t):
        return ("cmp", "not in", t[0], t[1])

    def arith(self, t):
        return ("arith", str(t[1]), t[0], t[2])

    def __default_token__(self, tok: Token):
        return tok


@lru_cache(maxsize=4096)
def parse(src: str):
    try:
        return _ToAst().transform(PARSER.parse(src))
    except LarkError as e:
        raise DSLError(f"cannot parse {src!r}: {str(e).splitlines()[0]}") from None


# ---------------------------------------------------------------- primitives

PRIMITIVES: dict[str, object] = {}


def prim(fn):
    """Register fn(env, *args) as a DSL primitive named after the function (trailing _ dropped)."""
    PRIMITIVES[fn.__name__.rstrip("_")] = fn
    return fn


def _house_list(h):
    return h if isinstance(h, list) else [h]


def _sign_idx(s: str) -> int:
    if s not in SIGNS:
        raise DSLError(f"not a sign: {s!r}")
    return SIGNS.index(s)


def _planet(p: str) -> str:
    if p not in PLANETS and p != "Lagna":
        raise DSLError(f"not a planet: {p!r}")
    return p


@prim
def lord(env, h: int) -> str:
    """lord(h): lord of house h in the current varga."""
    return env.need(f"lordship:{env.varga}:H{h}").object


@prim
def lord_of_sign(env, s: str) -> str:
    """lord_of_sign(s): Parashari lord of sign s (Mars for Scorpio, Saturn for Aquarius)."""
    return SIGN_LORDS[_sign_idx(s)]


@prim
def signs_owned(env, p: str) -> list:
    """signs_owned(p): signs whose Parashari lord is p (empty for the nodes)."""
    return [s for i, s in enumerate(SIGNS) if SIGN_LORDS[i] == p]


@prim
def house_of(env, p: str) -> int:
    """house_of(p): whole-sign house of planet p (Lagna = 1) in the current varga."""
    return env.need(f"placement:{env.varga}:{_planet(p)}").attrs["house"]


@prim
def sign_of(env, p: str) -> str:
    """sign_of(p): sign of planet p in the current varga."""
    return env.need(f"placement:{env.varga}:{_planet(p)}").attrs["sign"]


@prim
def in_house(env, p: str, h) -> bool:
    """in_house(p, h): p in house h (h may be a list, e.g. kendra)."""
    return house_of(env, p) in _house_list(h)


@prim
def in_sign(env, p: str, s) -> bool:
    """in_sign(p, s): p in sign s (s may be a list)."""
    return sign_of(env, p) in _house_list(s)


@prim
def occupants(env, h: int) -> list:
    """occupants(h): planets (Rahu, Ketu included) in house h of the current varga."""
    out = [p for p in PLANETS if env.peek(f"placement:{env.varga}:{p}").attrs["house"] == h]
    for p in out:
        env.get(f"placement:{env.varga}:{p}")
    if not out:  # when empty, every placement is the evidence of absence
        for p in PLANETS:
            env.absence(f"placement:{env.varga}:{p}")
    return out


@prim
def occupants_sign(env, s: str) -> list:
    """occupants_sign(s): planets in sign s of the current varga."""
    lagna = _sign_idx(sign_of(env, "Lagna"))
    return occupants(env, (_sign_idx(s) - lagna) % 12 + 1)


@prim
def sign_house(env, s: str) -> int:
    """sign_house(s): the house sign s falls in, counted from the varga Lagna."""
    return (_sign_idx(s) - _sign_idx(sign_of(env, "Lagna"))) % 12 + 1


@prim
def house_sign(env, h: int) -> str:
    """house_sign(h): the sign on house h."""
    return env.need(f"lordship:{env.varga}:H{h}").attrs["sign"]


@prim
def house_from(env, p: str, ref: str) -> int:
    """house_from(p, ref): the house p occupies counted from ref's sign (planet or Lagna), 1..12."""
    return (_sign_idx(sign_of(env, p)) - _sign_idx(sign_of(env, ref))) % 12 + 1


@prim
def sign_from(env, s: str, n: int) -> str:
    """sign_from(s, n): the n-th sign counted from sign s (n = 1 is s itself)."""
    return SIGNS[(_sign_idx(s) + n - 1) % 12]


@prim
def occupants_from(env, ref: str, n: int) -> list:
    """occupants_from(ref, n): planets in the n-th sign from ref's sign (ref a planet or Lagna)."""
    return occupants_sign(env, sign_from(env, sign_of(env, ref), n))


@prim
def houses_of(env, ps: list) -> list:
    """houses_of(ps): sorted distinct houses occupied by the planets ps."""
    return sorted({house_of(env, p) for p in ps})


@prim
def signs_of(env, ps: list) -> list:
    """signs_of(ps): distinct signs occupied by the planets ps, in zodiac order."""
    return sorted({sign_of(env, p) for p in ps}, key=SIGNS.index)


@prim
def house_run(env, start: int, n: int) -> list:
    """house_run(start, n): the n consecutive houses from house start, sorted (house_run(10, 4) = [1, 10, 11, 12])."""
    return sorted((start + i - 1) % 12 + 1 for i in range(n))


def _exaltation(env, p: str) -> int | None:
    if p in EXALTATION:
        return EXALTATION[p][0]
    return env.facts.config.node_exaltation.get(p) if env.facts.config else None


@prim
def exaltation_sign(env, p: str) -> str:
    """exaltation_sign(p): sign where p is exalted (nodes per ChartConfig.node_exaltation)."""
    i = _exaltation(env, _planet(p))
    return SIGNS[i] if i is not None else None


@prim
def debilitation_sign(env, p: str) -> str:
    """debilitation_sign(p): sign opposite p's exaltation sign."""
    i = _exaltation(env, _planet(p))
    return SIGNS[(i + 6) % 12] if i is not None else None


@prim
def exalted_in(env, s: str) -> list:
    """exalted_in(s): planets whose exaltation sign is s."""
    return [p for p in PLANETS if _exaltation(env, p) == _sign_idx(s)]


@prim
def rashi_aspects(env, p: str, q: str) -> bool:
    """rashi_aspects(p, q): Jaimini rashi drishti from p's sign onto q's sign (D1)."""
    return env.has(f"rashi_aspect:D1:{_planet(p)}:{_planet(q)}", f"placement:D1:{p}", f"placement:D1:{q}")


@prim
def aspects(env, p: str, q: str) -> bool:
    """aspects(p, q): p casts graha drishti on planet q (Parashari, node aspects per config)."""
    if q == "Lagna":
        return aspects_house(env, p, 1)
    v = env.varga
    return env.has(f"aspect:{v}:{_planet(p)}:{_planet(q)}", f"placement:{v}:{p}", f"placement:{v}:{q}")


@prim
def aspects_house(env, p: str, h: int) -> bool:
    """aspects_house(p, h): p casts graha drishti on house h."""
    return env.has(f"aspect:{env.varga}:{_planet(p)}:H{h}", f"placement:{env.varga}:{p}")


@prim
def aspected_by(env, target) -> list:
    """aspected_by(t): planets aspecting planet t, or house t when t is a number."""
    obj = f"H{target}" if isinstance(target, int) else target
    return [p for p in PLANETS if env.has(f"aspect:{env.varga}:{p}:{obj}")]


@prim
def conjunct(env, p: str, q: str) -> bool:
    """conjunct(p, q): p and q in the same sign of the current varga."""
    if p == q:
        return False
    a, b = sorted((_planet(p), _planet(q)), key=PLANETS.index)
    return env.has(f"conjunction:{env.varga}:{a}:{b}", f"placement:{env.varga}:{a}", f"placement:{env.varga}:{b}")


@prim
def dignity(env, p: str) -> str:
    """dignity(p): exalted | moolatrikona | own | great_friend | friend | neutral | enemy | great_enemy
    | debilitated, in the current varga."""
    f = env.get(f"dignity:{env.varga}:{_planet(p)}")
    return f.attrs["status"] if f else None


@prim
def relationship(env, p: str, q: str) -> str:
    """relationship(p, q): compound (panchadha) relationship of p towards q (D1)."""
    return env.need(f"relationship:D1:{p}:{q}").attrs["compound"]


@prim
def is_retro(env, p: str) -> bool:
    """is_retro(p): p retrograde at birth (always true for the nodes)."""
    return env.need(f"placement:D1:{_planet(p)}").attrs["retro"]


@prim
def is_combust(env, p: str) -> bool:
    """is_combust(p): p within its combustion orb of the Sun."""
    return env.has(f"combustion:D1:{_planet(p)}", f"placement:D1:{p}", "placement:D1:Sun")


@prim
def lost_war(env, p: str) -> bool:
    """lost_war(p): p is the loser of a graha yuddha."""
    return any(f.attrs["loser"] == p for f in env.facts.query("war") if env.get(f.id))


@prim
def shadbala_ratio(env, p: str) -> float:
    """shadbala_ratio(p): shadbala rupas / required minimum (Sun..Saturn; 0 for the nodes)."""
    f = env.get(f"shadbala:D1:{p}")
    return f.attrs["ratio"] if f else 0.0


@prim
def bhava_bala(env, h: int) -> float:
    """bhava_bala(h): bhava bala of house h in rupas."""
    return env.need(f"bhava_bala:D1:H{h}").attrs["rupas"]


@prim
def bav(env, p: str, s: str) -> int:
    """bav(p, s): bindus in p's bhinnashtakavarga for sign s (before reductions)."""
    return env.need(f"ashtakavarga:BAV:{p}:{s}").attrs["bindus"]


@prim
def sav(env, s: str) -> int:
    """sav(s): sarvashtakavarga bindus of sign s."""
    return env.need(f"ashtakavarga:SAV:{s}").attrs["bindus"]


@prim
def nakshatra_of(env, p: str) -> str:
    """nakshatra_of(p): birth nakshatra of p."""
    return env.need(f"placement:D1:{_planet(p)}").attrs["nakshatra"]


@prim
def nakshatra_lord_of(env, p: str) -> str:
    """nakshatra_lord_of(p): Vimshottari lord of p's nakshatra."""
    return env.need(f"placement:D1:{_planet(p)}").attrs["nakshatra_lord"]


@prim
def degree(env, p: str) -> float:
    """degree(p): degrees of p within its sign (D1)."""
    return env.need(f"placement:D1:{_planet(p)}").attrs["degree"]


@prim
def arc(env, p: str, q: str) -> float:
    """arc(p, q): degrees from p forward (zodiacal order) to q, 0..360 (D1)."""
    a = env.need(f"placement:D1:{_planet(p)}").attrs["longitude"]
    b = env.need(f"placement:D1:{_planet(q)}").attrs["longitude"]
    return (b - a) % 360


@prim
def karaka(env, name: str) -> str:
    """karaka(name): the planet holding chara karaka AK, AmK, BK, MK, PiK, PK, GK or DK."""
    return env.need(f"karaka:D1:{name}").object


@prim
def arudha(env, n) -> str:
    """arudha(n): sign of arudha pada A<n> (n = 1..12), or of "AL" / "UL"."""
    key = f"A{n}" if isinstance(n, int) else n
    return env.need(f"arudha:D1:{key}").attrs["sign"]


@prim
def special_lagna(env, name: str) -> str:
    """special_lagna(name): sign of Karakamsha, BL, HL, GL, SL, VL, IL or BB."""
    return env.need(f"special_lagna:D1:{name}").attrs["sign"]


@prim
def kp_star_lord(env, x) -> str:
    """kp_star_lord(x): KP star lord of cusp x (1..12) or planet x."""
    return env.need(f"kp_lords:KP:{'C%d' % x if isinstance(x, int) else x}").attrs["star_lord"]


@prim
def kp_sub_lord(env, x) -> str:
    """kp_sub_lord(x): KP sub lord of cusp x (1..12) or planet x."""
    return env.need(f"kp_lords:KP:{'C%d' % x if isinstance(x, int) else x}").attrs["sub_lord"]


@prim
def significations(env, p: str) -> list:
    """significations(p): houses p signifies at any of the four KP levels."""
    return env.need(f"kp_significator:KP:{p}").attrs["houses"]


@prim
def signifies(env, p: str, h) -> bool:
    """signifies(p, h): p signifies house h, or any house of the list h (KP, 4 levels)."""
    return bool(set(significations(env, p)) & set(_house_list(h)))


@prim
def exchange_type(env, p: str, q: str) -> str:
    """exchange_type(p, q): "maha" | "khala" | "dainya" if p and q exchange signs in the current
    varga, else none."""
    a, b = sorted((p, q), key=PLANETS.index)
    f = env.get(f"exchange:{env.varga}:{a}:{b}")
    return f.attrs["type"] if f else None


@prim
def paksha(env) -> str:
    """paksha(): "Shukla" (waxing) or "Krishna" (waning) at birth."""
    return env.need("panchanga:birth").attrs["paksha"]


@prim
def day_birth(env) -> bool:
    """day_birth(): born between sunrise and sunset."""
    return env.need("panchanga:birth").attrs["day_birth"]


@prim
def vargottama(env, p: str) -> bool:
    """vargottama(p): p in the same sign in D1 and D9."""
    return env.need(f"sensitive:D1:{p}").attrs["vargottama"]


@prim
def avastha(env, p: str, scheme: str) -> str:
    """avastha(p, scheme): baladi | jagradadi | deeptadi state of p."""
    return env.need(f"avastha:D1:{p}").attrs[scheme]


@prim
def sign_quality(env, s: str) -> str:
    """sign_quality(s): "movable" | "fixed" | "dual"."""
    return ("movable", "fixed", "dual")[_sign_idx(s) % 3]


@prim
def len_(env, xs: list) -> int:
    """len(xs): number of items."""
    return len(xs)


# ---------------------------------------------------------------- predicates

def load_predicates(path: Path = HERE / "predicates.yaml") -> dict[str, dict]:
    out = {}
    for d in yaml.safe_load(path.read_text()):
        key = f"{d['school']}.{d['name']}"
        if key in out:
            raise DSLError(f"duplicate predicate {key}")
        out[key] = d
    return out


PREDICATES = load_predicates()


# ---------------------------------------------------------------- evaluation

class Env:
    def __init__(self, facts: FactGraph, varga: str = "D1", school: str = "common",
                 timing: dict | None = None, vars: dict | None = None, depth: int = 0):
        self.facts, self.varga, self.school = facts, varga, school
        self.timing, self.vars, self.depth = timing or {}, vars or {}, depth
        self.used: set[str] = set()

    def child(self, **kw) -> "Env":
        d = dict(facts=self.facts, varga=self.varga, school=self.school, timing=self.timing, vars=self.vars,
                 depth=self.depth)
        return Env(**(d | kw))

    def peek(self, fid: str):
        return self.facts.get(fid)

    def get(self, fid: str):
        f = self.facts.get(fid)
        if f is not None:
            self.used.add(fid)
        return f

    def need(self, fid: str):
        """The fact, or a DSLError naming it (wrong argument type, or not computed for this chart)."""
        f = self.get(fid)
        if f is None:
            raise DSLError(f"no fact {fid!r}: check the argument types, or that this fact is computed")
        return f

    def absence(self, fid: str) -> None:
        """Record a fact cited only to prove something is absent, as ~<id> (no support for strength weighting)."""
        if self.facts.get(fid) is not None:
            self.used.add("~" + fid)

    def has(self, fid: str, *absent_evidence: str) -> bool:
        """Whether the fact exists; when it does not, the facts that prove its absence are recorded."""
        if self.get(fid) is not None:
            return True
        for e in absent_evidence:
            self.absence(e)
        return False


def resolve_call(name: str, school: str):
    """('predicate', definition) or ('primitive', fn), or None."""
    if "." in name:
        return ("predicate", PREDICATES[name]) if name in PREDICATES else None
    for key in (f"{school}.{name}", f"common.{name}"):
        if key in PREDICATES:
            return "predicate", PREDICATES[key]
    return ("primitive", PRIMITIVES[name]) if name in PRIMITIVES else None


def _value_of_name(env: Env, n: str):
    if n in env.vars:
        return env.vars[n]
    if n in TIMING_VARS:
        if n not in env.timing:
            raise DSLError(f"{n} is only defined when evaluating timing")
        return env.timing[n]
    if n in CONSTANTS:
        return CONSTANTS[n]
    raise DSLError(f"unknown name {n!r}")


def ev(node, env: Env) -> tuple[object, frozenset]:
    op = node[0]
    if op == "lit":
        return node[1], frozenset()
    if op == "name":
        return _value_of_name(env, node[1]), frozenset()
    if op == "list":
        vals, ids = [], frozenset()
        for x in node[1]:
            v, i = ev(x, env)
            vals.append(v)
            ids |= i
        return vals, ids
    if op == "and":
        ids = frozenset()
        for x in node[1]:
            v, i = ev(x, env)
            if not v:
                return False, i
            ids |= i
        return True, ids
    if op == "or":
        ids = frozenset()
        for x in node[1]:
            v, i = ev(x, env)
            if v:
                return True, i
            ids |= i
        return False, ids
    if op == "not":
        v, i = ev(node[1], env)
        return not v, i
    if op in ("cmp", "arith"):
        (a, ia), (b, ib) = ev(node[2], env), ev(node[3], env)
        try:
            return _OPS[node[1]](a, b), ia | ib
        except TypeError as e:
            raise DSLError(f"{node[1]}: {e}") from None
    if op == "varga":
        return ev(node[2], env.child(varga=node[1]))
    if op == "quant":
        _, kind, var, it, body = node
        xs, ids = ev(it, env)
        hits, all_ids = 0, frozenset()
        for x in xs:
            v, i = ev(body, env.child(vars=env.vars | {var: x}))
            if kind == "any" and v:
                return True, ids | i
            if kind == "all" and not v:
                return False, ids | i
            if v:
                hits += 1
            all_ids |= i
        return {"any": False, "all": True, "count": hits}[kind], ids | all_ids
    if op == "call":
        _, name, args = node
        vals, ids = [], frozenset()
        for a in args:
            v, i = ev(a, env)
            vals.append(v)
            ids |= i
        r = resolve_call(name, env.school)
        if r is None:
            raise DSLError(f"unknown function {name!r}")
        kind, target = r
        if kind == "predicate":
            if env.depth > 20:
                raise DSLError(f"predicate recursion too deep at {name}")
            params = target.get("params", [])
            if len(vals) != len(params):
                raise DSLError(f"{name} takes {len(params)} argument(s), got {len(vals)}")
            v, i = ev(parse(target["expr"]), env.child(vars=dict(zip(params, vals)), depth=env.depth + 1,
                                                       school=target["school"] if target["school"] != "common"
                                                       else env.school))
            return v, ids | i
        sub = env.child()
        try:
            v = target(sub, *vals)
        except DSLError:
            raise
        except (KeyError, AttributeError, TypeError, IndexError) as e:
            raise DSLError(f"{name}({', '.join(map(repr, vals))}) failed: {type(e).__name__} {e}") from None
        return v, ids | frozenset(sub.used)
    raise DSLError(f"bad node {op}")


_OPS = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        "in": lambda a, b: a in b, "not in": lambda a, b: a not in b,
        "+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b,
        "/": lambda a, b: a / b, "%": lambda a, b: a % b}


def evaluate(src: str, facts: FactGraph, varga: str = "D1", school: str = "common",
             timing: dict | None = None) -> tuple[object, list[str]]:
    """Evaluate a DSL expression: (value, sorted ids of the facts that decided it). Ids prefixed `~` are facts
    cited only to prove an absence (e.g. the two placements showing that a conjunction does not exist)."""
    v, ids = ev(parse(src), Env(facts, varga, school, timing))
    return v, sorted(ids)


# ---------------------------------------------------------------- static checks

def check(src: str, school: str = "common", allow_timing: bool = False, bound: tuple = ()) -> list[str]:
    """Problems found without a chart: parse errors, unknown names or functions, wrong arity."""
    try:
        tree = parse(src)
    except DSLError as e:
        return [str(e)]
    errs: list[str] = []

    def walk(node, bound):
        op = node[0]
        if op == "name":
            n = node[1]
            if n not in bound and n not in CONSTANTS and not (allow_timing and n in TIMING_VARS):
                errs.append(f"unknown name {n!r}" + (" (timing variables are allowed only in `timing`)"
                                                     if n in TIMING_VARS else ""))
        elif op == "call":
            _, name, args = node
            r = resolve_call(name, school)
            if r is None:
                errs.append(f"unknown function {name!r}")
            else:
                kind, t = r
                if kind == "predicate":
                    n = len(t.get("params", []))
                    ok = len(args) == n
                else:
                    ps = list(inspect.signature(t).parameters.values())[1:]
                    n = len(ps)
                    ok = sum(p.default is inspect.Parameter.empty for p in ps) <= len(args) <= n
                if not ok:
                    errs.append(f"{name} takes {n} argument(s), got {len(args)}")
            for a in args:
                walk(a, bound)
        elif op == "quant":
            walk(node[3], bound)
            walk(node[4], bound | {node[2]})
        elif op == "varga":
            walk(node[2], bound)
        elif op in ("and", "or", "list"):
            for x in node[1]:
                walk(x, bound)
        elif op == "not":
            walk(node[1], bound)
        elif op in ("cmp", "arith"):
            walk(node[2], bound)
            walk(node[3], bound)

    walk(tree, frozenset(bound))
    return errs


def check_predicates() -> list[str]:
    errs = []
    for key, d in PREDICATES.items():
        if d["school"] not in (*SCHOOLS, "common"):
            errs.append(f"predicate {key}: unknown school")
        if not d.get("source"):
            errs.append(f"predicate {key}: missing source")
        errs += [f"predicate {key}: {e}" for e in check(d["expr"], d["school"], bound=tuple(d.get("params", [])))]
    return errs


def reference() -> str:
    """Markdown reference of the language: primitives, predicates and constants (for docs and LLM drafting)."""
    lines = ["Primitives:"]
    lines += [f"- {inspect.getdoc(fn)}" for fn in PRIMITIVES.values()]
    lines.append("\nPredicates (call unqualified inside a rule of that school, or qualified school.name):")
    lines += [f"- {k}({', '.join(d.get('params', []))}): {d.get('doc', '')}" for k, d in PREDICATES.items()]
    lines.append("\nConstants: " + ", ".join(f"{k}={v!r}" if isinstance(v, list) else k for k, v in CONSTANTS.items()))
    lines.append("Timing variables (only in `timing`): " + ", ".join(TIMING_VARS))
    lines.append('Syntax: and/or/not, == != < <= > >=, in / not in, + - * / %, [lists], '
                 'any(x in xs: expr), all(...), count(...), varga("D9").primitive(...).')
    return "\n".join(lines)
