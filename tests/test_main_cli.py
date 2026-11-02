"""main.py n'appelle que des méthodes qui existent sur MainWindow (ouverture d'un fichier passé au lancement)."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "python_app"


class TestMainCli(unittest.TestCase):
    def test_main_calls_existing_window_methods(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        called = {n.func.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "window"}
        gui = ast.parse((ROOT / "gui" / "main_window.py").read_text(encoding="utf-8"))
        cls = next(n for n in gui.body if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
        methods = {f.name for f in cls.body if isinstance(f, ast.FunctionDef)}
        assert "_load_archive" in called
        missing = {m for m in called if m.startswith("_") and m not in methods}
        assert not missing, f"méthodes absentes de MainWindow : {missing}"
