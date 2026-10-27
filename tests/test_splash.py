# -*- coding: utf-8 -*-
"""Splash animé : dimensions Socle, traductions et chronologie (fenêtre à 2 s, sortie à 4 s)."""
import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from python_app.gui.splash import SPLASH_HEIGHT, SPLASH_WIDTH, SplashScreen
from python_app.locales import TRANSLATIONS

app = QApplication.instance() or QApplication([])


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class TestSplash(unittest.TestCase):
    def test_size_and_translations(self):
        splash = SplashScreen("fOMODSIM", "SIMULATEUR FOMOD", "Pour Skyrim SE / AE", reduced_motion=False)
        self.assertEqual((splash.width(), splash.height()), (SPLASH_WIDTH, SPLASH_HEIGHT))
        self.assertEqual((SPLASH_WIDTH, SPLASH_HEIGHT), (500, 190))
        for lang, strings in TRANSLATIONS.items():
            self.assertEqual(set(strings["splash"]), {"subtitle", "footer"}, lang)
        for t in (0, 500, 1200, 3000):  # le dessin ne lève pas d'exception à chaque étape
            splash._clock.start()
            splash._clock.restart()
            splash.grab()
        splash.deleteLater()

    def test_symmetric_margins(self):
        # Marges intérieures égales (24 px mini), même avec un nom ou un sous-titre trop long
        for title, sub in [("fOMODSIM", "SIMULATORE FOMOD"), ("fOMODSIMULATORULTIMATE", "SIMULATORE DI INSTALLATORI FOMOD")]:
            s = SplashScreen(title, sub, "x", reduced_motion=True)
            left = s._logo_left
            right = 476 - s._text_left - s._text_width
            self.assertAlmostEqual(left, right, delta=0.5)
            self.assertGreaterEqual(left, 24 - 0.5)

    def test_timeline(self):
        for reduced in (False, True):
            splash = SplashScreen("fOMODSIM", "X", "Y", reduced_motion=reduced)
            window = QWidget()
            start = time.monotonic()
            splash.start()
            splash.open_main_window(window)
            shown_at = None
            while time.monotonic() - start < 5.5:
                wait(20)
                if shown_at is None and window.isVisible():
                    shown_at = time.monotonic() - start
            self.assertAlmostEqual(shown_at, 2.0, delta=0.2)
            self.assertTrue(splash._closed)
            self.assertAlmostEqual(splash._leave_at / 1000, 4.0, delta=0.2)
            window.close()


if __name__ == "__main__":
    unittest.main()
