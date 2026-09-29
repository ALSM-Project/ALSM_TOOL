'''
bms2react.py

Converts CICS BMS mapsets (DFHMSD/DFHMDI/DFHMDF) into modern, runnable React 19 +
TypeScript + Tailwind screens - not a literal 80x24 character-grid replica, but a
real form/table layout that preserves every piece of business content and every
function key from the original 3270 map.

Pipeline per BMS file:
  1. extract_map_items()   - parse DFHMSD/DFHMDI/DFHMDF statements into flat dicts,
                              correctly rejoining INITIAL text that continues onto a
                              second physical line (BMS column-72/column-16 rule).
  2. build_screen_model()  - classify every field (input / output / static label /
                              skip), pair labels+helper text with the field next to
                              them, detect repeating field groups (e.g. CRDSEL1..7)
                              as table rows, and pull out the function-key legend
                              line (e.g. "ENTER=Sign-on  F3=Exit"). This model is
                              also written out as <MAP>.model.json for inspection.
  3. build_component()     - renders the model into a single self-contained .tsx
                              file: header + metadata bar, body form/table, an
                              alert region for ERRMSG/INFOMSG, and a footer action
                              bar wired to both on-screen buttons and real keyboard
                              shortcuts (Enter/F3/F4/F5/F7/F8/F12).

Author: KhangNV19 (original), extended 2026 to follow the BMS->React modernization
spec (intermediate model, real field classification, semantic color tokens,
repeating-group tables, PF-key wiring, ERRMSG/INFOMSG alerts).
'''
import argparse
import os
import re
import json


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 3270 COLOR -> semantic Tailwind token (never emit the raw 3270 color name into
# the generated code - it rarely has usable contrast on a light background).
COLOR_TOKEN_MAP = {
    'BLUE': 'text-slate-600',
    'TURQUOISE': 'text-slate-800',
    'GREEN': '',
    'YELLOW': 'text-blue-900 font-bold',
    'RED': 'text-red-600',
    'PINK': 'text-amber-600',
    'NEUTRAL': 'text-gray-700',
    'DEFAULT': 'text-gray-700',
}

# BMS HILIGHT value -> extra Tailwind class (on top of BRT -> font-semibold).
HILIGHT_TOKEN_MAP = {
    'UNDERLINE': 'underline',
    'BLINK': 'animate-pulse',
    'REVERSE': 'font-semibold',
}

# Real function-key legend line, e.g. "ENTER=Sign-on  F3=Exit  F7=Backward F8=Forward"
FUNCTION_KEY_LEGEND_RE = re.compile(
    r'(ENTER|PF\d{1,2}|F\d{1,2})\s*=\s*([^=]*?)(?=\s{2,}(?:ENTER|PF\d{1,2}|F\d{1,2})\s*=|$)',
    re.IGNORECASE,
)

# Repeating field group naming convention, e.g. CRDSEL1, ACCTNO12
GROUP_NAME_RE = re.compile(r'^([A-Za-z]+)(\d{1,3})$')

# Header metadata (Tran/Prog/Date/Time/AppID/SysID-style fields) only ever sits in
# the top few rows of a real BMS map; used to separate it from the page title and
# from the main body content without hardcoding any specific field name.
HEADER_MAX_ROW = 3

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


def find_left_label(field, labels_by_row, used_label_ids):
    """Nearest unused static-text field on the same row, to the left, ending in ':'."""
    row = field.get("row")
    col = field.get("col", 0)
    candidates = [
        f for f in labels_by_row.get(row, [])
        if id(f) not in used_label_ids and f.get("col", 0) < col and (f.get("initial") or "").rstrip().endswith(":")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.get("col", 0))


def find_right_helper(field, labels_by_row, used_label_ids):
    """Nearest unused static-text field on the same row, to the right, in parentheses."""
    row = field.get("row")
    col = field.get("col", 0)
    candidates = [
        f for f in labels_by_row.get(row, [])
        if id(f) not in used_label_ids
        and f.get("col", 0) > col
        and (f.get("initial") or "").strip().startswith("(")
        and (f.get("initial") or "").strip().endswith(")")
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda f: f.get("col", 0))


def detect_function_keys(label_fields, used_label_ids):
    """
    Finds the function-key legend line (e.g. "ENTER=Sign-on  F3=Exit") among the
    static-text fields and returns the parsed [{key, label}] list. The matched
    field is marked as used so it is not also rendered as plain static text.
    """
    for field in label_fields:
        text = field.get("initial") or ""
        matches = list(FUNCTION_KEY_LEGEND_RE.finditer(text))
        if len(matches) >= 1 and "=" in text:
            used_label_ids.add(id(field))
            keys = []
            for m in matches:
                raw_key = m.group(1).upper()
                label = m.group(2).strip()
                js_key = PF_KEY_TO_JS_KEY.get(raw_key, raw_key)
                action = "ENTER" if raw_key == "ENTER" else re.sub(r"^F", "PF", raw_key)
                keys.append({"key": js_key, "action": action, "label": label or action})
            return keys
    return []


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
    Builds the intermediate model described by the modernization spec: classified
    fields, label/helper pairing, header metadata, repeating tables, and the
    function-key legend - everything the codegen step needs, and exactly what gets
    written out to <MAP>.model.json for inspection.
    """
    fields = [f for f in map_items if is_field_definition(f)]
    for f in fields:
        f["kind"] = classify_field(f)

    labels_by_row = {}
    for f in fields:
        if f["kind"] == "label":
            labels_by_row.setdefault(f.get("row"), []).append(f)

    used_label_ids = set()
    function_keys = detect_function_keys(
        [f for f in fields if f["kind"] == "label"], used_label_ids
    )

    interactive = [f for f in fields if f["kind"] in ("input", "output")]
    for f in interactive:
        left = find_left_label(f, labels_by_row, used_label_ids)
        if left:
            used_label_ids.add(id(left))
            f["label"] = left.get("initial", "").rstrip().rstrip(":").strip()
        else:
            f["label"] = f.get("name", "")
        helper = find_right_helper(f, labels_by_row, used_label_ids)
        if helper:
            used_label_ids.add(id(helper))
            f["helper"] = helper.get("initial", "")

    errmsg_field = next((f for f in interactive if (f.get("name") or "").upper() == "ERRMSG"), None)
    infomsg_field = next((f for f in interactive if (f.get("name") or "").upper() == "INFOMSG"), None)
    body_candidates = [f for f in interactive if f is not errmsg_field and f is not infomsg_field]

    header_candidates = [f for f in body_candidates if f.get("row", 999) <= HEADER_MAX_ROW]
    metadata_items = [f for f in header_candidates if f.get("label") and f.get("kind") == "output" and f.get("label") != f.get("name")]
    title_items = [f for f in header_candidates if f not in metadata_items]
    remaining = [f for f in body_candidates if f not in header_candidates]

    tables, remaining = detect_repeating_groups(remaining)

    remaining_labels = [
        f for f in fields
        if f["kind"] == "label" and id(f) not in used_label_ids
    ]

    return {
        "mapName": map_name,
        "titles": [
            {"name": f.get("name"), "row": f.get("row"), "col": f.get("col")}
            for f in sorted(title_items, key=lambda x: (x.get("row", 0), x.get("col", 0)))
        ],
        "metadata": [
            {
                "name": f.get("name"),
                "label": f.get("label"),
                "initial": f.get("initial", ""),
                "row": f.get("row"),
                "col": f.get("col"),
            }
            for f in sorted(metadata_items, key=lambda x: (x.get("row", 0), x.get("col", 0)))
        ],
        "fields": [
            {
                "name": f.get("name"),
                "kind": f.get("kind"),
                "label": f.get("label"),
                "helper": f.get("helper"),
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
            for f in sorted(remaining, key=lambda x: (x.get("row", 0), x.get("col", 0)))
        ],
        "tables": tables,
        "staticText": [
            {
                "text": f.get("initial", ""),
                "row": f.get("row"),
                "col": f.get("col"),
                "color": f.get("color"),
                "className": css_class_for(f),
            }
            for f in sorted(remaining_labels, key=lambda x: (x.get("row", 0), x.get("col", 0)))
            if f.get("row", 0) > HEADER_MAX_ROW and not is_decorative_initial(f.get("initial"))
        ],
        "errmsgField": errmsg_field.get("name") if errmsg_field else None,
        "infomsgField": infomsg_field.get("name") if infomsg_field else None,
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
    """
    return (text or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").strip()


def esc_multiline(text):
    """Same as esc(), but keeps embedded newlines (escaped) instead of collapsing
    them - used for <pre> banner blocks where line breaks are the point."""
    return (text or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").strip()


def jsx_text(text):
    """Wraps literal text as a safe JS string-literal JSX expression: {'...'}"""
    return "{'" + esc(text) + "'}"


def field_var(name):
    return (name or "field").lower()


def is_banner_like(text):
    if not text or len(text) < 15:
        return False
    art_chars = sum(1 for c in text if c in "%$=~|+_(){}[]*")
    return (art_chars / len(text)) > 0.25


def render_titles(titles, field_lookup):
    lines = []
    for t in titles:
        name = t["name"]
        lines.append(
            f"<h2 className=\"text-base sm:text-lg font-bold text-blue-900\">"
            f"{{receivedData.{field_var(name)} || ''}}</h2>"
        )
    if not lines:
        return ""
    return "<div className=\"space-y-0.5\">\n" + "\n".join(lines) + "\n</div>"


def render_metadata_bar(metadata):
    if not metadata:
        return ""
    items = []
    for m in metadata:
        name = m["name"]
        label = jsx_text(m["label"] or name)
        items.append(
            "<div><span className=\"text-slate-400\">" + label + "</span>{' '}"
            "<span className=\"font-mono\">{receivedData." + field_var(name) + " || ''}</span></div>"
        )
    return (
        "<div className=\"flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-slate-500\">\n"
        + "\n".join(items)
        + "\n</div>"
    )


def render_static_text_block(static_text):
    if not static_text:
        return ""
    groups = []
    current = []
    prev_row = None
    for item in static_text:
        banner = is_banner_like(item["text"])
        if banner and (prev_row is None or item["row"] == prev_row + 1) and (not current or current[-1]["banner"]):
            current.append({**item, "banner": True})
        else:
            if current:
                groups.append(current)
            current = [{**item, "banner": banner}]
        prev_row = item["row"]
    if current:
        groups.append(current)

    parts = []
    for group in groups:
        if len(group) >= 3 and all(g["banner"] for g in group):
            content = "\\n".join(esc_multiline(g["text"]) for g in group)
            parts.append(
                "<pre className=\"font-mono text-xs text-slate-500 leading-tight whitespace-pre-wrap\">{'"
                + content + "'}</pre>"
            )
        else:
            for g in group:
                cls = g["className"] or "text-slate-600"
                parts.append("<p className=\"" + cls + " text-xs\">" + jsx_text(g["text"]) + "</p>")
    return "<div className=\"space-y-1 my-3\">\n" + "\n".join(parts) + "\n</div>"


def render_field(field):
    name = field["name"]
    var = field_var(name)
    label_jsx = jsx_text(field.get("label") or name)
    helper_text = field.get("helper") or ""
    length = field.get("length") or 20
    width_style = f"style={{{{ width: '{min(length, 60)}ch' }}}}"
    color_class = css_class_for(field)

    if field["kind"] == "input":
        input_type = "password" if field.get("isDark") else "text"
        extra_props = []
        if field.get("isNumeric"):
            extra_props.append('inputMode="numeric"')
            extra_props.append(f'pattern="[0-9]{{0,{length}}}"')
        if field.get("autoFocus"):
            extra_props.append("autoFocus")
        extra = " ".join(extra_props)
        helper_html = (
            '<p id="' + var + '-helper" className="text-[11px] text-slate-400 mt-0.5">'
            + jsx_text(helper_text) + "</p>"
        ) if helper_text else ""
        return f"""
<div>
  <label htmlFor="{var}" className="block text-xs font-semibold {color_class}">{label_jsx}</label>
  <input
    id="{var}"
    name="{var}"
    type="{input_type}"
    maxLength={{{length}}}
    {width_style}
    {extra}
    value={{formData.{var} ?? ''}}
    onChange={{(e) => handleInputChange('{var}', e.target.value)}}
    aria-describedby="{var}-helper"
    className="mt-1 block rounded-md border border-slate-300 px-2 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
  />
  {helper_html}
</div>"""
    # output field
    return f"""
<div>
  <span className="block text-xs font-semibold {color_class}">{label_jsx}</span>
  <span className="mt-1 block text-sm text-slate-800 font-mono">{{receivedData.{var} || ''}}</span>
</div>"""


def render_body_fields(fields):
    if not fields:
        return ""
    items = "\n".join(render_field(f) for f in fields)
    return f"""
<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
{items}
</div>"""


def render_tables(tables):
    if not tables:
        return ""
    blocks = []
    for t_index, table in enumerate(tables):
        columns = table["columns"]
        kind = table["columnKind"]
        headers = "".join(
            "<th className=\"px-3 py-2 text-left font-semibold text-slate-600\">" + jsx_text(col) + "</th>"
            for col in columns
        )
        cells = []
        for col in columns:
            var = field_var(col)
            if kind.get(col) == "input":
                cells.append(
                    f"<td className=\"px-3 py-1\"><input value={{(formData.{field_var(table['columns'][0])}Rows?.[i]?.{var}) ?? ''}} "
                    f"onChange={{(e) => handleRowChange('{field_var(table['columns'][0])}', i, '{var}', e.target.value)}} "
                    f"className=\"w-full rounded border border-slate-300 px-1.5 py-1 text-xs\" /></td>"
                )
            else:
                cells.append(f"<td className=\"px-3 py-1.5 font-mono\">{{row.{var} ?? ''}}</td>")
        cells_joined = "".join(cells)
        blocks.append(f"""
<div className="overflow-x-auto my-4">
  <table className="min-w-full text-xs border border-slate-200 rounded-lg overflow-hidden">
    <thead className="bg-slate-50">
      <tr>{headers}</tr>
    </thead>
    <tbody className="divide-y divide-slate-100">
      {{(receivedData.{field_var(table['columns'][0])}Rows || []).map((row: any, i: number) => (
        <tr key={{i}}>{cells_joined}</tr>
      ))}}
    </tbody>
  </table>
</div>""")
    return "\n".join(blocks)


def render_alert_region(errmsg_field, infomsg_field):
    parts = []
    if errmsg_field:
        var = field_var(errmsg_field)
        parts.append(f"""
{{errMsg && (
  <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
    {{errMsg}}
  </div>
)}}""")
    if infomsg_field:
        var = field_var(infomsg_field)
        parts.append(f"""
{{receivedData.{var} && (
  <div role="status" className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
    {{receivedData.{var}}}
  </div>
)}}""")
    return "\n".join(parts)


def render_action_bar(function_keys):
    if not function_keys:
        return ""
    buttons = []
    for fk in function_keys:
        label_jsx = jsx_text(fk["label"])
        buttons.append(
            f"""<button type="button" disabled={{isLoading}} onClick={{() => submitAction('{fk['action']}')}} """
            f"""className="px-4 py-2 text-xs font-semibold rounded-md border border-slate-300 bg-white hover:bg-slate-50 disabled:opacity-50">{label_jsx}</button>"""
        )
    return (
        '<div className="flex flex-wrap gap-2 pt-4 border-t border-slate-100">\n'
        + "\n".join(buttons)
        + "\n</div>"
    )


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
    for f in model["titles"]:
        output_names.add(field_var(f["name"]))
    for m in model["metadata"]:
        output_names.add(field_var(m["name"]))
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

    input_type = "\n  ".join(f"{n}: string;" for n in sorted(input_names)) or "[key: string]: string;"
    output_type = "\n  ".join(f"{n}: any;" for n in sorted(output_names)) or "[key: string]: any;"
    input_initial = "\n    ".join(f"{n}: '',".rstrip(',') + "," for n in sorted(input_names)) or ""
    output_initial_parts = []
    for f in model["fields"]:
        if f["kind"] == "output":
            init = esc(f.get("initial") or "")
            output_initial_parts.append(f"{field_var(f['name'])}: '{init}',")
    for m in model["metadata"]:
        init = esc(m.get("initial") or "")
        output_initial_parts.append(f"{field_var(m['name'])}: '{init}',")
    for t in model["titles"]:
        output_initial_parts.append(f"{field_var(t['name'])}: '',")
    output_initial = "\n    ".join(output_initial_parts)
    return input_type, output_type, input_initial, output_initial


def build_component(model):
    map_name = model["mapName"]
    titles_jsx = render_titles(model["titles"], None)
    metadata_jsx = render_metadata_bar(model["metadata"])
    static_jsx = render_static_text_block(model["staticText"])
    body_jsx = render_body_fields(model["fields"])
    tables_jsx = render_tables(model["tables"])
    alert_jsx = render_alert_region(model["errmsgField"], model["infomsgField"])
    action_bar_jsx = render_action_bar(model["functionKeys"])
    key_effect = render_function_key_effect(model["functionKeys"])
    input_type, output_type, input_initial, output_initial = build_state_types(model)

    has_row_tables = bool(model["tables"])
    row_change_fn = ""
    if has_row_tables:
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
  const [formData, setFormData] = useState<formInput>({{
    {input_initial}
  }});
  const [receivedData, setReceivedData] = useState<formOutput>({{
    {output_initial}
  }});
  const [errMsg, setErrMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleInputChange = (name: string, value: string) => {{
    setFormData((prev: any) => ({{ ...prev, [name]: value }}));
  }};
{row_change_fn}
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
    <div className="max-w-3xl mx-auto my-6 px-4 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 border-b border-slate-100 pb-3">
        {titles_jsx}
        {metadata_jsx}
      </div>
      {static_jsx}
      {alert_jsx}
      {body_jsx}
      {tables_jsx}
      {action_bar_jsx}
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
        map_name = (
            bms_file.replace(os.path.abspath(os.path.dirname(bms_file)), "")
            .replace(".bms", "")
            .replace("/", "")
            .replace("\\", "")
        )
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
