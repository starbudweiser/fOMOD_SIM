import os
import sys
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Initialiser QApplication offscreen pour exécuter les tests dans un conteneur headless
os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from python_app.gui.main_window import MainWindow
from python_app.gui.theme import DARK_THEME_QSS
from python_app.gui.mod_info_dialog import ModInfoDialog


class TestMainWindowGUI(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow()
        self.window.load_demo_mod()

    def tearDown(self):
        self.window.cleanup_workers()
        self.window.close()

    def test_default_welcome_screen(self):
        """Vérifie que la fenêtre démarre initialement sur l'écran d'accueil sans mod chargé."""
        fresh_win = MainWindow()
        try:
            self.assertEqual(fresh_win.central_stack.currentIndex(), 0)
            self.assertEqual(len(fresh_win.steps), 0)
            self.assertIsNotNone(fresh_win.welcome_widget)
        finally:
            fresh_win.cleanup_workers()
            fresh_win.close()

    def test_window_initialization(self):
        # Le mod CBBE chargé pour la simulation
        self.assertEqual(self.window.central_stack.currentIndex(), 1)
        self.assertIn("Caliente", self.window.title_label.text())
        self.assertEqual(len(self.window.steps), 5)
        self.assertEqual(self.window.current_step_idx, 0)
        self.assertFalse(self.window.btn_prev.isEnabled())
        self.assertTrue(self.window.btn_next.isEnabled())

    def test_step_navigation(self):
        # Étape 1 -> Étape 2
        self.window._next_step()
        self.assertEqual(self.window.current_step_idx, 1)
        self.assertTrue(self.window.btn_prev.isEnabled())
        self.assertIn("Textures", self.window.step_title_label.text())

        # Étape 2 -> Étape 1
        self.window._prev_step()
        self.assertEqual(self.window.current_step_idx, 0)
        self.assertFalse(self.window.btn_prev.isEnabled())

    def test_option_selection_and_staging(self):
        # Vérifier que des options par défaut sont sélectionnées
        self.assertTrue(len(self.window.selected_option_ids) > 0)

        # Attendre la fin du worker de staging et traiter les événements de boucle Qt
        if self.window._staging_worker:
            self.window._staging_worker.wait(2000)
            app.processEvents()

        self.assertIsNotNone(self.window.current_staging_result)
        self.assertTrue(self.window.current_staging_result.copied_count > 0)
        self.assertTrue(self.window.staging_tree.topLevelItemCount() > 0)

    def test_close_mod_returns_to_welcome(self):
        """Vérifie que la fermeture du mod réinitialise l'état et retourne sur l'écran d'accueil."""
        self.window._close_mod()
        self.assertEqual(self.window.central_stack.currentIndex(), 0)
        self.assertEqual(len(self.window.steps), 0)
        self.assertEqual(len(self.window.selected_option_ids), 0)

    def test_mod_info_dialog(self):
        dialog = ModInfoDialog(self.window.metadata)
        self.assertIn("Caliente", dialog.windowTitle())
        dialog.close()

    def test_language_switching(self):
        """Vérifie que le changement dynamique de langue met à jour les libellés de l'UI."""
        # 1. Anglais
        self.window._change_language("en")
        self.assertEqual(self.window.i18n.current_language, "en")
        self.assertEqual(self.window.windowTitle(), "fOMODSIM")
        self.assertEqual(self.window.btn_close.text(), "← Close mod")
        self.assertEqual(self.window.btn_next.text(), "CONTINUE →")

        # 2. Italien
        self.window._change_language("it")
        self.assertEqual(self.window.i18n.current_language, "it")
        self.assertEqual(self.window.btn_close.text(), "← Chiudi mod")
        self.assertEqual(self.window.btn_next.text(), "CONTINUA →")

        # 3. Espagnol
        self.window._change_language("es")
        self.assertEqual(self.window.i18n.current_language, "es")
        self.assertEqual(self.window.btn_close.text(), "← Cerrar mod")
        self.assertEqual(self.window.btn_next.text(), "CONTINUAR →")

        # 4. Retour au Français (défaut)
        self.window._change_language("fr")
        self.assertEqual(self.window.i18n.current_language, "fr")
        self.assertEqual(self.window.btn_close.text(), "← Fermer le mod")


if __name__ == "__main__":
    unittest.main()

