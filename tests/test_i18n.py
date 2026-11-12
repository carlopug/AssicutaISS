"""Ogni tr("...") del programma deve avere la traduzione inglese, con gli stessi segnaposto."""
import ast
import os
import string
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sstv_iss.i18n import EN, set_language, tr  # noqa: E402


def tr_keys():
    keys = {}
    for dirpath, _, files in os.walk(os.path.join(ROOT, "sstv_iss")):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(dirpath, f)
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr"
                        and node.args and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    keys[node.args[0].value] = f"{os.path.relpath(path, ROOT)}:{node.lineno}"
    return keys


def fields(s):
    return sorted(name for _, name, _, _ in string.Formatter().parse(s) if name)


def test_every_string_has_english_translation():
    keys = tr_keys()
    assert len(keys) > 100
    missing = [f"{where}: {k!r}" for k, where in keys.items() if k not in EN]
    assert not missing, "Traduzioni mancanti:\n" + "\n".join(missing)


def test_placeholders_match():
    bad = [k for k in tr_keys() if k in EN and fields(k) != fields(EN[k])]
    assert not bad, bad


def test_category_labels_translated():
    from sstv_iss.gui.widgets import CATEGORIES
    assert all(label in EN for _, label in CATEGORIES)


def test_switch_language():
    try:
        set_language("en")
        assert tr("Frequenza") == "Frequency"
        assert tr("Decodifica Robot36 ({m}) - riga {n}/{h}", m="VIS", n=5, h=240) == "Decoding Robot36 (VIS) - line 5/240"
    finally:
        set_language("it")
    assert tr("Frequenza") == "Frequenza"
