'''
bms2react.py

Converts CICS BMS mapsets (DFHMSD/DFHMDI/DFHMDF) into runnable React 19 +
TypeScript screens that are a faithful, position-accurate replica of the
original 3270 "green screen": every field keeps its exact BMS row/col/length
and is placed on a CSS character grid sized to the map's own SIZE=(rows,cols),
styled dark-terminal/monospace with the real 3270 COLOR mapped to a readable
equivalent - not a restyled "modern form" that only approximates the content.

Pipeline per BMS file:
  1. extract_map_items()   - parse DFHMSD/DFHMDI/DFHMDF statements into flat dicts,
                              correctly rejoining INITIAL text that continues onto a
                              second physical line (BMS column-72/column-16 rule).
  2. build_screen_model()  - classify every field (input / output / static label /
                              skip), detect repeating field groups (e.g. CRDSEL1..7)
                              as table rows, and pull out the function-key legend
                              line (e.g. "ENTER=Sign-on  F3=Exit"). Every surviving
                              field keeps its own row/col/length - there is no
                              label/helper pairing or header/title extraction,
                              because placing each field at its real position
                              reproduces those relationships for free. This model
                              is also written out as <MAP>.model.json for inspection.
  3. build_component()     - renders the model into a single self-contained .tsx
                              file: one CSS-grid canvas (sized to the map's real
                              SIZE=(rows,cols)) holding every field positioned at
                              its exact gridRow/gridColumn, a repeating-group table
                              where detected, a conditional ERRMSG/INFOMSG region,
                              and a window keydown handler wired to the real
                              function keys (Enter/F3/F4/F5/F7/F8/F12/...).

Author: KhangNV19 (original), extended 2026 to follow the BMS->React modernization
spec (intermediate model, real field classification, position-accurate terminal
replica, repeating-group tables, PF-key wiring, ERRMSG/INFOMSG alerts).
'''
import argparse
import os
import re
import json


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 3270 COLOR -> Tailwind text color readable on the black terminal background the
# generated screen now renders on, matching a real TN3270 emulator's palette
# instead of being restyled for a light modern UI.
COLOR_TOKEN_MAP = {
    'BLUE': 'text-blue-400',
    'TURQUOISE': 'text-cyan-400',
    'GREEN': 'text-green-400',
    'YELLOW': 'text-yellow-300',
    'RED': 'text-red-400',
    'PINK': 'text-pink-400',
    'NEUTRAL': 'text-slate-200',
    # No COLOR= clause at all defaults to classic green-screen green, not black-on-black.
    'DEFAULT': 'text-green-400',
}

# BMS HILIGHT value -> extra Tailwind class (on top of BRT -> font-semibold).
HILIGHT_TOKEN_MAP = {
    'UNDERLINE': 'underline',
    'BLINK': 'animate-pulse',
    # Real inverse video: swap foreground/background instead of just bolding text.
    'REVERSE': 'bg-green-400 text-black',
}

# A real 3270 Model 2 screen is 24 rows x 80 columns; DFHMDI's own SIZE=(rows,cols)
# overrides this when present. The generated grid is sized to this exactly so every
# field's row/col lines up pixel-for-pixel with the original map.
DEFAULT_GRID_ROWS = 24
DEFAULT_GRID_COLS = 80

# Real function-key legend line, e.g. "ENTER=Sign-on  F3=Exit  F7=Backward F8=Forward".
# Real CardDemo maps use either convention - COPAU01 double-spaces between keys, but
# COACTUP's FKEYS field (LENGTH=21, no room to spare) single-spaces them
# ('ENTER=Process F3=Exit') - requiring 2+ spaces silently dropped the first key on
# every tightly-packed field. The lookahead already disambiguates "is the next token
# a real key=value pair" independently of how much whitespace precedes it (so a
# multi-word label like "Mark/Remove Fraud" still isn't split early), so 1+ spaces
# is both necessary and sufficient.
FUNCTION_KEY_LEGEND_RE = re.compile(
    r'(ENTER|PF\d{1,2}|F\d{1,2})\s*=\s*([^=]*?)(?=\s+(?:ENTER|PF\d{1,2}|F\d{1,2})\s*=|$)',
    re.IGNORECASE,
)

# Repeating field group naming convention, e.g. CRDSEL1, ACCTNO12
GROUP_NAME_RE = re.compile(r'^([A-Za-z]+)(\d{1,3})$')

# A field's own INITIAL is a pure placeholder/underline (not real text) when it is
# entirely made of one decorative character (e.g. '________' on a password field).
DECORATIVE_INITIAL_RE = re.compile(r'^[_\-\.\s]*$')

PF_KEY_TO_JS_KEY = {
    'ENTER': 'Enter',
    'PF3': 'F3', 'F3': 'F3',
    'PF4': 'F4', 'F4': 'F4',
    'PF5': 'F5', 'F5': 'F5',
    'PF7': 'F7', 'F7': 'F7',
    'PF8': 'F8', 'F8': 'F8',
    'PF12': 'F12', 'F12': 'F12',
}


# ---------------------------------------------------------------------------
# Step 1: low-level BMS parsing
# ---------------------------------------------------------------------------

def get_value(search_result):
    """
    Extracts the value from a search result string.

    Parameters:
    - search_result (str): The input search result string.

    Returns:
    - str or list: The extracted value.
    """
    value = ""
    if search_result.find("=") == -1:
        find_match = re.compile(r"'(.*?)'").search(search_result)
        if find_match:
            value = find_match.group(0)
    elif not search_result.find(")") == -1:
        value = (
            search_result[search_result.find("=") + 1:]
            .replace("(", "")
            .replace(")", "")
            .split(",")
        )
    elif search_result.find(")") == -1:
        value = search_result[search_result.find("=") + 1:]
    if value and value[0] == "'" and value[-1] == "'":
        value = value.removeprefix("'").removesuffix("'")
    return value


def normalize_continued_text(raw):
    """
    Rejoins a BMS INITIAL value that was split across physical lines.

    BMS fixed format: a non-blank character in column 72 means the statement
    continues on the next line, resuming at column 16. Real example (CardDemo
    COSGN00, unnamed field at row 17):
        INITIAL='Type your User ID and Password, then press ENTE-
                       R:'
    must become "Type your User ID and Password, then press ENTER:" - direct
    concatenation, no inserted space, no leftover '-' or indentation.

    Also un-escapes '&&' (BMS escaping for a literal '&') to '&'.
    """
    if not raw:
        return raw
    if "\n" not in raw:
        return raw.replace("&&", "&")
    lines = raw.split("\n")
    result = lines[0]
    for cont in lines[1:]:
        if result.endswith("-"):
            result = result[:-1]
        # Continuation content starts at column 16 (index 15). Fall back to a
        # plain lstrip if the line is shorter/irregular rather than losing data.
        if len(cont) > 15 and cont[:15].strip() == "":
            stripped = cont[15:]
        else:
            stripped = cont.lstrip()
        result += stripped
    return result.replace("&&", "&")


def extract_property(current_item):
    """
    Extracts properties from a given item in the map file.

    Parameters:
    - current_item (str): The input map item string.

    Returns:
    - dict: Dictionary containing extracted properties.
    """
    pattern_type = re.compile(r"TYPE\s*=\s*([A-Z]+)")
    pattern_mode = re.compile(r"MODE\s*=\s*([A-Z]+)")
    pattern_lang = re.compile(r"LANG\s*=\s*([A-Z]+)")
    pattern_storage = re.compile(r"STORAGE\s*=\s*(?:\(([A-Z,]+)\)|([A-Z]+))")
    pattern_ctrl = re.compile(r"CTRL\s*=\s*(?:\(([A-Z,]+)\)|([A-Z]+))")
    pattern_term = re.compile(r"TERM\s*=\s*([A-Za-z0-9]+)")
    pattern_tioapfx = re.compile(r"TIOAPFX\s*=\s*([A-Z]+)")
    pattern_pos = re.compile(r"POS=\((\d+),(\d+)\)")
    pattern_size = re.compile(r"SIZE=\((\d+),(\d+)\)")
    pattern_length = re.compile(r"LENGTH=(\d+)")
    pattern_initial = re.compile(r"INITIAL='(.*?)'", re.DOTALL)
    pattern_title = re.compile(r"TITLE \'(.+?)\'")
    pattern_color = re.compile(r"COLOR\s*=\s*([A-Za-z0-9]+)")
    pattern_hilight = re.compile(r"HILIGHT\s*=\s*([A-Z]+)")
    pattern_picin = re.compile(r"PICIN\s*=\s*'([^']*)'")
    pattern_picout = re.compile(r"PICOUT\s*=\s*'([^']*)'")
    pattern_occurs = re.compile(r"OCCURS\s*=\s*([0-9]+)")
    pattern_mapatts = re.compile(r"MAPATTS\s*=\s*(?:\(([A-Z,]+)\)|([A-Z]+))")
    pattern_attrb = re.compile(r"ATTRB\s*=\s*(?:\(([A-Z,]+)\)|([A-Z]+))")
    data = {}
    current_item = current_item.replace(" = ", "=")
    if re.match(r"\s*DFHM\w+\s+", current_item):
        data["define"] = (
            re.match(r"\s*DFHM\w+\s+", current_item).group(0).replace(" ", "")
        )

    elif re.match(r"\s*([A-Z0-9]+)\s+DFHM\w+\s+", current_item):
        original_list = (
            re.match(r"\s*([A-Z0-9]+)\s+DFHM\w+\s+", current_item).group(0).split(" ")
        )
        filtered_list = [value for value in original_list if value.strip()]
        data["name"] = filtered_list[0]
        data["define"] = filtered_list[1]
    if pattern_title.search(current_item):
        search = pattern_title.search(current_item).group(0)
        data["title"] = get_value(search)
    if pattern_type.search(current_item):
        search = pattern_type.search(current_item).group(0)
        data["type"] = get_value(search)
    if pattern_mode.search(current_item):
        search = pattern_mode.search(current_item).group(0)
        data["mode"] = get_value(search)
    if pattern_lang.search(current_item):
        search = pattern_lang.search(current_item).group(0)
        data["lang"] = get_value(search)
    if pattern_storage.search(current_item):
        search = pattern_storage.search(current_item).group(0)
        data["storage"] = get_value(search)
    if pattern_ctrl.search(current_item):
        search = pattern_ctrl.search(current_item).group(0)
        data["ctrl"] = get_value(search)
    if pattern_term.search(current_item):
        search = pattern_term.search(current_item).group(0)
        data["term"] = get_value(search)
    if pattern_tioapfx.search(current_item):
        search = pattern_tioapfx.search(current_item).group(0)
        data["tioapfx"] = get_value(search)
    if pattern_pos.search(current_item):
        m = pattern_pos.search(current_item)
        data["pos"] = [m.group(1), m.group(2)]
        data["row"] = int(m.group(1))
        data["col"] = int(m.group(2))
    if pattern_size.search(current_item):
        m = pattern_size.search(current_item)
        data["size"] = (int(m.group(1)), int(m.group(2)))
    if pattern_length.search(current_item):
        search = pattern_length.search(current_item).group(0)
        data["length"] = int(get_value(search))
    if pattern_initial.search(current_item):
        raw_initial = pattern_initial.search(current_item).group(1)
        start_with_uppercase_pattern = re.compile(r"\*+\s*[A-Z]+")
        start_with_lowercase_pattern = re.compile(r"\*+\s*[a-z.]+")
        cleaned = raw_initial
        if start_with_lowercase_pattern.search(current_item):
            cleaned = re.sub(r"(\s*)(\*+)(\s*)", r"", raw_initial)
        elif start_with_uppercase_pattern.search(current_item):
            cleaned = re.sub(r"(\s*)(\*+)(\s*)", r" ", raw_initial)
        data["initial"] = normalize_continued_text(cleaned)
    if pattern_hilight.search(current_item):
        search = pattern_hilight.search(current_item).group(0)
        data["hilight"] = get_value(search)
    if pattern_picin.search(current_item):
        data["picin"] = pattern_picin.search(current_item).group(1)
    if pattern_picout.search(current_item):
        data["picout"] = pattern_picout.search(current_item).group(1)
    if pattern_mapatts.search(current_item):
        search = pattern_mapatts.search(current_item).group(0)
        data["mapatts"] = get_value(search)
    if pattern_attrb.search(current_item):
        search = pattern_attrb.search(current_item).group(0)
        data["attrb"] = get_value(search)
    else:
        pattern_attrb_bare = re.compile(r"ATTRB\s*=\s*([A-Za-z0-9]+)")
        if pattern_attrb_bare.search(current_item):
            search = pattern_attrb_bare.search(current_item).group(0)
            data["attrb"] = get_value(search)
    if "attrb" in data and isinstance(data["attrb"], str):
        data["attrb"] = [data["attrb"]] if data["attrb"] else []
    if pattern_color.search(current_item):
        search = pattern_color.search(current_item).group(0)
        data["color"] = get_value(search)
    if pattern_occurs.search(current_item):
        search = pattern_occurs.search(current_item).group(0)
        data["occurs"] = get_value(search)
    return data


def extract_map_items(file_path):
    """
    Extracts map items from a given map file.

    Parameters:
    - file_path (str): The path to the map file.

    Returns:
    - list: List of dictionaries containing extracted map items.
    """
    map_items = []
    with open(file_path, "r", encoding="utf8") as file:
        current_item = ""
        new_item = ""
        for index, line in enumerate(file):
            if re.match(r"\s*DFHM\w+\s+", line):
                new_item += line
            elif re.match(r"\s*([A-Z0-9]+)\s+DFHM\w+\s+", line):
                new_item += line
            else:
                current_item += line
            if new_item or (re.match(r"\s*END\s*", line) is not None):
                data = extract_property(current_item)
                map_items.append(data)
                current_item = new_item
                new_item = ""
        file.close()
    return map_items


# ---------------------------------------------------------------------------
# Step 2: intermediate model - classification, grouping, layout planning
# ---------------------------------------------------------------------------

def is_field_definition(item):
    return item.get("define") == "DFHMDF" and "length" in item


def extract_grid_size(map_items):
    """Real screen dimensions from the map's own DFHMDI SIZE=(rows,cols), falling
    back to the standard 3270 Model 2 size (24x80) when absent."""
    for item in map_items:
        if item.get("define") == "DFHMDI" and "size" in item:
            return item["size"]
    return (DEFAULT_GRID_ROWS, DEFAULT_GRID_COLS)


def classify_field(field):
    """
    Classifies one DFHMDF field per the modernization spec:
      - named + UNPROT               -> 'input'  (user enters data)
      - named + ASKIP/PROT (default) -> 'output' (server-supplied display value)
      - unnamed + has INITIAL        -> 'label'  (static text)
      - unnamed + UNPROT/DRK         -> 'skip'   (technical field, no business meaning)
      - anything else unnamed        -> 'skip'
    A missing ATTRB clause defaults to ASKIP (read-only), per real BMS semantics.
    """
    if field.get("length", 0) == 0:
        return "skip"
    attrb = field.get("attrb", [])
    name = field.get("name")
    is_unprot = "UNPROT" in attrb
    if name:
        if is_unprot:
            return "input"
        # DRK without UNPROT is a real, if unusual, BMS combination: a named,
        # protected field that is deliberately invisible on the 3270 (DRK means
        # "dark" regardless of protection). It is an internal bookkeeping value
        # (e.g. CardDemo's CRDSTPn), not something a user should ever see - the
        # modernized screen must not surface it just because it has a name.
        if "DRK" in attrb:
            return "skip"
        return "output"
    if is_unprot or "DRK" in attrb:
        return "skip"
    if field.get("initial"):
        return "label"
    return "skip"


def css_class_for(field):
    """3270 COLOR/HILIGHT/BRT -> semantic Tailwind classes (never a raw color name)."""
    color = (field.get("color") or "DEFAULT").upper()
    classes = [COLOR_TOKEN_MAP.get(color, COLOR_TOKEN_MAP["DEFAULT"])]
    attrb = field.get("attrb", [])
    if "BRT" in attrb:
        classes.append("font-semibold")
    hilight = (field.get("hilight") or "").upper()
    if hilight and hilight != "OFF":
        classes.append(HILIGHT_TOKEN_MAP.get(hilight, ""))
    return " ".join(c for c in classes if c).strip()


def is_decorative_initial(text):
    return bool(DECORATIVE_INITIAL_RE.match(text or ""))




def detect_function_keys(candidate_fields):
    """
    Finds the function-key legend line(s) (e.g. "ENTER=Sign-on  F3=Exit") among the
    candidate fields and returns the parsed, merged [{key, action, label}] list used
    to wire the real keyboard handler. This is a pure scan - every field keeps
    rendering normally wherever build_screen_model places it (the legend text is
    real on-screen content too, not something to hide once parsed).

    The legend is usually unnamed static text (kind 'label'), but some BMS maps
    (e.g. CardDemo's COACTUP/COCRDSL/COCRDUP/COTRTUP) instead give this same text
    to a NAMED, protected field (e.g. "FKEYS") so the program can swap it at
    runtime - classify_field() correctly calls that 'output', not 'label', per
    real BMS semantics. Scanning only 'label' fields silently dropped the legend
    - and with it every keyboard handler - on exactly those screens. candidate_fields
    must include both kinds so this is found either way.

    Some maps (e.g. CardDemo's COTRTLI) go further and split the legend across
    several separate single-key fields (BUTNF02="F2=Add", BUTNF03="F3=Exit", ...)
    instead of one combined line. Every matching field is scanned and merged into
    one list (in field order) rather than stopping at the first match, so none of
    these per-key fields are silently dropped either.
    """
    keys = []
    for field in candidate_fields:
        text = field.get("initial") or ""
        matches = list(FUNCTION_KEY_LEGEND_RE.finditer(text))
        if len(matches) >= 1 and "=" in text:
            for m in matches:
                raw_key = m.group(1).upper()
                label = m.group(2).strip()
                js_key = PF_KEY_TO_JS_KEY.get(raw_key, raw_key)
                action = "ENTER" if raw_key == "ENTER" else re.sub(r"^F", "PF", raw_key)
                keys.append({"key": js_key, "action": action, "label": label or action})
    return keys


def detect_repeating_groups(fields):
    """
    Groups fields whose name is <prefix><index> (e.g. CRDSEL1..7, ACCTNO1..7) into
    table columns, clustering columns that share the exact same set of indexes into
    one repeating table - this is how a real BMS selection list (CardDemo COCRDLI
    style) is represented. Returns (tables, remaining_fields).
    """
    by_prefix = {}
    for f in fields:
        name = f.get("name") or ""
        m = GROUP_NAME_RE.match(name)
        if not m:
            continue
        prefix, idx = m.group(1), int(m.group(2))
        by_prefix.setdefault(prefix, []).append((idx, f))

    candidate_prefixes = {p: items for p, items in by_prefix.items() if len(items) >= 2}
    if not candidate_prefixes:
        return [], fields

    idxset_to_prefixes = {}
    for prefix, items in candidate_prefixes.items():
        idxset = tuple(sorted(idx for idx, _ in items))
        idxset_to_prefixes.setdefault(idxset, []).append(prefix)

    tables = []
    consumed_names = set()
    for idxset, prefixes in idxset_to_prefixes.items():
        if len(idxset) < 2 or len(prefixes) < 2:
            continue

        def avg_col(p):
            items = candidate_prefixes[p]
            return sum(it.get("col", 0) for _, it in items) / len(items)

        ordered_prefixes = sorted(prefixes, key=avg_col)
        rows = []
        for idx in idxset:
            row_entry = {}
            for p in ordered_prefixes:
                match = next((it for i2, it in candidate_prefixes[p] if i2 == idx), None)
                if match:
                    row_entry[p] = match
                    consumed_names.add(match.get("name"))
            rows.append(row_entry)
        tables.append({
            "columns": ordered_prefixes,
            "columnKind": {p: classify_field(candidate_prefixes[p][0][1]) for p in ordered_prefixes},
            "rowIndexes": list(idxset),
            "rows": rows,
        })

    remaining = [f for f in fields if f.get("name") not in consumed_names]
    return tables, remaining


def build_screen_model(map_items, map_name):
    """
    Builds the intermediate model for a position-accurate terminal replica: every
    surviving field keeps its own real row/col/length/color so the codegen step can
    place it on a CSS grid cell-for-cell with the original 3270 map. There is no
    label/helper pairing and no separate header/title extraction - placing every
    field (label, input, output) at its own real position already reproduces
    whatever visual relationship it had with its neighbors in the source map, for
    free. This model is also written out as <MAP>.model.json for inspection.
    """
    grid_rows, grid_cols = extract_grid_size(map_items)

    fields = [f for f in map_items if is_field_definition(f)]
    for f in fields:
        f["kind"] = classify_field(f)

    visible = [
        f for f in fields
        if f["kind"] != "skip" and not (f["kind"] == "label" and is_decorative_initial(f.get("initial")))
    ]

    function_keys = detect_function_keys([f for f in visible if f["kind"] in ("label", "output")])

    errmsg_field = next((f for f in visible if (f.get("name") or "").upper() == "ERRMSG"), None)
    infomsg_field = next((f for f in visible if (f.get("name") or "").upper() == "INFOMSG"), None)
    body_fields = [f for f in visible if f is not errmsg_field and f is not infomsg_field]

    tables, body_fields = detect_repeating_groups(body_fields)

    def field_record(f):
        return {
            "name": f.get("name"),
            "kind": f.get("kind"),
            "row": f.get("row"),
            "col": f.get("col"),
            "length": f.get("length"),
            "attrb": f.get("attrb", []),
            "color": f.get("color"),
            "hilight": f.get("hilight"),
            "picin": f.get("picin"),
            "picout": f.get("picout"),
            "initial": f.get("initial"),
            "isDark": "DRK" in f.get("attrb", []),
            "isNumeric": "NUM" in f.get("attrb", []),
            "autoFocus": "IC" in f.get("attrb", []),
        }

    return {
        "mapName": map_name,
        "gridRows": grid_rows,
        "gridCols": grid_cols,
        "fields": [
            field_record(f)
            for f in sorted(body_fields, key=lambda x: (x.get("row", 0), x.get("col", 0)))
        ],
        "tables": tables,
        "errmsgField": errmsg_field.get("name") if errmsg_field else None,
        "errmsgRow": errmsg_field.get("row") if errmsg_field else None,
        "errmsgCol": errmsg_field.get("col") if errmsg_field else None,
        "errmsgLength": errmsg_field.get("length") if errmsg_field else None,
        "infomsgField": infomsg_field.get("name") if infomsg_field else None,
        "infomsgRow": infomsg_field.get("row") if infomsg_field else None,
        "infomsgCol": infomsg_field.get("col") if infomsg_field else None,
        "infomsgLength": infomsg_field.get("length") if infomsg_field else None,
        "functionKeys": function_keys,
    }


# ---------------------------------------------------------------------------
# Step 3: codegen - intermediate model -> a single self-contained .tsx file
# ---------------------------------------------------------------------------

def esc(text):
    """
    Escapes text for embedding inside a single-quoted JS string literal, e.g.
    {'<result>'}. Every piece of literal text parsed from BMS source (labels,
    static text, button labels) MUST be emitted this way - never as a raw JSX
    text node - because BMS content routinely contains '{', '}', '<', '>', '&'
    (ASCII-art banners, box-drawing characters) which JSX would otherwise parse
    as markup/expression syntax instead of literal text.

    Does NOT trim leading/trailing whitespace: on the position-accurate terminal
    grid, a field's own INITIAL text is sometimes padded with leading spaces to
    center or indent it within a LENGTH wider than the visible text - stripping
    that would silently shift it out of its real position.
    """
    return (text or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")


def jsx_text(text):
    """Wraps literal text as a safe JS string-literal JSX expression: {'...'}"""
    return "{'" + esc(text) + "'}"


def field_var(name):
    return (name or "field").lower()


def grid_style(row, col, length):
    """Inline style placing one element at its real BMS row/col on the character
    grid - `gridColumn` spans exactly `length` 1ch-wide track columns, so the
    rendered width always matches the field's declared LENGTH."""
    return f"style={{{{ gridRow: {row or 1}, gridColumn: '{col or 1} / span {max(length or 1, 1)}' }}}}"


def render_positioned_field(field):
    """Renders one field (label/output/input) at its exact grid position. A label
    is static text; an output field is read-only server-supplied text; an input
    is a real <input> the user can type into - all three are just "a cell on the
    screen" in a position-accurate replica, so there is no label/input pairing or
    wrapper markup here, unlike a conventional form layout."""
    row, col, length = field.get("row"), field.get("col"), field.get("length") or 1
    style = grid_style(row, col, length)
    color_class = css_class_for(field)

    if field["kind"] == "input":
        var = field_var(field["name"])
        input_type = "password" if field.get("isDark") else "text"
        extra_props = ['autoComplete="off"']
        if field.get("isNumeric"):
            extra_props.append('inputMode="numeric"')
        if field.get("autoFocus"):
            extra_props.append("autoFocus")
        extra = " ".join(extra_props)
        return f"""<input
          {style}
          id="{var}"
          name="{var}"
          type="{input_type}"
          maxLength={{{length}}}
          {extra}
          disabled={{isLoading}}
          value={{formData.{var} ?? ''}}
          onChange={{(e) => handleInputChange('{var}', e.target.value)}}
          className="bg-black {color_class} font-mono border-0 border-b border-dotted border-green-900 focus:outline-none focus:border-solid focus:border-cyan-400 disabled:opacity-60"
        />"""

    text_jsx = jsx_text(field.get("initial") or "")
    if field["kind"] == "label":
        return f'<span {style} className="whitespace-pre {color_class}">{text_jsx}</span>'
    # output - server-supplied, read from receivedData
    var = field_var(field["name"])
    return f'<span {style} className="whitespace-pre {color_class}">{{receivedData.{var} ?? \'\'}}</span>'


def render_tables(tables):
    """A repeating-group list (e.g. CardDemo's COCRDLI card list) still renders as
    a real HTML table rather than one positioned <span> per cell - the terminal
    only ever shows a fixed number of visible rows at a time (scrolled via
    PF7/PF8), so a table is the closer real-world equivalent of the 3270 behavior
    anyway. It's placed at the grid row just above the table's own first declared
    data row/column so it still lines up with the rest of the screen, and kept in
    the same dark/monospace palette as everything else."""
    if not tables:
        return ""
    blocks = []
    for table in tables:
        columns = table["columns"]
        kind = table["columnKind"]
        first_col_var = field_var(columns[0])
        start_row = min((cell.get("row", 999) for row in table["rows"] for cell in row.values()), default=1)
        start_col = min((cell.get("col", 999) for row in table["rows"] for cell in row.values()), default=1)
        wrapper_style = f"style={{{{ gridRow: '{max(start_row - 1, 1)} / span 20', gridColumn: '{start_col} / -1' }}}}"
        headers = "".join(
            "<th className=\"px-2 text-left font-normal text-green-600\">" + jsx_text(col) + "</th>"
            for col in columns
        )
        cells = []
        for col in columns:
            var = field_var(col)
            if kind.get(col) == "input":
                cells.append(
                    f"<td className=\"px-2\"><input value={{(formData.{first_col_var}Rows?.[i]?.{var}) ?? ''}} "
                    f"onChange={{(e) => handleRowChange('{first_col_var}', i, '{var}', e.target.value)}} "
                    f"disabled={{isLoading}} className=\"bg-black text-green-400 font-mono border-0 border-b border-dotted border-green-900 focus:outline-none disabled:opacity-60\" /></td>"
                )
            else:
                cells.append(f"<td className=\"px-2 font-mono text-green-400 whitespace-pre\">{{row.{var} ?? ''}}</td>")
        cells_joined = "".join(cells)
        blocks.append(f"""<div {wrapper_style} className="overflow-x-auto">
          <table className="text-xs font-mono border-collapse">
            <thead><tr>{headers}</tr></thead>
            <tbody>
              {{(receivedData.{first_col_var}Rows || []).map((row: any, i: number) => (
                <tr key={{i}}>{cells_joined}</tr>
              ))}}
            </tbody>
          </table>
        </div>""")
    return "\n".join(blocks)


def render_alert_region(model):
    """ERRMSG/INFOMSG keep their own real grid position (every real 3270 map has a
    dedicated message line) instead of floating as a modern alert card - red/green
    text in place, matching how the original screen actually reports status.

    errMsg itself is always rendered (falling back to the map's last row when the
    source has no real ERRMSG field) rather than only when model["errmsgField"]
    exists: errMsg also carries client-side failures (network errors, etc.) that
    have nothing to do with a named BMS field, and errMsg must be read somewhere
    regardless - the `useState` declaring it is unconditional - or an otherwise
    error-free screen fails `tsc -b` with "declared but never read".
    """
    parts = []
    if model["errmsgField"]:
        style = grid_style(model["errmsgRow"], model["errmsgCol"], model["errmsgLength"])
    else:
        style = grid_style(model["gridRows"], 1, model["gridCols"])
    parts.append(f'{{errMsg && <span {style} role="alert" className="whitespace-pre text-red-400">{{errMsg}}</span>}}')
    if model["infomsgField"]:
        var = field_var(model["infomsgField"])
        style = grid_style(model["infomsgRow"], model["infomsgCol"], model["infomsgLength"])
        parts.append(
            f'{{receivedData.{var} && <span {style} role="status" className="whitespace-pre text-green-400">{{receivedData.{var}}}</span>}}'
        )
    return "\n".join(parts)


def render_function_key_effect(function_keys):
    if not function_keys:
        return ""
    entries = ", ".join(
        f"{{ key: '{fk['key']}', action: '{fk['action']}' }}" for fk in function_keys
    )
    return f"""
  const FUNCTION_KEYS = [{entries}];
  useEffect(() => {{
    const handler = (e: KeyboardEvent) => {{
      const match = FUNCTION_KEYS.find((fk) => fk.key === e.key);
      if (match) {{
        e.preventDefault();
        submitAction(match.action);
      }}
    }};
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }}, [formData]);
"""


def build_state_types(model):
    output_names = set()
    input_names = set()
    for f in model["fields"]:
        if f["kind"] == "output":
            output_names.add(field_var(f["name"]))
        elif f["kind"] == "input":
            input_names.add(field_var(f["name"]))
    if model["errmsgField"]:
        output_names.add(field_var(model["errmsgField"]))
    if model["infomsgField"]:
        output_names.add(field_var(model["infomsgField"]))
    for t in model["tables"]:
        first_col_var = field_var(t["columns"][0])
        output_names.add(f"{first_col_var}Rows")
        for col in t["columns"]:
            if t["columnKind"].get(col) == "input":
                input_names.add(f"{first_col_var}Rows")

    # A "...Rows" entry (an editable table's rows) is an array of partial row objects
    # - see handleRowChange's `rows[index] = { ...(rows[index] || {}), [field]: value }`
    # below - never a plain string like every other formInput field. Typing/initializing
    # it as `string` made every per-cell `formData.xRows?.[i]?.field` access a real
    # `tsc -b` error (property access on type 'string').
    def is_rows_field(n):
        return n.endswith("Rows")

    input_type = "\n  ".join(
        f"{n}: {'Record<string, string>[]' if is_rows_field(n) else 'string'};"
        for n in sorted(input_names)
    ) or "[key: string]: string;"
    # Optional: every output field (including errmsgField/infomsgField/table "...Rows"
    # names) is populated asynchronously from the API response, never in the initial
    # useState() literal below - declaring them required made every single generated
    # screen fail `tsc -b` with "missing properties ... errmsg, infomsg" (and more for
    # screens with tables), since TypeScript correctly rejected the initial object
    # literal against the (wrongly) required type.
    output_type = "\n  ".join(f"{n}?: any;" for n in sorted(output_names)) or "[key: string]: any;"
    input_initial = "\n    ".join(
        f"{n}: {'[]' if is_rows_field(n) else chr(39) + chr(39)},"
        for n in sorted(input_names)
    ) or ""
    output_initial_parts = []
    for f in model["fields"]:
        if f["kind"] == "output":
            init = esc(f.get("initial") or "")
            output_initial_parts.append(f"{field_var(f['name'])}: '{init}',")
    output_initial = "\n    ".join(output_initial_parts)
    return input_type, output_type, input_initial, output_initial


def build_component(model):
    map_name = model["mapName"]
    grid_rows, grid_cols = model["gridRows"], model["gridCols"]
    fields_jsx = "\n          ".join(render_positioned_field(f) for f in model["fields"])
    tables_jsx = render_tables(model["tables"])
    alert_jsx = render_alert_region(model)
    key_effect = render_function_key_effect(model["functionKeys"])
    input_type, output_type, input_initial, output_initial = build_state_types(model)

    # Generating these unconditionally produced a real `tsc -b` error
    # ("'handleInputChange'/'handleRowChange' is declared but its value is never
    # read") on every screen with no plain input field (e.g. COPAU01, entirely
    # view-only) or no editable table column (e.g. COACTVW's read-only ACSADL
    # table) - noUnusedLocals correctly flags a function nothing calls.
    has_plain_inputs = any(f["kind"] == "input" for f in model["fields"])
    has_editable_tables = any(
        t["columnKind"].get(col) == "input" for t in model["tables"] for col in t["columns"]
    )

    input_change_fn = ""
    if has_plain_inputs:
        input_change_fn = """
  const handleInputChange = (name: string, value: string) => {
    setFormData((prev: any) => ({ ...prev, [name]: value }));
  };
"""

    # setFormData is called by handleInputChange and/or handleRowChange - if neither
    # exists (a fully view-only screen like COPAU01), destructuring it anyway is
    # another "declared but never read" tsc error.
    form_data_destructure = (
        "formData, setFormData" if (has_plain_inputs or has_editable_tables) else "formData"
    )

    row_change_fn = ""
    if has_editable_tables:
        row_change_fn = """
  const handleRowChange = (tableKey: string, index: number, field: string, value: string) => {
    setFormData((prev: any) => {
      const rows = [...(prev[`${tableKey}Rows`] || [])];
      rows[index] = { ...(rows[index] || {}), [field]: value };
      return { ...prev, [`${tableKey}Rows`]: rows };
    });
  };
"""

    return f"""import {{ useEffect, useState }} from 'react';
import {{ useNavigate }} from 'react-router-dom';
import axios from 'axios';

type formInput = {{
  {input_type}
}}

type formOutput = {{
  {output_type}
}}

export function {map_name}() {{
  const navigate = useNavigate();
  const [{form_data_destructure}] = useState<formInput>({{
    {input_initial}
  }});
  const [receivedData, setReceivedData] = useState<formOutput>({{
    {output_initial}
  }});
  const [errMsg, setErrMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);

{input_change_fn}{row_change_fn}
  const submitAction = async (action: string) => {{
    setIsLoading(true);
    setErrMsg('');
    try {{
      const baseUrl = (import.meta as any).env?.VITE_API_BASE_URL || '';
      const response = await axios.post(`${{baseUrl}}/api/{map_name}`, {{ action, fields: formData }});
      const data = response.data as {{ fields?: Partial<formOutput>; errmsg?: string; nextScreen?: string }};
      if (data.fields) {{
        setReceivedData((prev) => ({{ ...prev, ...data.fields }}));
      }}
      if (data.errmsg) {{
        setErrMsg(data.errmsg);
      }}
      if (data.nextScreen) {{
        navigate(`/${{data.nextScreen}}`);
      }}
    }} catch (err) {{
      setErrMsg(err instanceof Error ? err.message : 'Request failed');
    }} finally {{
      setIsLoading(false);
    }}
  }};
{key_effect}
  return (
    <div className="min-h-screen bg-black flex items-start justify-center p-4">
      <div
        className="relative bg-black text-green-400 font-mono text-[13px] leading-[1.35] p-3 border border-green-900 rounded shadow-[0_0_25px_rgba(34,197,94,0.12)] overflow-x-auto"
        style={{{{
          display: 'grid',
          gridTemplateColumns: 'repeat({grid_cols}, 1ch)',
          gridTemplateRows: 'repeat({grid_rows}, 1.35em)',
          width: 'max-content',
          minWidth: '100%',
        }}}}
      >
          {fields_jsx}
          {tables_jsx}
          {alert_jsx}
          {{isLoading && (
            <span style={{{{ gridRow: {grid_rows}, gridColumn: '{max(grid_cols - 9, 1)} / span 9' }}}} className="text-yellow-300 animate-pulse">{{'...WAIT...'}}</span>
          )}}
      </div>
    </div>
  );
}}

export default {map_name};
"""


# ---------------------------------------------------------------------------
# Orchestration (per-file processing, router export, CLI) - unchanged shape,
# now driven by build_screen_model()/build_component() instead of the old
# per-item GridItem codegen.
# ---------------------------------------------------------------------------

def parse_bms_2_tsx(bms_file, tsx_file):
    """
    Parses a BMS file and generates a corresponding TSX file (plus a sibling
    <MAP>.model.json with the intermediate model, for inspection).

    Parameters:
    - bms_file (str): Path to the BMS file.
    - tsx_file (str): Path to the output TSX file.

    Returns:
    - dict or None: {"name": <component name>} on success, None on failure.
    """
    desired_object = {}
    try:
        map_items = extract_map_items(bms_file)
        # Just the filename, extension stripped - e.g. "/abs/dir/COACTUP.bms" ->
        # "COACTUP". The previous approach (stripping os.path.abspath(dirname(bms_file))
        # out of bms_file itself) silently broke whenever bms_file was passed as a
        # relative path: abspath() always returns an absolute string, which then never
        # matches inside the original relative bms_file, so nothing got stripped and the
        # whole path (with slashes removed) leaked into the component name instead
        # (e.g. "._verify_inCOACTUP"). The real backend adapter always resolves an
        # absolute sourceDir before invoking this CLI, so production was never affected -
        # but direct/manual CLI invocations with a relative path were.
        map_name = os.path.splitext(os.path.basename(bms_file))[0]
        model = build_screen_model(map_items, map_name)
        tsx_content = build_component(model)
        with open(tsx_file, "w", encoding="utf8") as file:
            file.write(tsx_content)
        model_file = os.path.splitext(tsx_file)[0] + ".model.json"
        with open(model_file, "w", encoding="utf8") as file:
            json.dump(model, file, indent=2)
        desired_object = {"name": map_name}
    except Exception as ex:
        print(ex)
        return None
    return desired_object


def process_file_bms(bms_file, bms_directory, react_directory):
    """
    Processes a BMS file and generates a corresponding React component.

    Parameters:
    - bms_file (str): Path to the BMS file.
    - bms_directory (str): Path to the BMS directory.
    - react_directory (str): Path to the React directory.

    Returns:
    - dict or None: Extracted information from the BMS file.
    """
    react_path = bms_file.replace(f"{bms_directory}", f"{react_directory}")
    tsx_file = os.path.splitext(react_path)[0] + ".tsx"
    tsx_directory = os.path.dirname(tsx_file)
    os.makedirs(tsx_directory, exist_ok=True)
    tsx = parse_bms_2_tsx(bms_file, tsx_file)
    if not tsx:
        print(f"\033[91m{bms_file}\033[0m")
    return tsx


def export_react_router(dfhmsd, tsx_directory):
    """
    Exports a React router file based on DFHMSD data.

    Parameters:
    - dfhmsd (list): List of dictionaries containing DFHMSD data.
    - tsx_directory (str): Path to the TSX directory.

    Returns:
    - bool: True if successful, False otherwise.
    """
    dfhmsd = [value for value in dfhmsd if value is not None]
    try:
        router_file = os.path.join(tsx_directory, "bmsRoutes.tsx")
        react_import = []
        react_export = []
        for item in dfhmsd:
            react_export.append({"name": item["name"], "component": f'{item["name"]}'})
            react_import.append(f'import {{ {item["name"]} }} from "./{item["name"]}"')
        output_str = json.dumps(react_export, separators=(",", ":"))
        react_import = "\n".join(react_import)
        react_code = f"""
import {{ type ElementType }} from 'react';
{react_import}

type BMSRoutes = {{
  name: string;
  component: ElementType;
}}[];

const bmsRoutes: BMSRoutes = {output_str};

export default bmsRoutes;
"""
        react_code = re.sub(r'"component":"([^"]+)"', r"component:\1", react_code)
        react_code = re.sub(r'"name":"([^"]+)"', r'name:"\1"', react_code)
        with open(router_file, "w") as tsx_file:
            tsx_file.write(f"{react_code}")
    except Exception as ex:
        print(ex)
        return False
    return True


def export_react_router_from_dir(tsx_directory):
    """
    Exports a React router file from a directory of TSX files.

    Parameters:
    - tsx_directory (str): Path to the TSX directory.

    Returns:
    - bool: True if successful, False otherwise.
    """
    tsx_files = [f for f in os.listdir(tsx_directory) if f.endswith(".tsx")]
    tsx_files = [
        f.replace(tsx_directory, "")
        .replace(".tsx", "")
        .replace("/", "")
        .replace("\\", "")
        for f in tsx_files
    ]
    tsx_files = [s for s in tsx_files if not any(c.islower() for c in s)]
    tsx_files = [{"name": f} for f in tsx_files]
    return export_react_router(tsx_files, tsx_directory)


def list_file_in_input_source(bms_directory, react_directory):
    """
    Lists and processes BMS files in the input source.

    Parameters:
    - bms_directory (str): Path to the BMS directory.
    - react_directory (str): Path to the React directory.
    """
    dfhmsd_list = []
    if not os.path.exists(bms_directory):
        print(f"\033[91mBMS directory '{bms_directory}' does not exist.\033[0m")
        return
    if not os.path.exists(react_directory):
        os.makedirs(react_directory)
    bms_files = []
    for root, dirs, files in os.walk(bms_directory, followlinks=False):
        for file in files:
            if file.endswith(".bms"):
                bms_files.append(os.path.join(root, file))
    for bms_file in bms_files:
        dfhmsd_list.append(process_file_bms(bms_file, bms_directory, react_directory))

    if export_react_router_from_dir(react_directory):
        print(f"\033[92mExported router name: bmsRouter.tsx\033[0m{''}")
    else:
        print(f"\033[91mUnable to export router name\033[0m{''}")


def main():
    """
    Main function to execute the BMS to React conversion.
    """
    os.system("")
    parser = argparse.ArgumentParser(
        description="Process BMS and React folders using bms2react.py"
    )
    parser.add_argument("-bms", help="Path to the BMS folder", required=True)
    parser.add_argument("-react", help="Path to the React folder", required=True)
    args = parser.parse_args()
    bms_folder = args.bms
    react_folder = args.react
    list_file_in_input_source(bms_folder, react_folder)


if __name__ == "__main__":
    main()
