# -*- coding: utf-8 -*-
"""Traductions : mêmes clés dans les 4 langues, textes « À propos » compris (règle Socle)."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python_app"))

from locales import fr, en, es, it  # noqa: E402

ABOUT_KEYS = {"menu", "version", "tagline", "license", "disclaimer", "credit"}


def _keys(d, prefix=""):
    out = set()
    for k, v in d.items():
        out |= _keys(v, f"{prefix}{k}.") if isinstance(v, dict) else {prefix + k}
    return out


class TestLocales(unittest.TestCase):
    def test_same_keys(self):
        ref = _keys(fr.STRINGS)
        for mod in (en, es, it):
            self.assertEqual(_keys(mod.STRINGS), ref, mod.__name__)

    def test_about(self):
        for mod in (fr, en, es, it):
            about = mod.STRINGS["about"]
            self.assertEqual(set(about), ABOUT_KEYS, mod.__name__)
            self.assertIn("fOMODSIM", about["menu"])
            self.assertIn("{v}", about["version"])
            self.assertIn("{b}", about["version"])


if __name__ == "__main__":
    unittest.main()
