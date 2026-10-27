# -*- coding: utf-8 -*-
"""
Écran de lancement animé de fOMODSIM (règle Socle « Splash animé », modèle : splash de mORTEX).

Fenêtre sans cadre, transparente, centrée, de 500 × 190 px (carte de 476 × 166 px et marge de 12 px
pour son ombre). Chronologie : t = 0 splash visible → t = 2 s fenêtre principale → t = 4 s sortie
animée de 600 ms. Tout est dessiné au QPainter d'après le temps écoulé, image par image.
"""

import logging
import math
import subprocess
import sys

from PyQt6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, QEasingCurve
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPolygonF,
    QRadialGradient,
    QTransform,
)
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger("fomod_simulator.splash")

SPLASH_WIDTH = 500  # size-splash-width (Socle)
SPLASH_HEIGHT = 190  # size-splash-height (Socle)
MARGIN = 12
MAIN_WINDOW_AT_MS = 2000
MIN_SHOWN_MS = 4000
LEAVE_MS = 600

# Couleurs de l'icône : carré bleu, losanges blancs
BLUE_1 = QColor("#7cc8ff")
BLUE_2 = QColor("#1a73e8")
SQUARE_TOP = QColor("#1c86e2")
SQUARE_BOTTOM = QColor("#0e5cc4")

# Losanges de l'icône (centre x, centre y) dans le carré de 824 px de icon.png, ordre d'empilement
DIAMONDS = [(412, 555), (278, 440), (545, 440), (278, 272), (545, 272)]
DIAMOND_HALF = (128, 80)


def _bezier(x1, y1, x2, y2) -> QEasingCurve:
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2), QPointF(1, 1))
    return curve


EASE_CARD = _bezier(0.16, 1, 0.3, 1)
EASE_LOGO = _bezier(0.22, 1, 0.36, 1)
EASE_DROP = _bezier(0.34, 1.3, 0.5, 1)
EASE_LETTER = _bezier(0.2, 1.2, 0.4, 1)
EASE_RULE = _bezier(0.65, 0, 0.35, 1)
EASE_INOUT = _bezier(0.42, 0, 0.58, 1)
EASE_OUT = _bezier(0, 0, 0.58, 1)
EASE_LEAVE = _bezier(0.6, -0.28, 0.735, 0.045)


def _progress(t: float, delay: float, duration: float, curve: QEasingCurve) -> float:
    if t <= delay:
        return 0.0
    if t >= delay + duration:
        return 1.0
    return curve.valueForProgress((t - delay) / duration)


def _heartbeat(t: float) -> float:
    """Double pulsation douce puis repos (période 1,2 s), comme les pales de mORTEX."""
    keys = [(0, 1.0), (0.14, 1.03), (0.28, 0.94), (0.42, 1.02), (0.56, 0.97), (0.70, 1.0), (1, 1.0)]
    x = (t % 1200) / 1200
    for (x0, v0), (x1, v1) in zip(keys, keys[1:]):
        if x <= x1:
            return v0 + (v1 - v0) * EASE_INOUT.valueForProgress((x - x0) / (x1 - x0))
    return 1.0


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
            QTimer.singleShot(max(200, MIN_SHOWN_MS - self.elapsed()), self.leave)

        QTimer.singleShot(max(0, MAIN_WINDOW_AT_MS - self.elapsed()), show_window)

    def leave(self):
        if self._closed or self._leave_at is not None:
            return
        self._leave_at = self.elapsed()
        logger.info("Splash : début de la sortie à t = %d ms", self._leave_at)
        if self._reduced:
            self._close_now()
        else:
            QTimer.singleShot(LEAVE_MS + 50, self._close_now)

    def _close_now(self):
        if self._closed:
            return
        self._closed = True
        self._frame_timer.stop()
        logger.info("Splash : fermé à t = %d ms", self.elapsed())
        self.close()

    # ---- Mise en page ----
    def _prepare_fonts(self):
        self._text_left = 34 + 108 + 26
        self._text_width = 476 - 30 - self._text_left

        self._title_font = QFont(".AppleSystemUIFont")
        self._title_font.setWeight(QFont.Weight.ExtraBold)
        self._title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        size = 50.0
        while size > 24:
            self._title_font.setPixelSize(int(size))
            if QFontMetricsF(self._title_font).horizontalAdvance(self._title) <= self._text_width:
                break
            size -= 1
        self._title_size = size

        self._sub_font = QFont(".AppleSystemUIFont")
        self._sub_font.setWeight(QFont.Weight.DemiBold)
        sub = 17.0
        while sub > 10:
            self._sub_font.setPixelSize(int(sub))
            self._sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5)
            if QFontMetricsF(self._sub_font).horizontalAdvance(self._subtitle) <= self._text_width:
                break
            sub -= 1
        self._sub_size = sub

        self._footer_font = QFont(".AppleSystemUIFont")
        self._footer_font.setPixelSize(10)
        self._footer_font.setWeight(QFont.Weight.Medium)
        self._footer_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)

    # ---- Dessin ----
    def paintEvent(self, _event):
        t = 1e7 if self._reduced else float(self.elapsed())
        idle = not self._reduced
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

        # Arrivée de la carte en perspective
        k = _progress(t, 0, 900, EASE_CARD)
        card = QRectF(MARGIN, MARGIN, SPLASH_WIDTH - 2 * MARGIN, SPLASH_HEIGHT - 2 * MARGIN)
        tr = QTransform()
        tr.translate(card.center().x(), card.center().y())
        tr.rotate(28 * (1 - k), Qt.Axis.XAxis)
        tr.rotate(-14 * (1 - k), Qt.Axis.YAxis)
        s = 0.92 + 0.08 * k
        tr.scale(s, s)
        tr.translate(-card.center().x(), -card.center().y())
        p.setTransform(tr, True)
        p.setOpacity(p.opacity() * min(1.0, k))

        path = QPainterPath()
        path.addRoundedRect(card, 16, 16)
        self._paint_shadow(p, card)
        bg = QLinearGradient(card.topLeft(), QPointF(card.left() + card.width() * 0.35, card.bottom()))
        bg.setColorAt(0, QColor("#34363d"))
        bg.setColorAt(0.55, QColor("#1b1c21"))
        bg.setColorAt(1, QColor("#121317"))
        p.fillPath(path, bg)

        p.save()
        p.setClipPath(path)
        p.translate(card.topLeft())
        self._paint_glow(p, t)
        self._paint_sheen(p, t)
        self._paint_logo(p, t, idle)
        self._paint_text(p, t)
        p.restore()

        p.setPen(QColor(255, 255, 255, 20))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), 16, 16)
        p.end()

    def _paint_shadow(self, p: QPainter, card: QRectF):
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(12, 0, -1):
            p.setBrush(QColor(0, 0, 0, int(115 / 12 * (13 - i) / 6.5)))
            r = card.adjusted(-i * 0.8, -i * 0.8 + 6, i * 0.8, i * 0.8 + 6)
            p.drawRoundedRect(r, 16 + i, 16 + i)
        p.restore()

    def _paint_glow(self, p: QPainter, t: float):
        k = _progress(t, 300, 1400, EASE_OUT)
        if k <= 0:
            return
        c = QPointF(80, 83)
        g = QRadialGradient(c, 120)
        g.setColorAt(0, QColor(40, 140, 255, int(56 * k)))
        g.setColorAt(0.65, QColor(40, 140, 255, 0))
        p.fillRect(QRectF(c.x() - 120, c.y() - 120, 240, 240), g)

    def _paint_sheen(self, p: QPainter, t: float):
        k = _progress(t, 1350, 1100, EASE_INOUT)
        if k <= 0 or k >= 1:
            return
        w = 476 * 0.4
        p.save()
        p.translate(-476 * 0.6 + k * w * 5.2, -83)
        p.rotate(8)
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0, QColor(255, 255, 255, 0))
        g.setColorAt(0.45, QColor(255, 255, 255, 26))
        g.setColorAt(0.5, QColor(255, 255, 255, 46))
        g.setColorAt(0.55, QColor(255, 255, 255, 26))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(0, 0, w, 332), g)
        p.restore()

    def _paint_logo(self, p: QPainter, t: float, idle: bool):
        size = 108.0
        p.save()
        p.translate(34 + size / 2, 83)

        # Carré bleu : arrivée en tourbillon, puis battement de cœur
        k = _progress(t, 0, 1300, EASE_LOGO)
        lin = min(1.0, t / 1300)
        alpha = min(1.0, lin / 0.4)
        beat = _heartbeat(t - 1300) if idle and t > 1300 else 1.0
        sc = (0.2 + 0.8 * k) * beat
        p.rotate(-420 * (1 - k))
        p.scale(sc, sc)
        p.setOpacity(p.opacity() * alpha)
        half = size / 2
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(6, 0, -1):  # halo bleu
            p.setBrush(QColor(40, 140, 255, 14))
            p.drawRoundedRect(QRectF(-half - i, -half - i, size + 2 * i, size + 2 * i), 24 + i, 24 + i)
        sq = QLinearGradient(0, -half, 0, half)
        sq.setColorAt(0, SQUARE_TOP)
        sq.setColorAt(1, SQUARE_BOTTOM)
        p.setBrush(sq)
        p.drawRoundedRect(QRectF(-half, -half, size, size), 24, 24)

        # Losanges : chute en culbute et empilement, puis léger flottement
        unit = size / 824
        for i, (cx, cy) in enumerate(DIAMONDS):
            delay = 150 + i * 90
            d = _progress(t, delay, 900, EASE_DROP)
            fade = _progress(t, delay, 450, EASE_OUT)
            if fade <= 0:
                continue
            bob = 1.5 * math.sin((t - 1650) / 6000 * 2 * math.pi + i * 0.9) if idle and t > 1650 else 0.0
            p.save()
            p.translate((cx - 412) * unit, (cy - 412) * unit - 70 * (1 - d) + bob)
            p.rotate(160 * (1 - d))
            ds = 0.3 + 0.7 * d
            p.scale(ds, ds)
            p.setOpacity(p.opacity() * fade)
            hw, hh = DIAMOND_HALF[0] * unit, DIAMOND_HALF[1] * unit
            p.setBrush(QColor(0, 0, 0, 40))
            p.drawPolygon(QPolygonF([QPointF(0, -hh + 1.2), QPointF(hw, 1.2), QPointF(0, hh + 1.2), QPointF(-hw, 1.2)]))
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
                if i == 0:
                    g = QLinearGradient(pos.x(), -title_h * 0.7, pos.x() + adv, title_h * 0.15)
                    g.setColorAt(0, BLUE_1)
                    g.setColorAt(1, BLUE_2)
                    p.setPen(Qt.PenStyle.NoPen)
                    text_path = QPainterPath()
                    text_path.addText(pos, self._title_font, ch)
                    p.fillPath(text_path, g)
                else:
                    p.setPen(QColor("#ffffff"))
                    p.drawText(pos, ch)
                p.restore()
            x += adv
        p.restore()

        # Filet qui se déploie
        rule_y = top + title_h + 10
        k = _progress(t, 950, 700, EASE_RULE)
        if k > 0:
            g = QLinearGradient(x0, 0, x0 + self._text_width, 0)
            g.setColorAt(0, BLUE_1)
            g.setColorAt(0.6, BLUE_2)
            g.setColorAt(1, QColor(26, 115, 232, 0))
            path = QPainterPath()
            path.addRoundedRect(QRectF(x0, rule_y, self._text_width * k, 2), 1, 1)
            p.fillPath(path, g)

        # Sous-titre : resserrement des lettres
        k = _progress(t, 1100, 900, EASE_CARD)
        if k > 0:
            p.save()
            font = QFont(self._sub_font)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 14 - 9 * k)
            p.setFont(font)
            p.setOpacity(p.opacity() * k)
            p.setPen(QColor("#d8d8d8"))
            p.drawText(QPointF(x0, rule_y + 2 + 9 + self._sub_size * 0.95), self._subtitle)
            p.restore()

        # Mention en bas à droite
        k = _progress(t, 1500, 600, EASE_OUT)
        if k > 0:
            p.save()
            p.setFont(self._footer_font)
            p.setOpacity(p.opacity() * k)
            p.setPen(QColor("#aaaaaa"))
            w = QFontMetricsF(self._footer_font).horizontalAdvance(self._footer)
            p.drawText(QPointF(476 - 18 - w, 166 - 10 - 2), self._footer)
            p.restore()
