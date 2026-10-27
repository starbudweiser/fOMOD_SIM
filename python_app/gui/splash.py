# -*- coding: utf-8 -*-
"""
Écran de lancement animé de fOMODSIM (règle Socle « Splash animé », modèle : splash de mORTEX).

Fenêtre sans cadre, transparente, centrée, de 500 × 190 px (carte de 476 × 166 px et marge de 12 px,
commune aux applis). Effets sobres (Socle) : carte plate, entrée de l'icône et du nom, filet, sous-titre.
Chronologie : t = 0 splash visible → t = 2 s fenêtre principale → t = 4 s sortie
animée de 600 ms. Tout est dessiné au QPainter d'après le temps écoulé, image par image.
"""

import logging
import subprocess
import sys

from PyQt6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, QEasingCurve
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPolygonF,
    QTransform,
)
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger("fomod_simulator.splash")

SPLASH_WIDTH = 500  # size-splash-width (Socle)
SPLASH_HEIGHT = 190  # size-splash-height (Socle)
MARGIN = 12
PADDING = 24  # space-6 (Socle) : même marge intérieure à gauche et à droite
LOGO = 108
GAP = 26
TITLE_SIZE = 40  # size-splash-title (Socle)
MAIN_WINDOW_AT_MS = 2000
MIN_SHOWN_MS = 4000
LEAVE_MS = 600

# Couleurs plates : carte sombre, bleu de l'icône, losanges blancs
CARD_BG = QColor("#1b1c21")
BLUE = QColor("#1677dc")
BLUE_LIGHT = QColor("#5fb4ff")

# Losanges de l'icône (centre x, centre y) dans le carré de 824 px de icon.png, ordre d'empilement
DIAMONDS = [(412, 555), (278, 440), (545, 440), (278, 272), (545, 272)]
DIAMOND_HALF = (128, 80)


def _bezier(x1, y1, x2, y2) -> QEasingCurve:
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2), QPointF(1, 1))
    return curve


EASE_SUB = _bezier(0.16, 1, 0.3, 1)
EASE_LOGO = _bezier(0.22, 1, 0.36, 1)
EASE_DROP = _bezier(0.34, 1.3, 0.5, 1)
EASE_LETTER = _bezier(0.2, 1.2, 0.4, 1)
EASE_RULE = _bezier(0.65, 0, 0.35, 1)
EASE_OUT = _bezier(0, 0, 0.58, 1)
EASE_LEAVE = _bezier(0.6, -0.28, 0.735, 0.045)


def _progress(t: float, delay: float, duration: float, curve: QEasingCurve) -> float:
    if t <= delay:
        return 0.0
    if t >= delay + duration:
        return 1.0
    return curve.valueForProgress((t - delay) / duration)


def reduce_motion_enabled() -> bool:
    """Réglage « Réduire les animations » de macOS (équivalent de prefers-reduced-motion)."""
    if sys.platform != "darwin":
        return False
    try:
        out = subprocess.run(
            ["defaults", "read", "com.apple.universalaccess", "reduceMotion"],
            capture_output=True, text=True, timeout=1,
        )
        return out.stdout.strip() == "1"
    except Exception:
        return False


class SplashScreen(QWidget):
    def __init__(self, title: str, subtitle: str, footer: str, reduced_motion: bool | None = None):
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(SPLASH_WIDTH, SPLASH_HEIGHT)

        self._title = title
        self._subtitle = subtitle
        self._footer = footer.upper()
        self._reduced = reduce_motion_enabled() if reduced_motion is None else reduced_motion
        self._clock = QElapsedTimer()
        self._leave_at: float | None = None
        self._closed = False
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(16)
        self._frame_timer.timeout.connect(self.update)
        self._prepare_fonts()

    # ---- Chronologie ----
    def elapsed(self) -> int:
        return self._clock.elapsed() if self._clock.isValid() else 0

    def start(self):
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - SPLASH_WIDTH // 2, geo.center().y() - SPLASH_HEIGHT // 2)
        self.show()
        self._clock.start()
        if not self._reduced:
            self._frame_timer.start()
        logger.info("Splash : visible (t = 0 ms)")

    def open_main_window(self, window):
        """Ouvre la fenêtre principale à t = 2 s (ou tout de suite si l'appli est prête plus tard),
        puis fait sortir le splash à t = 4 s, jamais avant que la fenêtre soit affichée."""
        def show_window():
            window.show()
            window.raise_()
            window.activateWindow()
            logger.info("Splash : fenêtre principale affichée à t = %d ms", self.elapsed())
            QTimer.singleShot(max(200, MIN_SHOWN_MS - self.elapsed()), Qt.TimerType.PreciseTimer, self.leave)

        QTimer.singleShot(max(0, MAIN_WINDOW_AT_MS - self.elapsed()), Qt.TimerType.PreciseTimer, show_window)

    def leave(self):
        if self._closed or self._leave_at is not None:
            return
        self._leave_at = self.elapsed()
        logger.info("Splash : début de la sortie à t = %d ms", self._leave_at)
        if self._reduced:
            self._close_now()
        else:
            QTimer.singleShot(LEAVE_MS + 50, Qt.TimerType.PreciseTimer, self._close_now)

    def _close_now(self):
        if self._closed:
            return
        self._closed = True
        self._frame_timer.stop()
        logger.info("Splash : fermé à t = %d ms", self.elapsed())
        self.close()

    # ---- Mise en page ----
    def _prepare_fonts(self):
        # Zone utile : 476 − 2 × 24 px ; le texte se réduit pour y tenir sur une ligne
        max_text = 476 - 2 * PADDING - LOGO - GAP

        self._title_font = QFont(".AppleSystemUIFont")
        self._title_font.setWeight(QFont.Weight.ExtraBold)
        self._title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        self._title_font.setPixelSize(TITLE_SIZE)  # taille fixe, identique dans toutes les applis
        self._title_size = float(TITLE_SIZE)

        self._sub_font = QFont(".AppleSystemUIFont")
        self._sub_font.setWeight(QFont.Weight.DemiBold)
        sub = 17.0
        while sub > 6:
            self._sub_font.setPixelSize(int(sub))
            self._sub_spacing = 5 * sub / 17  # l'espacement se réduit avec la taille
            self._sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, self._sub_spacing)
            if QFontMetricsF(self._sub_font).horizontalAdvance(self._subtitle) <= max_text:
                break
            sub -= 1
        self._sub_size = sub

        # Bloc logo + texte centré dans la carte
        sub_font = QFont(self._sub_font)
        self._text_width = max(
            QFontMetricsF(self._title_font).horizontalAdvance(self._title),
            QFontMetricsF(sub_font).horizontalAdvance(self._subtitle),
        )
        self._logo_left = (476 - (LOGO + GAP + self._text_width)) / 2
        self._text_left = self._logo_left + LOGO + GAP

        self._footer_font = QFont(".AppleSystemUIFont")
        self._footer_font.setPixelSize(10)
        self._footer_font.setWeight(QFont.Weight.Medium)
        self._footer_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)

    # ---- Dessin ----
    def paintEvent(self, _event):
        t = 1e7 if self._reduced else float(self.elapsed())
        p = QPainter(self)
        p.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )

        # Sortie : zoom arrière avec rebond (easeInBack), fondu sur les 30 derniers %
        if self._leave_at is not None and not self._reduced:
            lt = min(1.0, (self.elapsed() - self._leave_at) / LEAVE_MS)
            scale = 1 - 0.95 * EASE_LEAVE.valueForProgress(lt)
            opacity = 1.0 if lt < 0.7 else 1 - EASE_LEAVE.valueForProgress((lt - 0.7) / 0.3)
            p.setOpacity(max(0.0, opacity))
            cx, cy = SPLASH_WIDTH / 2, SPLASH_HEIGHT / 2
            p.translate(cx, cy)
            p.scale(scale, scale)
            p.translate(-cx, -cy)

        # Carte plate (Socle : ni ombre, ni dégradé, ni contour)
        card = QRectF(MARGIN, MARGIN, SPLASH_WIDTH - 2 * MARGIN, SPLASH_HEIGHT - 2 * MARGIN)
        path = QPainterPath()
        path.addRoundedRect(card, 16, 16)
        p.fillPath(path, CARD_BG)

        p.save()
        p.setClipPath(path)
        p.translate(card.topLeft())
        self._paint_logo(p, t)
        self._paint_text(p, t)
        p.restore()
        p.end()

    def _paint_logo(self, p: QPainter, t: float):
        size = float(LOGO)
        p.save()
        p.translate(self._logo_left + size / 2, 83)

        # Carré bleu : arrivée en tourbillon
        k = _progress(t, 0, 1300, EASE_LOGO)
        lin = min(1.0, t / 1300)
        alpha = min(1.0, lin / 0.4)
        sc = 0.2 + 0.8 * k
        p.rotate(-420 * (1 - k))
        p.scale(sc, sc)
        p.setOpacity(p.opacity() * alpha)
        half = size / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BLUE)
        p.drawRoundedRect(QRectF(-half, -half, size, size), 24, 24)

        # Losanges : chute en culbute et empilement
        unit = size / 824
        for i, (cx, cy) in enumerate(DIAMONDS):
            delay = 150 + i * 90
            d = _progress(t, delay, 900, EASE_DROP)
            fade = _progress(t, delay, 450, EASE_OUT)
            if fade <= 0:
                continue
            p.save()
            p.translate((cx - 412) * unit, (cy - 412) * unit - 70 * (1 - d))
            p.rotate(160 * (1 - d))
            ds = 0.3 + 0.7 * d
            p.scale(ds, ds)
            p.setOpacity(p.opacity() * fade)
            hw, hh = DIAMOND_HALF[0] * unit, DIAMOND_HALF[1] * unit
            p.setBrush(QColor("#ffffff"))
            p.drawPolygon(QPolygonF([QPointF(0, -hh), QPointF(hw, 0), QPointF(0, hh), QPointF(-hw, 0)]))
            p.restore()
        p.restore()

    def _paint_text(self, p: QPainter, t: float):
        x0 = self._text_left
        fm = QFontMetricsF(self._title_font)
        title_h = self._title_size
        sub_h = self._sub_size * 1.2
        block = title_h + 10 + 2 + 9 + sub_h
        top = 83 - block / 2
        baseline = top + fm.ascent() - (fm.ascent() - title_h * 0.72)

        # Titre : lettres qui basculent en place une à une
        p.save()
        p.setFont(self._title_font)
        x = x0
        for i, ch in enumerate(self._title):
            adv = fm.horizontalAdvance(ch)
            k = _progress(t, 450 + i * 70, 700, EASE_LETTER)
            lin = min(1.0, max(0.0, (t - 450 - i * 70) / 700))
            if lin > 0:
                tr = QTransform()
                tr.translate(x + adv / 2, baseline - title_h * 0.15 + 14 * (1 - k))
                tr.rotate(-95 * (1 - k), Qt.Axis.XAxis)
                p.save()
                p.setTransform(tr, True)
                p.setOpacity(p.opacity() * min(1.0, lin * 1.6))
                pos = QPointF(-adv / 2, title_h * 0.15)
                p.setPen(BLUE_LIGHT if i == 0 else QColor("#ffffff"))
                p.drawText(pos, ch)
                p.restore()
            x += adv
        p.restore()

        # Filet qui se déploie
        rule_y = top + title_h + 10
        k = _progress(t, 950, 700, EASE_RULE)
        if k > 0:
            p.fillRect(QRectF(x0, rule_y, self._text_width * k, 2), BLUE)

        # Sous-titre : resserrement des lettres
        k = _progress(t, 1100, 900, EASE_SUB)
        if k > 0:
            p.save()
            font = QFont(self._sub_font)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, self._sub_spacing * (14 - 9 * k) / 5)
            p.setFont(font)
            p.setOpacity(p.opacity() * k)
            p.setPen(QColor("#d8d8d8"))
            p.drawText(QPointF(x0, rule_y + 2 + 9 + self._sub_size * 0.95), self._subtitle)
            p.restore()

        # Mention en bas à droite (fixe)
        p.save()
        p.setFont(self._footer_font)
        p.setPen(QColor("#aaaaaa"))
        w = QFontMetricsF(self._footer_font).horizontalAdvance(self._footer)
        p.drawText(QPointF(476 - PADDING - w, 166 - 10 - 2), self._footer)
        p.restore()
