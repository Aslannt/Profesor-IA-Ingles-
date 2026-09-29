"""Sistema de diseño de la app, siguiendo la guía de estilo tipo Apple (DESIGN-apple.md).

Fuente única de verdad para color, tipografía, radios y espaciado: los widgets toman su aspecto
de aquí (QSS generado + `fuente()` + `icono()`), nunca de colores escritos a mano.

Reglas de la guía que se respetan:
- Un solo color de acción: Action Blue (#0066cc). Todo lo que se toca es azul; nada más lo es.
- Superficies: blanco, "parchment" (#f5f5f7) y bloques casi negros (#272729). El cambio de
  superficie es el separador: sin sombras, sin degradados, sin bordes decorativos.
- Tipografía: Inter Display (títulos, 600, tracking negativo) + Inter (texto, 17 px, 400).
  Inter es el reemplazo libre de SF Pro que recomienda la guía. Escalera de pesos 300/400/600.
- Radios: 8 (utilitario), 11 (cápsula perla), 18 (tarjetas), píldora (acciones).
- Al presionar, los botones se encogen al 95 % (la micro-interacción de todo el sistema).

Única excepción funcional: el verde/ámbar/rojo de la calificación de pronunciación. La guía no
cubre estados de validación, y la alumna necesita ver de un vistazo qué palabra salió bien.
Se usan los tonos de sistema accesibles de Apple, solo dentro de la tarjeta de resultado.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap, QTransform
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QGraphicsEffect

from ..config import RAIZ_PAQUETE

CARPETA_FUENTES = RAIZ_PAQUETE / "assets" / "fuentes"
CARPETA_ICONOS = RAIZ_PAQUETE / "assets" / "iconos"

# ------------------------------------------------------------------ colores (tokens de la guía)
C = {
    "primary": "#0066cc",            # Action Blue: lo único que es "tócame"
    "primary_focus": "#0071e3",
    "primary_on_dark": "#2997ff",    # azul para enlaces sobre bloques oscuros
    "ink": "#1d1d1f",
    "on_dark": "#ffffff",
    "body_muted": "#cccccc",         # texto secundario sobre oscuro
    "ink_muted_80": "#333333",
    "ink_muted_48": "#7a7a7a",
    "divider_soft": "#f0f0f0",
    "hairline": "#e0e0e0",
    "canvas": "#ffffff",
    "parchment": "#f5f5f7",
    "pearl": "#fafafc",
    "tile_1": "#272729",
    "tile_2": "#2a2a2c",
    "black": "#000000",
    "chip": "#d2d2d7",
    # Solo para calificar pronunciación (ver nota arriba):
    "bien": "#248a3d", "casi": "#b25000", "falta": "#d70015",
}

# ------------------------------------------------------------------ tipografía
DISPLAY = "Inter Display"
TEXTO = "Inter"
RESPALDO = ["Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", "Arial"]


@dataclass(frozen=True, slots=True)
class Tipo:
    familia: str
    px: float
    peso: int
    tracking: float  # px
    interlineado: float


TIPOS = {
    "hero": Tipo(DISPLAY, 56, 600, -0.28, 1.07),
    "display_lg": Tipo(DISPLAY, 40, 600, 0.0, 1.10),
    "display_md": Tipo(TEXTO, 34, 600, -0.374, 1.47),
    "lead": Tipo(TEXTO, 28, 400, 0.196, 1.14),  # Inter Display solo trae 600
    "lead_airy": Tipo(TEXTO, 24, 300, 0.0, 1.5),
    "tagline": Tipo(DISPLAY, 21, 600, 0.231, 1.19),
    "body_strong": Tipo(TEXTO, 17, 600, -0.374, 1.24),
    "body": Tipo(TEXTO, 17, 400, -0.374, 1.47),
    "caption": Tipo(TEXTO, 14, 400, -0.224, 1.43),
    "caption_strong": Tipo(TEXTO, 14, 600, -0.224, 1.29),
    "button_large": Tipo(TEXTO, 18, 300, 0.0, 1.0),
    "button_utility": Tipo(TEXTO, 14, 400, -0.224, 1.29),
    "nav_link": Tipo(TEXTO, 12, 400, -0.12, 1.0),
}

RADIO = {"sm": 8, "md": 11, "lg": 18, "pill": 9999}
# Qt ignora un border-radius mayor que la mitad de la altura, así que las píldoras tienen altura
# fija y radio = altura / 2 (el equivalente exacto de border-radius: 9999px).
ALTURA_PILDORA = {"primario": 44, "primario_grande": 52, "secundario": 44, "secundario_chico": 36}
ESPACIO = {"xxs": 4, "xs": 8, "sm": 12, "md": 17, "lg": 24, "xl": 32, "xxl": 48, "section": 80}

_PESOS = {300: QFont.Weight.Light, 400: QFont.Weight.Normal, 600: QFont.Weight.DemiBold}


class Escala:
    """La guía está en px para 17 px de texto. `tamano_letra` del cliente escala todo junto,
    por si la alumna necesita letra más grande (p. ej. 19 = +12 %)."""
    factor = 1.0


def px(valor: float) -> int:
    return max(1, round(valor * Escala.factor))


def cargar_fuentes() -> None:
    for archivo in sorted(CARPETA_FUENTES.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(archivo))


def fuente(nombre: str) -> QFont:
    t = TIPOS[nombre]
    f = QFont(t.familia)
    f.setFamilies([t.familia, TEXTO, *RESPALDO])
    f.setPixelSize(px(t.px))
    f.setWeight(_PESOS[t.peso])
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, t.tracking * Escala.factor)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def css_tipo(nombre: str, color: str | None = None) -> str:
    """Estilo en línea para texto enriquecido (HTML dentro de QLabel/QTextBrowser)."""
    t = TIPOS[nombre]
    estilo = (f"font-family:'{t.familia}','{TEXTO}','Segoe UI'; font-size:{px(t.px)}px; font-weight:{t.peso};"
              f" letter-spacing:{t.tracking * Escala.factor:.3f}px;")
    return estilo + (f" color:{color};" if color else "")


# ------------------------------------------------------------------ íconos (Feather, MIT)

@lru_cache(maxsize=256)
def icono(nombre: str, color: str, tamano: int = 20) -> QIcon:
    ruta = CARPETA_ICONOS / f"{nombre}.svg"
    if not ruta.exists():
        return QIcon()
    svg = ruta.read_text(encoding="utf-8").replace("currentColor", color)
    render = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    mapa = QPixmap(tamano * 2, tamano * 2)  # a 2x para pantallas escaladas
    mapa.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(mapa)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    render.render(pintor)
    pintor.end()
    mapa.setDevicePixelRatio(2)
    return QIcon(mapa)


# ------------------------------------------------------------------ presión: escala 0.95

class EfectoPresion(QGraphicsEffect):
    """La micro-interacción de la guía (`transform: scale(0.95)` al presionar), en Qt."""

    def __init__(self, boton: QAbstractButton) -> None:
        super().__init__(boton)
        self._escala = 1.0
        boton.pressed.connect(lambda: self._poner(0.95))
        boton.released.connect(lambda: self._poner(1.0))

    def _poner(self, escala: float) -> None:
        self._escala = escala
        self.update()

    def draw(self, pintor: QPainter) -> None:
        if self._escala == 1.0:
            self.drawSource(pintor)
            return
        caja = self.sourceBoundingRect()
        centro = caja.center()
        pintor.save()
        pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        pintor.setTransform(QTransform().translate(centro.x(), centro.y()).scale(self._escala, self._escala)
                            .translate(-centro.x(), -centro.y()), True)
        self.drawSource(pintor)
        pintor.restore()

    def boundingRectFor(self, rect: QRectF) -> QRectF:
        return rect


def presionable(boton: QAbstractButton) -> QAbstractButton:
    boton.setGraphicsEffect(EfectoPresion(boton))
    boton.setCursor(Qt.CursorShape.PointingHandCursor)
    return boton


# ------------------------------------------------------------------ hoja de estilo

def qss() -> str:
    """Solo color, fondos, bordes y rellenos. Las fuentes van por `fuente()`: si se pusieran aquí,
    Qt pisaría el tracking negativo de los títulos."""
    c, r = C, RADIO
    return f"""
    QMainWindow, QWidget#raiz {{ background: {c['canvas']}; }}
    QWidget {{ color: {c['ink']}; }}
    QLabel {{ background: transparent; }}

    /* global-nav: barra negra de 44 px */
    QFrame#nav {{ background: {c['black']}; }}
    QLabel#nav_titulo {{ color: {c['on_dark']}; }}
    QPushButton#nav_enlace {{ background: transparent; border: none; color: {c['on_dark']}; padding: 0 {px(10)}px; }}
    QPushButton#nav_enlace:checked {{ color: {c['body_muted']}; }}

    /* avisos: el cambio de superficie es el mensaje (sin rojo chillón) */
    QLabel#aviso {{ background: {c['tile_1']}; color: {c['on_dark']}; padding: {px(12)}px {px(24)}px; }}
    QLabel#aviso_leve {{ background: {c['parchment']}; color: {c['ink']}; padding: {px(12)}px {px(24)}px;
                         border-bottom: 1px solid {c['hairline']}; }}

    /* superficies de bloque (tiles): de borde a borde, sin radio */
    QWidget#tile_blanco {{ background: {c['canvas']}; }}
    QWidget#tile_parchment {{ background: {c['parchment']}; }}
    QFrame#tile_oscuro {{ background: {c['tile_1']}; }}
    QLabel#sobre_oscuro {{ color: {c['on_dark']}; }}
    QLabel#sobre_oscuro_suave {{ color: {c['body_muted']}; }}
    QLabel#suave {{ color: {c['ink_muted_48']}; }}

    /* sub-nav de la clase (parchment, línea fina abajo) */
    QFrame#subnav {{ background: {c['parchment']}; border-bottom: 1px solid {c['hairline']}; }}
    /* barra inferior de controles (floating-sticky-bar) */
    QFrame#barra_inferior {{ background: {c['parchment']}; border-top: 1px solid {c['hairline']}; }}

    /* store-utility-card */
    QFrame#tarjeta {{ background: {c['canvas']}; border: 1px solid {c['hairline']}; border-radius: {r['lg']}px; }}
    QFrame#tarjeta_clase {{ background: {c['canvas']}; border: 1px solid {c['hairline']}; border-radius: {r['lg']}px; }}

    /* burbujas del chat */
    QLabel#burbuja_profe {{ background: {c['parchment']}; border-radius: {r['lg']}px; padding: {px(14)}px {px(20)}px; }}
    QLabel#burbuja_alumna {{ background: {c['ink']}; color: {c['on_dark']}; border-radius: {r['lg']}px;
                             padding: {px(14)}px {px(20)}px; }}
    QLabel#resultado {{ background: {c['canvas']}; border: 1px solid {c['hairline']}; border-radius: {r['lg']}px;
                        padding: {px(17)}px {px(24)}px; }}

    /* button-primary / button-store-hero: píldora azul */
    QPushButton#primario {{ background: {c['primary']}; color: {c['canvas']}; border: none;
                            border-radius: {px(ALTURA_PILDORA['primario']) // 2}px; padding: 0 {px(22)}px; }}
    QPushButton#primario_grande {{ background: {c['primary']}; color: {c['canvas']}; border: none;
                                   border-radius: {px(ALTURA_PILDORA['primario_grande']) // 2}px; padding: 0 {px(28)}px; }}
    QPushButton#primario:disabled, QPushButton#primario_grande:disabled {{ background: {c['chip']}; color: {c['ink_muted_48']}; }}
    /* button-secondary-pill: píldora "fantasma" */
    QPushButton#secundario, QPushButton#secundario_chico {{ background: transparent; color: {c['primary']};
                              border: 1px solid {c['primary']}; padding: 0 {px(21)}px; }}
    QPushButton#secundario {{ border-radius: {px(ALTURA_PILDORA['secundario']) // 2}px; }}
    QPushButton#secundario_chico {{ border-radius: {px(ALTURA_PILDORA['secundario_chico']) // 2}px; padding: 0 {px(17)}px; }}
    QPushButton#secundario:disabled, QPushButton#secundario_chico:disabled {{ color: {c['ink_muted_48']}; border-color: {c['chip']}; }}
    /* button-pearl-capsule: controles de apoyo */
    QPushButton#perla {{ background: {c['pearl']}; color: {c['ink_muted_80']}; border: 3px solid {c['divider_soft']};
                         border-radius: {r['md']}px; padding: {px(8)}px {px(14)}px {px(8)}px {px(12)}px; }}
    QPushButton#perla:disabled {{ color: {c['ink_muted_48']}; }}
    /* text-link sobre oscuro */
    QPushButton#enlace_oscuro {{ background: transparent; border: none; color: {c['primary_on_dark']}; padding: {px(4)}px; }}
    QPushButton#enlace {{ background: transparent; border: none; color: {c['primary']}; padding: {px(4)}px; text-align: left; }}

    /* search-input: píldora */
    QLineEdit {{ background: {c['canvas']}; color: {c['ink']}; border: 1px solid rgba(0,0,0,0.08);
                 border-radius: {px(22)}px; padding: {px(10)}px {px(20)}px; min-height: {px(24)}px; }}
    QLineEdit:focus {{ border: 2px solid {c['primary_focus']}; }}

    QTextBrowser {{ background: {c['canvas']}; border: none; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['chip']}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QMessageBox {{ background: {c['canvas']}; }}
    """
