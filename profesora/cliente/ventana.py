"""Ventana de la app (PySide6), con el sistema de diseño de `tema.py` (guía tipo Apple).

Pensada para alguien que no es de tecnología: una sola acción grande (el micrófono azul),
la profesora que habla sola, y lo demás en segundo plano.
"""
from __future__ import annotations

import html
import re

import numpy as np
from PySide6.QtCore import QObject, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from .. import protocolo as p
from ..config import ConfigCliente
from . import tema
from .motor import Conexion, Microfono, Parlante
from .tema import C, css_tipo, fuente, icono, presionable, px

ANCHO_COLUMNA = 760  # columna de lectura centrada (la guía usa ~980 en páginas de texto)
PAG_INICIO, PAG_CLASE, PAG_RESUMEN, PAG_CLASES = range(4)


def a_html(texto: str, color_enlace: str = C["primary"]) -> str:
    """Texto con marcas [en]/[repite] -> HTML: el inglés es un enlace azul (tocarlo lo pronuncia)."""
    partes, pos = [], 0
    for m in re.finditer(r"\[(en|repite)\](.*?)\[/\1\]", texto, flags=re.S | re.I):
        partes.append(html.escape(texto[pos:m.start()]))
        frase = m.group(2).strip()
        partes.append(f'<a href="en:{html.escape(frase)}" style="color:{color_enlace};text-decoration:none;'
                      f'font-weight:600">{html.escape(frase)}</a>')
        pos = m.end()
    partes.append(html.escape(texto[pos:]))
    cuerpo = re.sub(r"\[/?(en|repite)\]", "", "".join(partes)).replace("\n", "<br>")
    return f'<div style="line-height:147%">{cuerpo}</div>'


class Puente(QObject):
    """Lleva lo que pasa en los hilos de fondo al hilo de la ventana."""
    evento = Signal(dict)
    audio = Signal(object, int)
    conexion = Signal(bool, str)
    nivel = Signal(float)
    frase = Signal(object)
    voz_terminada = Signal(bool)
    error_mic = Signal(str)


# ================================================================ piezas

def etiqueta(texto: str, tipo: str, nombre: str = "", alinear=None, ajustar: bool = False) -> QLabel:
    lbl = QLabel(texto)
    lbl.setFont(fuente(tipo))
    if nombre:
        lbl.setObjectName(nombre)
    if alinear is not None:
        lbl.setAlignment(alinear)
    lbl.setWordWrap(ajustar)
    return lbl


def boton(texto: str, estilo: str, tipo: str = "body", icono_nombre: str = "", color_icono: str = "") -> QPushButton:
    b = QPushButton(("  " + texto) if icono_nombre else texto)  # aire entre ícono y texto
    b.setObjectName(estilo)
    b.setFont(fuente(tipo))
    if estilo in tema.ALTURA_PILDORA:
        b.setFixedHeight(px(tema.ALTURA_PILDORA[estilo]))
    if icono_nombre:
        b.setIcon(icono(icono_nombre, color_icono or C["ink_muted_80"], px(18)))
        b.setIconSize(QSize(px(18), px(18)))
    return presionable(b)


def columna_centrada(contenido: QWidget | None = None, ancho: int = ANCHO_COLUMNA) -> tuple[QWidget, QVBoxLayout]:
    """Contenedor a todo lo ancho con una columna central de ancho máximo."""
    fuera = QWidget()
    h = QHBoxLayout(fuera)
    h.setContentsMargins(px(24), 0, px(24), 0)
    dentro = contenido or QWidget()
    dentro.setMaximumWidth(px(ancho))
    v = dentro.layout() or QVBoxLayout(dentro)
    v.setContentsMargins(0, 0, 0, 0)
    h.addStretch()
    h.addWidget(dentro, 100)
    h.addStretch()
    return fuera, v


class BotonMic(QAbstractButton):
    """El micrófono: un círculo dibujado a mano. Azul = tócame. Casi negro con anillo = te escucho."""

    def __init__(self) -> None:
        super().__init__()
        self.estado = "listo"  # listo | escuchando | hablando | ocupado | desconectado
        self.nivel = 0.0
        lado = px(104)
        self.setFixedSize(lado + px(28), lado + px(28))  # espacio para el anillo de volumen
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        presionable(self)

    def poner(self, estado: str) -> None:
        self.estado = estado
        if estado != "escuchando":
            self.nivel = 0.0
        self.update()

    def poner_nivel(self, nivel: float) -> None:
        self.nivel = nivel
        self.update()

    def paintEvent(self, _evento) -> None:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        centro = QRectF(self.rect()).center()
        radio = px(52)
        relleno, color_icono, nombre_icono = {
            "listo": (C["primary"], C["canvas"], "mic"),
            "escuchando": (C["ink"], C["canvas"], "mic"),
            "hablando": (C["primary"], C["canvas"], "square"),
            "ocupado": (C["chip"], C["ink_muted_48"], "clock"),
            "desconectado": (C["chip"], C["ink_muted_48"], "mic"),
        }[self.estado]
        if self.estado == "escuchando":  # anillo que crece con la voz
            grosor = px(3) + self.nivel * px(11)
            pintor.setPen(QPen(QColor(C["primary_focus"]), grosor))
            pintor.setBrush(Qt.BrushStyle.NoBrush)
            r = radio + px(4) + grosor / 2
            pintor.drawEllipse(centro, r, r)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(relleno))
        pintor.drawEllipse(centro, radio, radio)
        lado = px(40)
        icono(nombre_icono, color_icono, lado).paint(
            pintor, int(centro.x() - lado / 2), int(centro.y() - lado / 2), lado, lado)


class TarjetaClase(QFrame):
    """store-utility-card para la lista de "Mis clases"."""

    def __init__(self, clase: dict, al_tocar) -> None:
        super().__init__()
        self.setObjectName("tarjeta_clase")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._al_tocar = lambda: al_tocar(clase["id"])
        h = QHBoxLayout(self)
        h.setContentsMargins(px(24), px(20), px(24), px(20))
        col = QVBoxLayout()
        col.setSpacing(px(4))
        col.addWidget(etiqueta(f"Clase {clase['numero']} · {clase['titulo']}", "body_strong"))
        col.addWidget(etiqueta(clase["fecha"], "caption", "suave"))
        h.addLayout(col, 1)
        pr = clase.get("promedio_pronunciacion")
        if pr is not None:
            nota = QVBoxLayout()
            nota.setSpacing(0)
            nota.addWidget(etiqueta(str(pr), "tagline", alinear=Qt.AlignmentFlag.AlignRight))
            nota.addWidget(etiqueta("pronunciación", "caption", "suave", Qt.AlignmentFlag.AlignRight))
            h.addLayout(nota)
        flecha = etiqueta("›", "lead")
        flecha.setStyleSheet(f"color:{C['primary']}")
        h.addWidget(flecha)

    def mousePressEvent(self, evento) -> None:
        self._al_tocar()


# ================================================================ ventana

class Ventana(QMainWindow):
    def __init__(self, config: ConfigCliente, conexion: Conexion | None = None,
                 microfono: Microfono | None = None, parlante: Parlante | None = None) -> None:
        super().__init__()
        self.config = config
        tema.Escala.factor = max(0.8, config.tamano_letra / 17)
        tema.cargar_fuentes()
        self.puente = Puente()
        self.conexion = conexion or Conexion(config, self.puente.evento.emit, self.puente.audio.emit,
                                             self.puente.conexion.emit)
        self.microfono = microfono or Microfono(config)
        self.parlante = parlante or Parlante()
        self.info: dict = {}
        self.practica: str | None = None
        self.ocupado = False
        self.reintento_hecho = False
        self.en_clase = False
        self._clase_mostrada: dict | None = None

        self.puente.evento.connect(self._al_evento)
        self.puente.audio.connect(self._al_audio)
        self.puente.conexion.connect(self._al_cambiar_conexion)
        self.puente.nivel.connect(self._al_nivel)
        self.puente.frase.connect(self._al_frase)
        self.puente.voz_terminada.connect(self._al_terminar_voz)
        self.puente.error_mic.connect(lambda m: self._aviso(f"Problema con el micrófono: {m}"))

        self.setWindowTitle("Clase de Inglés")
        self.resize(px(960), px(860))
        self.setFont(fuente("body"))
        self.setStyleSheet(tema.qss())
        self._construir()
        self._actualizar_mic()

    # ================================================================ construcción

    def _construir(self) -> None:
        raiz = QWidget()
        raiz.setObjectName("raiz")
        v = QVBoxLayout(raiz)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # global-nav: negra, 44 px, enlaces de 12 px
        nav = QFrame()
        nav.setObjectName("nav")
        nav.setFixedHeight(px(44))
        h = QHBoxLayout(nav)
        h.setContentsMargins(px(24), 0, px(14), 0)
        self.lbl_app = etiqueta("Clase de Inglés", "caption_strong", "nav_titulo")
        h.addWidget(self.lbl_app)
        h.addStretch()
        self.nav_inicio = boton("Inicio", "nav_enlace", "nav_link")
        self.nav_inicio.clicked.connect(self._ir_inicio)
        self.nav_clases = boton("Mis clases", "nav_enlace", "nav_link")
        self.nav_clases.clicked.connect(self._ir_clases)
        for b in (self.nav_inicio, self.nav_clases):
            b.setFixedHeight(px(44))
            h.addWidget(b)
        v.addWidget(nav)

        self.banner = etiqueta("", "caption", "aviso", ajustar=True)
        self.banner.hide()
        v.addWidget(self.banner)

        self.paginas = QStackedWidget()
        for pagina in (self._pagina_inicio(), self._pagina_clase(), self._pagina_resumen(), self._pagina_clases()):
            self.paginas.addWidget(pagina)
        v.addWidget(self.paginas, 1)
        self.setCentralWidget(raiz)

    def _pagina_inicio(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Tile blanco (hero): titular, subtítulo, dos píldoras y la profe "sobre la superficie".
        hero = QWidget()
        hero.setObjectName("tile_blanco")
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(px(24), px(64), px(24), px(48))
        hv.setSpacing(0)
        self.lbl_saludo = etiqueta("¡Hola!", "hero", alinear=Qt.AlignmentFlag.AlignCenter)
        self.lbl_sub = etiqueta("Conectando con la profesora…", "lead", alinear=Qt.AlignmentFlag.AlignCenter, ajustar=True)
        self.lbl_sub.setStyleSheet(f"color:{C['ink_muted_80']}")
        hv.addWidget(self.lbl_saludo)
        hv.addSpacing(px(12))
        sub, sv = columna_centrada(ancho=680)
        sv.addWidget(self.lbl_sub)
        hv.addWidget(sub)
        hv.addSpacing(px(32))
        fila = QHBoxLayout()
        fila.setSpacing(px(17))
        fila.addStretch()
        self.btn_empezar = boton("Empezar la clase", "primario_grande", "button_large")
        self.btn_empezar.clicked.connect(lambda: self._empezar(False))
        self.btn_continuar = boton("Continuar la clase", "secundario", "body")
        self.btn_continuar.clicked.connect(lambda: self._empezar(True))
        self.btn_continuar.hide()
        fila.addWidget(self.btn_empezar)
        fila.addWidget(self.btn_continuar)
        fila.addStretch()
        hv.addLayout(fila)
        hv.addStretch()
        avatar = etiqueta("👩🏽‍🏫", "body", alinear=Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"font-size:{px(112)}px")
        # La única sombra del sistema: la del "producto" que descansa sobre la superficie.
        sombra = QGraphicsDropShadowEffect(avatar)
        sombra.setColor(QColor(0, 0, 0, 56))
        sombra.setOffset(3, 5)
        sombra.setBlurRadius(30)
        avatar.setGraphicsEffect(sombra)
        hv.addWidget(avatar)
        hv.addStretch()
        v.addWidget(hero, 3)

        # Tile parchment: el progreso en tres tarjetas.
        progreso = QWidget()
        progreso.setObjectName("tile_parchment")
        pv = QVBoxLayout(progreso)
        pv.setContentsMargins(px(24), px(32), px(24), px(40))
        pv.addWidget(etiqueta("Tu progreso", "tagline", alinear=Qt.AlignmentFlag.AlignCenter))
        pv.addSpacing(px(17))
        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(px(20))
        tarjetas.addStretch()
        self.datos = {}
        for clave, texto in (("clase", "Clase"), ("unidad", "Unidad"), ("palabras", "Palabras aprendidas")):
            t = QFrame()
            t.setObjectName("tarjeta")
            t.setMinimumWidth(px(190))
            tv = QVBoxLayout(t)
            tv.setContentsMargins(px(24), px(20), px(24), px(20))
            valor = etiqueta("–", "display_lg", alinear=Qt.AlignmentFlag.AlignCenter)
            nombre = etiqueta(texto, "caption", "suave", Qt.AlignmentFlag.AlignCenter, ajustar=True)
            tv.addWidget(valor)
            tv.addWidget(nombre)
            self.datos[clave] = (valor, nombre)
            tarjetas.addWidget(t)
        tarjetas.addStretch()
        pv.addLayout(tarjetas)
        v.addWidget(progreso, 0)
        return w

    def _pagina_clase(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # sub-nav: nombre de la profe + estado a la izquierda, "Terminar" a la derecha.
        subnav = QFrame()
        subnav.setObjectName("subnav")
        subnav.setMinimumHeight(px(52))
        h = QHBoxLayout(subnav)
        h.setContentsMargins(px(24), px(6), px(24), px(6))
        self.lbl_profe = etiqueta("Profe", "tagline")
        self.lbl_estado = etiqueta("", "caption", "suave")
        h.addWidget(self.lbl_profe)
        h.addSpacing(px(12))
        h.addWidget(self.lbl_estado, 1)
        self.btn_terminar = boton("Terminar clase", "secundario_chico", "caption")
        self.btn_terminar.clicked.connect(self._terminar)
        h.addWidget(self.btn_terminar)
        v.addWidget(subnav)

        # El chat: lienzo blanco, columna centrada.
        self.chat_columna = QWidget()
        self.chat = QVBoxLayout(self.chat_columna)
        self.chat.setContentsMargins(0, px(24), 0, px(24))
        self.chat.setSpacing(px(12))
        self.chat.addStretch()
        envoltura, _ = columna_centrada(self.chat_columna)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(envoltura)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        v.addWidget(self.scroll, 1)

        # Práctica: un tile oscuro de borde a borde. El cambio de superficie ES el énfasis.
        self.caja_practica = QFrame()
        self.caja_practica.setObjectName("tile_oscuro")
        pv = QVBoxLayout(self.caja_practica)
        pv.setContentsMargins(px(24), px(24), px(24), px(20))
        pv.setSpacing(px(4))
        pv.addWidget(etiqueta("Repite en voz alta", "caption", "sobre_oscuro_suave", Qt.AlignmentFlag.AlignCenter))
        self.lbl_frase = etiqueta("", "display_lg", "sobre_oscuro", Qt.AlignmentFlag.AlignCenter, ajustar=True)
        pv.addWidget(self.lbl_frase)
        oir = boton("Escuchar despacio", "enlace_oscuro", "body", "volume-2", C["primary_on_dark"])
        oir.clicked.connect(lambda: self._oir_ingles(self.practica))
        pv.addWidget(oir, alignment=Qt.AlignmentFlag.AlignCenter)
        self.caja_practica.hide()
        v.addWidget(self.caja_practica)

        # Barra inferior (parchment): apoyos a los lados, el micrófono al centro.
        barra = QFrame()
        barra.setObjectName("barra_inferior")
        bv = QVBoxLayout(barra)
        bv.setContentsMargins(px(24), px(12), px(24), px(16))
        bv.setSpacing(px(4))
        self.lbl_oido = etiqueta("", "caption", "suave", Qt.AlignmentFlag.AlignCenter)
        bv.addWidget(self.lbl_oido)
        fila = QHBoxLayout()
        fila.setSpacing(px(12))
        self.btn_repetir = boton("Repetir", "perla", "body", "refresh-cw")
        self.btn_repetir.clicked.connect(lambda: self._repetir(False))
        self.btn_despacio = boton("Más despacio", "perla", "body", "clock")
        self.btn_despacio.clicked.connect(lambda: self._repetir(True))
        self.btn_escribir = boton("Escribir", "perla", "body", "edit-3")
        self.btn_escribir.clicked.connect(self._alternar_escribir)
        self.btn_mic = BotonMic()
        self.btn_mic.clicked.connect(self._tocar_mic)
        mic_col = QVBoxLayout()
        mic_col.setSpacing(0)
        mic_col.addWidget(self.btn_mic, alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl_mic = etiqueta("", "caption", "suave", Qt.AlignmentFlag.AlignCenter)
        mic_col.addWidget(self.lbl_mic)
        fila.addStretch()
        fila.addWidget(self.btn_repetir, alignment=Qt.AlignmentFlag.AlignVCenter)
        fila.addWidget(self.btn_despacio, alignment=Qt.AlignmentFlag.AlignVCenter)
        fila.addSpacing(px(12))
        fila.addLayout(mic_col)
        fila.addSpacing(px(12))
        fila.addWidget(self.btn_escribir, alignment=Qt.AlignmentFlag.AlignVCenter)
        fila.addStretch()
        bv.addLayout(fila)

        self.fila_escribir = QWidget()
        fe = QHBoxLayout(self.fila_escribir)
        fe.setContentsMargins(0, px(8), 0, 0)
        self.entrada = QLineEdit()
        self.entrada.setFont(fuente("body"))
        self.entrada.setPlaceholderText("Escribe aquí tu respuesta…")
        self.entrada.returnPressed.connect(self._enviar_texto)
        enviar = boton("Enviar", "primario", "body")
        enviar.clicked.connect(self._enviar_texto)
        fe.addWidget(self.entrada, 1)
        fe.addWidget(enviar)
        self.fila_escribir.hide()
        bv.addWidget(self.fila_escribir)
        v.addWidget(barra)
        return w

    def _pagina_resumen(self) -> QWidget:
        w = QWidget()
        w.setObjectName("tile_blanco")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.resumen = QTextBrowser()
        self.resumen.setOpenLinks(False)
        self.resumen.setFont(fuente("body"))
        self.resumen.anchorClicked.connect(lambda url: self._oir_ingles(url.toString()[3:]))
        self.resumen.document().setDocumentMargin(px(8))
        col, cv = columna_centrada()
        cv.setContentsMargins(0, px(40), 0, 0)
        cv.addWidget(self.resumen)
        v.addWidget(col, 1)
        barra = QFrame()
        barra.setObjectName("barra_inferior")
        h = QHBoxLayout(barra)
        h.setContentsMargins(px(32), px(12), px(32), px(12))
        h.addStretch()
        oir = boton("Escuchar el resumen", "secundario", "body")
        oir.clicked.connect(self._oir_resumen)
        volver = boton("Volver al inicio", "primario", "body")
        volver.clicked.connect(self._ir_inicio)
        h.addWidget(oir)
        h.addWidget(volver)
        h.addStretch()
        v.addWidget(barra)
        return w

    def _pagina_clases(self) -> QWidget:
        w = QWidget()
        w.setObjectName("tile_parchment")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, px(48), 0, 0)
        v.setSpacing(0)
        cab, cv = columna_centrada()
        cv.addWidget(etiqueta("Mis clases", "display_lg"))
        cv.addSpacing(px(4))
        cv.addWidget(etiqueta("Aquí quedan guardados los resúmenes de todas tus clases.", "body", "suave", ajustar=True))
        v.addWidget(cab)
        v.addSpacing(px(24))
        self.lista = QWidget()
        self.lista_v = QVBoxLayout(self.lista)
        self.lista_v.setSpacing(px(12))
        envoltura, _ = columna_centrada(self.lista)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(envoltura)
        v.addWidget(scroll, 1)
        return w

    # ================================================================ navegación

    def _ir_inicio(self) -> None:
        if self.en_clase and self.paginas.currentIndex() == PAG_CLASE:
            self.parlante.detener()
            self.microfono.terminar_ya()
        self.paginas.setCurrentIndex(PAG_INICIO)
        self.conexion.enviar_control(p.ESTADO)

    def _ir_clases(self) -> None:
        self.paginas.setCurrentIndex(PAG_CLASES)
        self.conexion.enviar_control(p.LISTAR_CLASES)

    def _empezar(self, continuar: bool) -> None:
        if not self.conexion.conectada:
            self._aviso(self.config.mensaje_servidor_apagado)
            return
        self._limpiar_chat()
        self.en_clase = True
        self.paginas.setCurrentIndex(PAG_CLASE)
        self._ocupar("Preparando la clase…")
        self.conexion.enviar_control(p.EMPEZAR, continuar=continuar)

    # ================================================================ eventos del servidor

    def _al_cambiar_conexion(self, conectado: bool, mensaje: str) -> None:
        if conectado:
            self.banner.hide()
            if self.en_clase and self.paginas.currentIndex() == PAG_CLASE:
                # Se había caído en plena clase: se retoma donde iba.
                self._limpiar_chat()
                self._ocupar("Reconectado. Retomando la clase…")
                self.conexion.enviar_control(p.EMPEZAR, continuar=True)
        else:
            self._aviso(mensaje, fijo=True)
            self.ocupado = False
        self.btn_empezar.setEnabled(conectado)
        self.btn_continuar.setEnabled(conectado)
        self._actualizar_mic()

    def _al_evento(self, ev: dict) -> None:
        tipo = ev["evento"]
        if tipo == p.EV_INFO:
            self._mostrar_info(ev)
        elif tipo == p.EV_ESTADO:
            self.lbl_estado.setText(ev.get("mensaje", ""))
            if ev.get("estado") == "tu_turno":
                self._liberar()
                self._escuchar_si_toca()
        elif tipo == p.EV_HISTORIAL:
            mensajes = ev["mensajes"]
            if mensajes and mensajes[-1]["role"] == "assistant":
                mensajes = mensajes[:-1]  # el último llega enseguida como EV_PROFE (con su voz)
            for m in mensajes:
                self._burbuja(m["role"], m["content"])
        elif tipo == p.EV_PROFE:
            self._burbuja("assistant", ev["texto"])
            self._mostrar_practica(ev.get("practica"))
            self.reintento_hecho = False
        elif tipo == p.EV_OIDO:
            self._al_oir(ev)
        elif tipo == p.EV_RESULTADO:
            self._tarjeta_resultado(ev)
        elif tipo == p.EV_RESUMEN:
            self.en_clase = False
            self._liberar()
            if ev.get("clase"):
                self._mostrar_resumen(ev["clase"])
            else:
                self._ir_inicio()
        elif tipo == p.EV_CLASES:
            self._mostrar_lista(ev["clases"])
        elif tipo == p.EV_CLASE:
            self._mostrar_resumen(ev["clase"])
        elif tipo == p.EV_ERROR:
            self._aviso(ev["mensaje"], leve=bool(ev.get("leve")))
            if not ev.get("leve"):
                self._liberar()
                self.lbl_estado.setText("Hubo un problema. Toca el micrófono para intentarlo otra vez.")

    def _mostrar_info(self, ev: dict) -> None:
        self.info = ev
        alumna, profe = ev["alumna"], ev["profesora"]
        self.setWindowTitle(f"Clase de Inglés de {alumna}")
        self.lbl_app.setText(f"Clase de Inglés · {alumna}")
        self.lbl_saludo.setText(f"¡Hola, {alumna}!")
        self.lbl_sub.setText(
            f"Soy {profe}, tu profesora. Empezamos desde cero, paso a paso y sin afanes."
            if ev["clase_numero"] == 1 else f"Hoy es tu clase número {ev['clase_numero']}. Qué bueno verte otra vez.")
        self.lbl_profe.setText(f"Profe {profe}")
        self.datos["clase"][0].setText(str(ev["clase_numero"]))
        self.datos["unidad"][0].setText(f"{ev['unidad_numero']}/{ev['total_unidades']}")
        self.datos["unidad"][1].setText(ev["unidad_titulo"])
        self.datos["palabras"][0].setText(str(ev["palabras_aprendidas"]))
        self.btn_continuar.setVisible(bool(ev.get("hay_clase_en_curso")))

    # ================================================================ voz y micrófono

    def _al_audio(self, audio: np.ndarray, frecuencia: int) -> None:
        self.microfono.terminar_ya()
        self.lbl_estado.setText("Hablando…")
        self._actualizar_mic(hablando=True)
        self.parlante.reproducir(audio, frecuencia, self.puente.voz_terminada.emit)

    def _al_terminar_voz(self, completo: bool) -> None:
        if self.parlante.sonando:  # ya empezó otro audio
            return
        self._liberar()
        self.lbl_estado.setText("Tu turno")
        if completo:
            self._escuchar_si_toca()

    def _escuchar_si_toca(self) -> None:
        if (self.config.conversacion_automatica and self.en_clase and self.paginas.currentIndex() == PAG_CLASE
                and not self.fila_escribir.isVisible()):
            self._escuchar()

    def _tocar_mic(self) -> None:
        if self.parlante.sonando:
            self.parlante.detener()  # interrumpir a la profe para contestar
            QTimer.singleShot(150, self._escuchar)
        elif self.microfono.grabando:
            self.microfono.terminar_ya()
        elif not self.ocupado:
            self._escuchar()

    def _escuchar(self) -> None:
        if self.microfono.grabando or self.ocupado or not self.en_clase:
            return
        if not self.conexion.conectada:
            self._aviso(self.config.mensaje_servidor_apagado, fijo=True)
            return
        self.lbl_estado.setText("Te escucho en inglés…" if self.practica else "Te escucho…")
        self.lbl_oido.setText("")
        self.microfono.escuchar(bool(self.practica), self.puente.frase.emit, self.puente.nivel.emit,
                                lambda e: self.puente.error_mic.emit(str(e)))
        QTimer.singleShot(50, self._actualizar_mic)

    def _al_frase(self, audio) -> None:
        self.lbl_oido.setText("")
        if audio is None:
            self.lbl_estado.setText("No te escuché. Toca el micrófono cuando quieras.")
            self._actualizar_mic()
            return
        if self.conexion.enviar_audio(audio):
            self._ocupar("Enviando…")
        else:
            self._aviso(self.config.mensaje_servidor_apagado, fijo=True)
        self._actualizar_mic()

    def _al_nivel(self, nivel: float) -> None:
        if self.microfono.grabando:
            self.btn_mic.poner_nivel(nivel)

    def _al_oir(self, ev: dict) -> None:
        if ev.get("texto"):
            self._burbuja("user", ev["texto"])
            return
        self._liberar()
        if not self.reintento_hecho:
            self.reintento_hecho = True
            self.lbl_estado.setText("No te entendí bien. ¿Lo intentas otra vez, un poquito más fuerte?")
            QTimer.singleShot(600, self._escuchar)
        else:
            self.lbl_estado.setText("No te entendí. Toca el micrófono para intentarlo de nuevo.")

    # ================================================================ botones

    def _repetir(self, despacio: bool) -> None:
        if not self.ocupado and not self.microfono.grabando:
            self.parlante.detener()
            self._ocupar("…")
            self.conexion.enviar_control(p.REPETIR, despacio=despacio)

    def _oir_ingles(self, frase: str | None) -> None:
        if frase and not self.microfono.grabando:
            self.parlante.detener()
            self.conexion.enviar_control(p.REPETIR, texto=f"[en]{frase}[/en]", despacio=True)

    def _alternar_escribir(self) -> None:
        self.fila_escribir.setVisible(not self.fila_escribir.isVisible())
        if self.fila_escribir.isVisible():
            self.microfono.terminar_ya()
            self.entrada.setFocus()

    def _enviar_texto(self) -> None:
        texto = self.entrada.text().strip()
        if not texto or self.ocupado:
            return
        self.entrada.clear()
        self._burbuja("user", texto)
        self._mostrar_practica(None)
        self._ocupar("Pensando…")
        self.conexion.enviar_control(p.HABLAR_TEXTO, texto=texto)

    def _terminar(self) -> None:
        r = QMessageBox.question(self, "Terminar clase", "¿Terminamos la clase de hoy y vemos el resumen?")
        if r != QMessageBox.StandardButton.Yes:
            return
        self.parlante.detener()
        self.microfono.terminar_ya()
        self._ocupar("Preparando el resumen de tu clase…")
        self.conexion.enviar_control(p.TERMINAR)

    def _oir_resumen(self) -> None:
        r = (self._clase_mostrada or {}).get("resumen")
        if not r:
            return
        texto = f"{r.get('titulo', '')}. {r.get('resumen', '')} "
        if r.get("palabras_nuevas"):
            texto += "Las palabras nuevas: " + " ".join(f"[en]{x['en']}[/en], {x['es']}." for x in r["palabras_nuevas"]) + " "
        if r.get("tarea"):
            texto += f"Tu tarea: {r['tarea']}"
        self.conexion.enviar_control(p.REPETIR, texto=texto)

    # ================================================================ pintar cosas

    def _ocupar(self, mensaje: str) -> None:
        self.ocupado = True
        self.lbl_estado.setText(mensaje)
        self._actualizar_mic()

    def _liberar(self) -> None:
        self.ocupado = False
        self._actualizar_mic()

    def _actualizar_mic(self, hablando: bool = False) -> None:
        if self.microfono.grabando:
            estado, texto = "escuchando", "Te escucho · toca al terminar"
        elif hablando or self.parlante.sonando:
            estado, texto = "hablando", "Toca para interrumpir"
        elif not self.conexion.conectada:
            estado, texto = "desconectado", "Sin conexión"
        elif self.ocupado:
            estado, texto = "ocupado", "Un momento…"
        else:
            estado, texto = "listo", "Toca y repite" if self.practica else "Toca para hablar"
        self.btn_mic.poner(estado)
        self.lbl_mic.setText(texto)
        for b in (self.btn_repetir, self.btn_despacio):
            b.setEnabled(estado in ("listo", "hablando"))

    def _limpiar_chat(self) -> None:
        while self.chat.count() > 1:
            item = self.chat.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._mostrar_practica(None)

    def _agregar_al_chat(self, widget: QWidget, lado: str) -> None:
        fila = QHBoxLayout()
        fila.setContentsMargins(0, 0, 0, 0)
        widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        widget.setMaximumWidth(px(560) if lado != "centro" else px(ANCHO_COLUMNA))
        if lado != "izquierda":
            fila.addStretch()
        fila.addWidget(widget)
        if lado != "derecha":
            fila.addStretch()
        contenedor = QWidget()
        contenedor.setLayout(fila)
        self.chat.insertWidget(self.chat.count() - 1, contenedor)
        QTimer.singleShot(60, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def _burbuja(self, rol: str, texto: str) -> None:
        if rol == "user" and texto.startswith("[Resultado de práctica"):
            return  # ya se mostró como tarjeta de resultado
        lbl = QLabel()
        lbl.setFont(fuente("body"))
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        natural = QFontMetrics(lbl.font()).horizontalAdvance(re.sub(r"\[/?(en|repite)\]", "", texto)) + px(42)
        lbl.setMinimumWidth(min(natural, px(560)))
        if rol == "assistant":
            lbl.setObjectName("burbuja_profe")
            lbl.setText(a_html(texto))
            lbl.linkActivated.connect(lambda enlace: self._oir_ingles(enlace[3:]))
            self._agregar_al_chat(lbl, "izquierda")
        else:
            lbl.setObjectName("burbuja_alumna")
            lbl.setText(f'<div style="line-height:147%">{html.escape(texto)}</div>')
            self._agregar_al_chat(lbl, "derecha")

    def _tarjeta_resultado(self, r: dict) -> None:
        palabras = " ".join(
            f'<span style="color:{C[w["nivel"]]};{"text-decoration:underline;" if w["nivel"] == "falta" else ""}">'
            f'{html.escape(w["palabra"])}</span>' for w in r["palabras"])
        mensaje = "¡Perfecto!" if r["puntaje"] >= 85 else "¡Muy bien, casi!" if r["puntaje"] >= 60 else "Vamos de nuevo"
        lbl = QLabel(
            f'<div align="center"><span style="{css_tipo("caption_strong", C["ink_muted_48"])}">{mensaje} · '
            f'{r["puntaje"]}/100</span><br><span style="{css_tipo("display_lg")}">{palabras}</span><br>'
            f'<span style="{css_tipo("caption", C["ink_muted_48"])}">Se escuchó: “{html.escape(r["oido"])}”</span></div>')
        lbl.setObjectName("resultado")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        self._agregar_al_chat(lbl, "centro")

    def _mostrar_practica(self, frase: str | None) -> None:
        self.practica = frase
        self.caja_practica.setVisible(bool(frase))
        if frase:
            self.lbl_frase.setText(frase)
        self._actualizar_mic()

    def _aviso(self, mensaje: str, leve: bool = False, fijo: bool = False) -> None:
        self.banner.setObjectName("aviso_leve" if leve else "aviso")
        self.banner.style().unpolish(self.banner)  # re-aplica el estilo según el nuevo nombre
        self.banner.style().polish(self.banner)
        self.banner.setText(mensaje)
        self.banner.show()
        if not fijo:
            QTimer.singleShot(9000, lambda: self.conexion.conectada and self.banner.hide())

    def _mostrar_lista(self, clases: list[dict]) -> None:
        while self.lista_v.count():
            item = self.lista_v.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not clases:
            self.lista_v.addWidget(etiqueta("Todavía no hay clases terminadas.", "body", "suave"))
        for c in clases:
            self.lista_v.addWidget(TarjetaClase(c, lambda id_clase: self.conexion.enviar_control(p.VER_CLASE, id=id_clase)))
        self.lista_v.addStretch()

    def _mostrar_resumen(self, clase: dict) -> None:
        self._clase_mostrada = clase
        r = clase["resumen"]
        e = html.escape
        linea = f"border-top:1px solid {C['hairline']}"

        def seccion(titulo: str) -> str:
            return f'<p style="{css_tipo("tagline")} margin-top:{px(32)}px; margin-bottom:{px(8)}px">{titulo}</p>'

        h = [f'<p style="{css_tipo("caption", C["ink_muted_48"])}">Clase {clase["numero"]} · {e(clase["fecha"])}</p>',
             f'<p style="{css_tipo("display_lg")} margin-top:{px(4)}px">{e(r.get("titulo", ""))}</p>',
             f'<p style="{css_tipo("lead_airy", C["ink_muted_80"])} line-height:150%">{e(r.get("resumen", ""))}</p>']
        if r.get("palabras_nuevas"):
            h.append(seccion("Palabras nuevas"))
            h.append(f'<table width="100%" cellspacing="0" cellpadding="{px(10)}">'
                     f'<tr style="{css_tipo("caption", C["ink_muted_48"])}"><td>Inglés</td><td>Español</td><td>Cómo suena</td></tr>')
            for x in r["palabras_nuevas"]:
                h.append(f'<tr><td style="{linea}"><a href="en:{e(x.get("en", ""))}" style="color:{C["primary"]};'
                         f'text-decoration:none;font-weight:600">{e(x.get("en", ""))}</a></td>'
                         f'<td style="{linea}">{e(x.get("es", ""))}</td>'
                         f'<td style="{linea};color:{C["ink_muted_80"]}">{e(x.get("pronunciacion", ""))}</td></tr>')
            h.append("</table>")
        for titulo, clave in (("Frases para practicar", "frases_nuevas"), ("Lo que hiciste muy bien", "logros"),
                              ("Sonidos para seguir practicando", "dificultades_pronunciacion")):
            if r.get(clave):
                h.append(seccion(titulo) + "<ul>" + "".join(f'<li style="line-height:147%">{e(x)}</li>' for x in r[clave])
                         + "</ul>")
        if clase.get("promedio_pronunciacion") is not None:
            h.append(seccion("Pronunciación de hoy"))
            h.append(f'<p><span style="{css_tipo("display_lg")}">{clase["promedio_pronunciacion"]}</span>'
                     f'<span style="{css_tipo("body", C["ink_muted_48"])}"> /100 · {len(clase.get("practicas", []))} '
                     f'prácticas</span></p>')
        if r.get("tarea"):
            h.append(seccion("Tarea para la casa"))
            h.append(f'<table width="100%" cellpadding="{px(17)}" style="background:{C["parchment"]}"><tr><td>'
                     f'{e(r["tarea"])}</td></tr></table>')
        self.resumen.setHtml("".join(h))
        self.paginas.setCurrentIndex(PAG_RESUMEN)

    def closeEvent(self, evento) -> None:
        self.microfono.terminar_ya()
        self.parlante.detener()
        self.conexion.cerrar()
        super().closeEvent(evento)
