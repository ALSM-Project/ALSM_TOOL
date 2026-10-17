"""
test_bms2react.py

Unit tests for the BMS->React modernization logic, grounded in real CardDemo BMS
content (the continuation-line example and function-key legend are taken verbatim
from the real COSGN00.bms mapset), not fabricated fixtures.

Run: python -m unittest test_bms2react -v
"""
import unittest

from bms2react import (
    build_state_types,
    classify_field,
    detect_function_keys,
    detect_repeating_groups,
    normalize_continued_text,
    extract_property,
)


class NormalizeContinuedTextTests(unittest.TestCase):
    def test_joins_a_real_two_line_continuation_with_no_inserted_space(self):
        # Verbatim from CardDemo COSGN00.bms (row 17): a non-blank char in column 72
        # ('-') means the statement continues at column 16 on the next line.
        raw = "Type your User ID and Password, then press ENTE-\n               R:"
        self.assertEqual(
            normalize_continued_text(raw),
            "Type your User ID and Password, then press ENTER:",
        )

    def test_joins_a_second_real_continuation_example(self):
        raw = "This is a Credit Card Demo Application for Main-\n               frame Modernization"
        self.assertEqual(
            normalize_continued_text(raw),
            "This is a Credit Card Demo Application for Mainframe Modernization",
        )

    def test_leaves_single_line_text_unchanged_besides_ampersand_escaping(self):
        self.assertEqual(normalize_continued_text("Plain text"), "Plain text")

    def test_unescapes_double_ampersand_to_a_literal_ampersand(self):
        self.assertEqual(normalize_continued_text("A && B"), "A & B")


class ClassifyFieldTests(unittest.TestCase):
    def test_named_unprot_is_input(self):
        field = {"name": "USERID", "attrb": ["FSET", "IC", "NORM", "UNPROT"], "length": 8}
        self.assertEqual(classify_field(field), "input")

    def test_named_askip_is_output(self):
        field = {"name": "TRNNAME", "attrb": ["ASKIP", "FSET", "NORM"], "length": 4}
        self.assertEqual(classify_field(field), "output")

    def test_named_with_no_attrb_clause_defaults_to_askip_and_is_output(self):
        # ATTRB is optional in real BMS; a missing clause defaults to ASKIP.
        field = {"name": "APPLID", "length": 8}
        self.assertEqual(classify_field(field), "output")

    def test_named_drk_without_unprot_is_a_hidden_technical_field_and_skipped(self):
        # Real CardDemo COCRDLI.bms: CRDSTPn is ATTRB=(ASKIP,DRK,FSET) - a named,
        # protected, but deliberately invisible internal marker.
        field = {"name": "CRDSTP2", "attrb": ["ASKIP", "DRK", "FSET"], "length": 1}
        self.assertEqual(classify_field(field), "skip")

    def test_unnamed_with_initial_is_a_static_label(self):
        field = {"initial": "User ID     :", "attrb": ["ASKIP", "NORM"], "length": 13}
        self.assertEqual(classify_field(field), "label")

    def test_unnamed_unprot_technical_field_is_skipped(self):
        # Real CardDemo COSGN00.bms field at POS(20,61): ATTRB=(DRK,UNPROT), no name.
        field = {"attrb": ["DRK", "UNPROT"], "length": 1, "initial": " "}
        self.assertEqual(classify_field(field), "skip")

    def test_length_zero_stopper_field_is_always_skipped(self):
        field = {"name": "ANYTHING", "attrb": ["UNPROT"], "length": 0}
        self.assertEqual(classify_field(field), "skip")


class DetectFunctionKeysTests(unittest.TestCase):
    def test_parses_the_real_cosgn00_legend_line(self):
        label_fields = [{"initial": "ENTER=Sign-on  F3=Exit"}]
        used = set()
        keys = detect_function_keys(label_fields, used)
        self.assertEqual(
            keys,
            [
                {"key": "Enter", "action": "ENTER", "label": "Sign-on"},
                {"key": "F3", "action": "PF3", "label": "Exit"},
            ],
        )
        self.assertEqual(len(used), 1)

    def test_returns_empty_list_when_no_legend_line_present(self):
        label_fields = [{"initial": "Just some regular instructional text"}]
        self.assertEqual(detect_function_keys(label_fields, set()), [])

    def test_finds_the_legend_in_a_named_output_field_not_just_unnamed_labels(self):
        # Real CardDemo bug (COACTUP/COCRDSL/COCRDUP/COTRTUP): the legend text is
        # the INITIAL value of a NAMED, protected field (e.g. "FKEYS") - that field
        # is classified 'output', not 'label', so a caller must include 'output'
        # fields in candidate_fields or the legend (and every button it implies)
        # is silently dropped.
        candidate_fields = [
            {"name": "FKEYS", "kind": "output", "initial": "ENTER=Process F3=Exit"},
        ]
        used = set()
        keys = detect_function_keys(candidate_fields, used)
        self.assertEqual(
            keys,
            [
                {"key": "Enter", "action": "ENTER", "label": "Process"},
                {"key": "F3", "action": "PF3", "label": "Exit"},
            ],
        )
        self.assertEqual(len(used), 1)

    def test_merges_keys_split_across_several_single_key_fields(self):
        # Real CardDemo bug (COTRTLI): instead of one combined legend line, each
        # key gets its own named field (BUTNF02="F2=Add", BUTNF03="F3=Exit", ...).
        # Every matching field must contribute to one merged, ordered list rather
        # than only the first one found.
        candidate_fields = [
            {"name": "BUTNF02", "kind": "output", "initial": "F2=Add"},
            {"name": "BUTNF03", "kind": "output", "initial": "F3=Exit"},
            {"name": "BUTNF07", "kind": "output", "initial": "F7=Page Up"},
            {"name": "BUTNF08", "kind": "output", "initial": "F8=Page Dn"},
            {"name": "BUTNF10", "kind": "output", "initial": "F10=Save"},
        ]
        used = set()
        keys = detect_function_keys(candidate_fields, used)
        self.assertEqual([k["key"] for k in keys], ["F2", "F3", "F7", "F8", "F10"])
        self.assertEqual(len(used), 5)


class DetectRepeatingGroupsTests(unittest.TestCase):
    def test_groups_same_indexed_columns_into_one_table(self):
        fields = []
        for i in range(1, 8):
            fields.append({"name": f"CRDSEL{i}", "row": 10 + i, "col": 10})
            fields.append({"name": f"ACCTNO{i}", "row": 10 + i, "col": 20})
        tables, remaining = detect_repeating_groups(fields)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["columns"], ["CRDSEL", "ACCTNO"])
        self.assertEqual(len(tables[0]["rowIndexes"]), 7)
        self.assertEqual(remaining, [])

    def test_a_lone_single_field_is_not_treated_as_a_table(self):
        fields = [{"name": "USERID", "row": 19, "col": 43}]
        tables, remaining = detect_repeating_groups(fields)
        self.assertEqual(tables, [])
        self.assertEqual(remaining, fields)

    def test_columns_with_different_index_sets_are_not_merged(self):
        # A column missing an index (e.g. CRDSTP starting at 2, not 1) must not be
        # forced into the same table as columns present at every index 1..7 - that
        # would silently fabricate a 7th "row" of data that was never defined.
        fields = [{"name": f"CRDSEL{i}", "row": i, "col": 10} for i in range(1, 8)]
        fields += [{"name": f"CRDSTP{i}", "row": i, "col": 30} for i in range(2, 8)]
        tables, remaining = detect_repeating_groups(fields)
        self.assertEqual(tables, [])
        self.assertEqual(len(remaining), 13)


class ExtractPropertyTests(unittest.TestCase):
    def test_parses_a_real_multiline_dfhmdf_statement(self):
        raw = (
            "        DFHMDF ATTRB=(ASKIP,NORM),                                     -\n"
            "               COLOR=TURQUOISE,                                        -\n"
            "               LENGTH=49,                                              -\n"
            "               POS=(17,16),                                            -\n"
            "               INITIAL='Type your User ID and Password, then press ENTE-\n"
            "               R:'\n"
        )
        data = extract_property(raw)
        self.assertEqual(data["initial"], "Type your User ID and Password, then press ENTER:")
        self.assertEqual(data["row"], 17)
        self.assertEqual(data["col"], 16)
        self.assertEqual(data["length"], 49)
        self.assertEqual(data["color"], "TURQUOISE")
        self.assertEqual(data["attrb"], ["ASKIP", "NORM"])

    def test_attrb_is_always_normalized_to_a_list_even_when_bare(self):
        raw = "TESTFLD DFHMDF ATTRB=PROT,LENGTH=1,POS=(1,1)"
        data = extract_property(raw)
        self.assertEqual(data["attrb"], ["PROT"])


class BuildStateTypesTests(unittest.TestCase):
    def test_errmsg_and_infomsg_are_optional_since_the_initial_literal_never_sets_them(self):
        # Real bug: every generated screen declares `errmsg`/`infomsg` as REQUIRED
        # formOutput fields but never includes them in the initial useState()
        # literal (they only ever arrive later from the API response) - this made
        # `tsc -b` fail on every single converted screen with "missing properties
        # ... errmsg, infomsg" the moment a real project scaffold tried to build it.
        model = {
            "titles": [],
            "metadata": [],
            "fields": [],
            "errmsgField": "ERRMSG",
            "infomsgField": "INFOMSG",
            "tables": [],
        }
        _, output_type, _, output_initial = build_state_types(model)
        self.assertIn("errmsg?: any;", output_type)
        self.assertIn("infomsg?: any;", output_type)
        self.assertNotIn("errmsg:", output_initial)
        self.assertNotIn("infomsg:", output_initial)

    def test_table_row_field_is_also_optional(self):
        model = {
            "titles": [],
            "metadata": [],
            "fields": [],
            "errmsgField": None,
            "infomsgField": None,
            "tables": [{"columns": ["CRDSEL"], "columnKind": {"CRDSEL": "output"}}],
        }
        _, output_type, _, _ = build_state_types(model)
        self.assertIn("crdselRows?: any;", output_type)


if __name__ == "__main__":
    unittest.main()
