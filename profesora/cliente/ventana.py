"""Ventana de la app (PySide6). Pensada para que la use una persona que no es de tecnología:
letra grande, un solo botón grande de micrófono y la profesora que habla sola."""
from __future__ import annotations

import html
import re

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from .. import protocolo as p
from ..config import ConfigCliente
from .motor import Conexion, Microfono, Parlante

COLORES = {
    "fondo": "#FBF7F2", "tarjeta": "#FFFFFF", "texto": "#2B2622", "suave": "#7A6F66", "borde": "#EADFD4",
    "principal": "#E0662F", "principal_oscuro": "#BF4F1D", "ingles": "#1F5FD1", "ingles_fondo": "#E8F0FF",
    "alumna": "#FFE9DC", "bien": "#1E9E5A", "casi": "#C98A00", "falta": "#D64040", "aviso": "#FFF3CD",
}


def estilo(tamano: int) -> str:
    c = COLORES
    return f"""
    QWidget {{ background: {c['fondo']}; color: {c['texto']}; font-family: 'Segoe UI', sans-serif; font-size: {tamano}pt; }}
    QLabel#titulo {{ font-size: {tamano + 12}pt; font-weight: 700; }}
    QLabel#suave, QLabel#estado {{ color: {c['suave']}; }}
    QLabel#avatar {{ font-size: {tamano + 30}pt; }}
    QLabel#burbuja_profe {{ background: {c['tarjeta']}; border: 1px solid {c['borde']}; border-radius: 16px; padding: 12px 16px; }}
    QLabel#burbuja_alumna {{ background: {c['alumna']}; border: 1px solid {c['borde']}; border-radius: 16px; padding: 12px 16px; }}
    QLabel#nota {{ color: {c['suave']}; font-size: {tamano - 3}pt; }}
    QFrame#tarjeta {{ background: {c['tarjeta']}; border: 1px solid {c['borde']}; border-radius: 16px; }}
    QFrame#practica {{ background: {c['ingles_fondo']}; border: 2px dashed {c['ingles']}; border-radius: 16px; }}
    QLabel#frase {{ color: {c['ingles']}; font-size: {tamano + 12}pt; font-weight: 700; background: transparent; }}
    QLabel#banner {{ background: {c['falta']}; color: white; padding: 10px; border-radius: 10px; }}
    QPushButton {{ background: {c['tarjeta']}; border: 2px solid {c['borde']}; border-radius: 14px; padding: 10px 16px; }}
    QPushButton:hover {{ border-color: {c['principal']}; }}
    QPushButton:disabled {{ color: {c['suave']}; }}
    QPushButton#principal {{ background: {c['principal']}; color: white; border: none; font-size: {tamano + 4}pt; padding: 16px 36px; }}
    QPushButton#principal:hover {{ background: {c['principal_oscuro']}; }}
    QPushButton#principal:disabled {{ background: {c['borde']}; color: {c['suave']}; }}
    QPushButton#enlace {{ border: none; color: {c['ingles']}; background: transparent; }}
    QLineEdit {{ background: {c['tarjeta']}; border: 2px solid {c['borde']}; border-radius: 12px; padding: 10px; }}
    QTextBrowser, QListWidget {{ background: {c['tarjeta']}; border: 1px solid {c['borde']}; border-radius: 16px; padding: 12px; }}
    QListWidget::item {{ padding: 12px; border-bottom: 1px solid {c['borde']}; }}
    QScrollArea {{ border: none; }}
    """


def a_html(texto: str) -> str:
    """Texto con marcas [en]/[repite] -> HTML con el inglés resaltado y tocable (para oírlo)."""
    partes, pos = [], 0
    for m in re.finditer(r"\[(en|repite)\](.*?)\[/\1\]", texto, flags=re.S | re.I):
        partes.append(html.escape(texto[pos:m.start()]))
        frase = m.group(2).strip()
        partes.append(f'<a href="en:{html.escape(frase)}" style="color:{COLORES["ingles"]};font-weight:700;'
                      f'text-decoration:none;background:{COLORES["ingles_fondo"]}">&nbsp;{html.escape(frase)}&nbsp;</a>')
        pos = m.end()
    partes.append(html.escape(texto[pos:]))
    return re.sub(r"\[/?(en|repite)\]", "", "".join(partes)).replace("\n", "<br>")


class Puente(QObject):
    """Lleva lo que pasa en los hilos de fondo al hilo de la ventana."""
    evento = Signal(dict)
    audio = Signal(object, int)
    conexion = Signal(bool, str)
    nivel = Signal(float)
    frase = Signal(object)
    voz_terminada = Signal(bool)
    error_mic = Signal(str)


class Ventana(QMainWindow):
    def __init__(self, config: ConfigCliente, conexion: Conexion | None = None,
                 microfono: Microfono | None = None, parlante: Parlante | None = None) -> None:
        super().__init__()
        self.config = config
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

        self.puente.evento.connect(self._al_evento)
        self.puente.audio.connect(self._al_audio)
        self.puente.conexion.connect(self._al_cambiar_conexion)
        self.puente.nivel.connect(self._al_nivel)
        self.puente.frase.connect(self._al_frase)
        self.puente.voz_terminada.connect(self._al_terminar_voz)
        self.puente.error_mic.connect(lambda m: self._aviso(f"Problema con el micrófono: {m}"))

        self.setWindowTitle("Clase de Inglés")
        self.resize(900, 820)
        self.setStyleSheet(estilo(config.tamano_letra))
        self._construir()
        self._actualizar_mic()

    # ================================================================ construcción

    def _construir(self) -> None:
        raiz = QWidget()
        v = QVBoxLayout(raiz)
        v.setContentsMargins(20, 12, 20, 12)

        barra = QHBoxLayout()
        self.lbl_app = QLabel("Clase de Inglés")
        self.lbl_app.setStyleSheet("font-weight:700")
        barra.addWidget(self.lbl_app)
        barra.addStretch()
        for texto, accion in (("Inicio", self._ir_inicio), ("Mis clases", self._ir_clases)):
            b = QPushButton(texto)
            b.setObjectName("enlace")
            b.clicked.connect(accion)
            barra.addWidget(b)
        v.addLayout(barra)

        self.banner = QLabel()
        self.banner.setObjectName("banner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        v.addWidget(self.banner)

        self.paginas = QStackedWidget()
        self.paginas.addWidget(self._pagina_inicio())
        self.paginas.addWidget(self._pagina_clase())
        self.paginas.addWidget(self._pagina_resumen())
        self.paginas.addWidget(self._pagina_clases())
        v.addWidget(self.paginas, 1)
        self.setCentralWidget(raiz)

    def _pagina_inicio(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addStretch()
        for widget in (self._etiqueta("👩🏽‍🏫", "avatar"), ):
            v.addWidget(widget, alignment=Qt.AlignCenter)
        self.lbl_saludo = self._etiqueta("¡Hola!", "titulo")
        self.lbl_sub = self._etiqueta("Conectando con la profesora…", "suave")
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        v.addWidget(self.lbl_saludo, alignment=Qt.AlignCenter)
        v.addWidget(self.lbl_sub)
        fila = QHBoxLayout()
        fila.addStretch()
        self.datos = {}
        for clave, etiqueta in (("clase", "Clase"), ("unidad", "Unidad"), ("palabras", "Palabras aprendidas")):
            tarjeta = QFrame()
            tarjeta.setObjectName("tarjeta")
            tv = QVBoxLayout(tarjeta)
            valor = QLabel("–")
            valor.setStyleSheet(f"font-size:{self.config.tamano_letra + 10}pt;font-weight:700;color:{COLORES['principal']};background:transparent")
            valor.setAlignment(Qt.AlignCenter)
            texto = QLabel(etiqueta)
            texto.setObjectName("suave")
            texto.setStyleSheet("background:transparent")
            texto.setAlignment(Qt.AlignCenter)
            tv.addWidget(valor)
            tv.addWidget(texto)
            self.datos[clave] = (valor, texto)
            fila.addWidget(tarjeta)
        fila.addStretch()
        v.addLayout(fila)
        v.addSpacing(16)
        self.btn_empezar = QPushButton("▶  Empezar la clase")
        self.btn_empezar.setObjectName("principal")
        self.btn_empezar.clicked.connect(lambda: self._empezar(False))
        v.addWidget(self.btn_empezar, alignment=Qt.AlignCenter)
        self.btn_continuar = QPushButton("Continuar la clase que quedó abierta")
        self.btn_continuar.clicked.connect(lambda: self._empezar(True))
        self.btn_continuar.hide()
        v.addWidget(self.btn_continuar, alignment=Qt.AlignCenter)
        v.addStretch()
        return w

    def _pagina_clase(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        cab = QHBoxLayout()
        self.lbl_avatar = self._etiqueta("👩🏽‍🏫", "")
        self.lbl_avatar.setStyleSheet(f"font-size:{self.config.tamano_letra + 14}pt")
        cab.addWidget(self.lbl_avatar)
        col = QVBoxLayout()
        self.lbl_profe = self._etiqueta("Profe", "")
        self.lbl_profe.setStyleSheet("font-weight:700")
        self.lbl_estado = self._etiqueta("", "estado")
        col.addWidget(self.lbl_profe)
        col.addWidget(self.lbl_estado)
        cab.addLayout(col, 1)
        v.addLayout(cab)

        self.chat_contenedor = QWidget()
        self.chat = QVBoxLayout(self.chat_contenedor)
        self.chat.addStretch()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.chat_contenedor)
        v.addWidget(self.scroll, 1)

        self.caja_practica = QFrame()
        self.caja_practica.setObjectName("practica")
        pv = QVBoxLayout(self.caja_practica)
        t = QLabel("Repite en voz alta:")
        t.setStyleSheet("background:transparent")
        pv.addWidget(t, alignment=Qt.AlignCenter)
        self.lbl_frase = QLabel()
        self.lbl_frase.setObjectName("frase")
        self.lbl_frase.setWordWrap(True)
        self.lbl_frase.setAlignment(Qt.AlignCenter)
        pv.addWidget(self.lbl_frase)
        b = QPushButton("🔊 Escuchar despacio")
        b.clicked.connect(lambda: self._oir_ingles(self.practica))
        pv.addWidget(b, alignment=Qt.AlignCenter)
        self.caja_practica.hide()
        v.addWidget(self.caja_practica)

        self.lbl_oido = self._etiqueta("", "suave")
        self.lbl_oido.setAlignment(Qt.AlignCenter)
        v.addWidget(self.lbl_oido)

        controles = QHBoxLayout()
        controles.addStretch()
        self.btn_repetir = QPushButton("🔁 Repetir")
        self.btn_repetir.clicked.connect(lambda: self._repetir(False))
        self.btn_despacio = QPushButton("🐢 Más despacio")
        self.btn_despacio.clicked.connect(lambda: self._repetir(True))
        self.btn_mic = QPushButton()
        self.btn_mic.setFixedSize(160, 160)
        self.btn_mic.clicked.connect(self._tocar_mic)
        self.btn_escribir = QPushButton("⌨️ Escribir")
        self.btn_escribir.clicked.connect(self._alternar_escribir)
        self.btn_terminar = QPushButton("✔ Terminar clase")
        self.btn_terminar.setStyleSheet(f"color:{COLORES['bien']};border-color:{COLORES['bien']}")
        self.btn_terminar.clicked.connect(self._terminar)
        for b in (self.btn_repetir, self.btn_despacio, self.btn_mic, self.btn_escribir, self.btn_terminar):
            controles.addWidget(b, alignment=Qt.AlignVCenter)
        controles.addStretch()
        v.addLayout(controles)

        fila = QHBoxLayout()
        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("Escribe aquí tu respuesta…")
        self.entrada.returnPressed.connect(self._enviar_texto)
        enviar = QPushButton("Enviar")
        enviar.clicked.connect(self._enviar_texto)
        fila.addWidget(self.entrada, 1)
        fila.addWidget(enviar)
        self.fila_escribir = QWidget()
        self.fila_escribir.setLayout(fila)
        self.fila_escribir.hide()
        v.addWidget(self.fila_escribir)
        return w

    def _pagina_resumen(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.resumen = QTextBrowser()
        self.resumen.setOpenLinks(False)
        self.resumen.anchorClicked.connect(lambda url: self._oir_ingles(url.toString()[3:]))
        v.addWidget(self.resumen, 1)
        fila = QHBoxLayout()
        fila.addStretch()
        b = QPushButton("🔊 Escuchar el resumen")
        b.clicked.connect(self._oir_resumen)
        fila.addWidget(b)
        b = QPushButton("Volver al inicio")
        b.setObjectName("principal")
        b.clicked.connect(self._ir_inicio)
        fila.addWidget(b)
        fila.addStretch()
        v.addLayout(fila)
        self._clase_mostrada: dict | None = None
        return w

    def _pagina_clases(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(self._etiqueta("Mis clases", "titulo"))
        v.addWidget(self._etiqueta("Aquí quedan guardados los resúmenes de todas tus clases.", "suave"))
        self.lista = QListWidget()
        self.lista.itemClicked.connect(lambda item: self.conexion.enviar_control(p.VER_CLASE, id=item.data(Qt.UserRole)))
        v.addWidget(self.lista, 1)
        return w

    @staticmethod
    def _etiqueta(texto: str, nombre: str) -> QLabel:
        lbl = QLabel(texto)
        if nombre:
            lbl.setObjectName(nombre)
        return lbl

    # ================================================================ navegación

    def _ir_inicio(self) -> None:
        if self.en_clase and self.paginas.currentIndex() == 1:
            self.parlante.detener()
            self.microfono.terminar_ya()
        self.paginas.setCurrentIndex(0)
        self.conexion.enviar_control(p.ESTADO)

    def _ir_clases(self) -> None:
        self.paginas.setCurrentIndex(3)
        self.conexion.enviar_control(p.LISTAR_CLASES)

    def _empezar(self, continuar: bool) -> None:
        if not self.conexion.conectada:
            self._aviso(self.config.mensaje_servidor_apagado)
            return
        self._limpiar_chat()
        self.en_clase = True
        self.paginas.setCurrentIndex(1)
        self._ocupar("Preparando la clase…")
        self.conexion.enviar_control(p.EMPEZAR, continuar=continuar)

    # ================================================================ eventos del servidor

    def _al_cambiar_conexion(self, conectado: bool, mensaje: str) -> None:
        if conectado:
            self.banner.hide()
            if self.en_clase and self.paginas.currentIndex() == 1:
                # Se había caído en plena clase: se retoma donde iba.
                self._limpiar_chat()
                self._ocupar("Reconectado. Retomando la clase…")
                self.conexion.enviar_control(p.EMPEZAR, continuar=True)
        else:
            self.banner.setText("⚠  " + mensaje)
            self.banner.show()
            self.ocupado = False
        self.btn_empezar.setEnabled(conectado)
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
            self._aviso(ev["mensaje"], grave=not ev.get("leve"))
            if not ev.get("leve"):
                self._liberar()
                self.lbl_estado.setText("Hubo un problema. Toca el micrófono para intentarlo otra vez.")

    def _mostrar_info(self, ev: dict) -> None:
        self.info = ev
        alumna, profe = ev["alumna"], ev["profesora"]
        self.setWindowTitle(f"Clase de Inglés de {alumna}")
        self.lbl_app.setText(f"🇺🇸  Clase de Inglés de {alumna}")
        self.lbl_saludo.setText(f"¡Hola, {alumna}!")
        self.lbl_sub.setText(
            f"Soy {profe}, tu profesora. Vamos a empezar desde cero, paso a paso y sin afanes."
            if ev["clase_numero"] == 1 else f"Hoy es tu clase número {ev['clase_numero']}. ¡Qué bueno verte otra vez!")
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
        self.lbl_avatar.setText("🗣️")
        self._actualizar_mic(hablando=True)
        self.parlante.reproducir(audio, frecuencia, self.puente.voz_terminada.emit)

    def _al_terminar_voz(self, completo: bool) -> None:
        self.lbl_avatar.setText("👩🏽‍🏫")
        if self.parlante.sonando:  # ya empezó otro audio
            return
        self._liberar()
        self.lbl_estado.setText("Tu turno")
        if completo:
            self._escuchar_si_toca()

    def _escuchar_si_toca(self) -> None:
        if (self.config.conversacion_automatica and self.en_clase and self.paginas.currentIndex() == 1
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
            self._aviso(self.config.mensaje_servidor_apagado)
            return
        self.lbl_estado.setText("Te escucho en inglés…" if self.practica else "Te escucho…")
        self.lbl_oido.setText("🎤 …")
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
            self._aviso(self.config.mensaje_servidor_apagado)
        self._actualizar_mic()

    def _al_nivel(self, nivel: float) -> None:
        if self.microfono.grabando:
            borde = 4 + int(nivel * 16)
            self.btn_mic.setStyleSheet(self._estilo_mic(COLORES["falta"], borde))

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
        if r != QMessageBox.Yes:
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

    @staticmethod
    def _estilo_mic(color: str, borde: int = 0) -> str:
        return (f"QPushButton {{ background:{color}; color:white; border-radius:80px; font-size:12pt; font-weight:600;"
                f" border:{borde}px solid rgba(214,64,64,0.35); }}")

    def _actualizar_mic(self, hablando: bool = False) -> None:
        if self.microfono.grabando:
            self.btn_mic.setText("🎤\nTe escucho…\n(toca al terminar)")
            self.btn_mic.setStyleSheet(self._estilo_mic(COLORES["falta"], 4))
        elif hablando or self.parlante.sonando:
            self.btn_mic.setText("🎤\nToca para\ninterrumpir")
            self.btn_mic.setStyleSheet(self._estilo_mic(COLORES["principal"]))
        elif self.ocupado or not self.conexion.conectada:
            self.btn_mic.setText("⏳\nEspera…")
            self.btn_mic.setStyleSheet(self._estilo_mic(COLORES["suave"]))
        else:
            self.btn_mic.setText("🎤\nToca y repite" if self.practica else "🎤\nToca para\nhablar")
            self.btn_mic.setStyleSheet(self._estilo_mic(COLORES["principal"]))

    def _limpiar_chat(self) -> None:
        while self.chat.count() > 1:
            item = self.chat.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._mostrar_practica(None)

    def _agregar_al_chat(self, widget: QWidget, alineacion) -> None:
        fila = QHBoxLayout()
        if alineacion != Qt.AlignLeft:
            fila.addStretch()
        fila.addWidget(widget, 5)
        if alineacion != Qt.AlignRight:
            fila.addStretch()
        contenedor = QWidget()
        contenedor.setLayout(fila)
        self.chat.insertWidget(self.chat.count() - 1, contenedor)
        QTimer.singleShot(60, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def _burbuja(self, rol: str, texto: str) -> None:
        if rol == "user" and texto.startswith("[Resultado de práctica"):
            return  # ya se mostró como tarjeta de resultado
        lbl = QLabel()
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        if rol == "assistant":
            lbl.setObjectName("burbuja_profe")
            lbl.setText(a_html(texto))
            lbl.linkActivated.connect(lambda enlace: self._oir_ingles(enlace[3:]))
            self._agregar_al_chat(lbl, Qt.AlignLeft)
        else:
            lbl.setObjectName("burbuja_alumna")
            lbl.setText(html.escape(texto))
            self._agregar_al_chat(lbl, Qt.AlignRight)

    def _tarjeta_resultado(self, r: dict) -> None:
        estrellas = "⭐⭐⭐" if r["puntaje"] >= 85 else "⭐⭐" if r["puntaje"] >= 60 else "⭐"
        palabras = " ".join(
            f'<span style="color:{COLORES[w["nivel"] if w["nivel"] != "falta" else "falta"]};'
            f'{"text-decoration:underline;" if w["nivel"] == "falta" else ""}">{html.escape(w["palabra"])}</span>'
            for w in r["palabras"])
        lbl = QLabel(f'<div align="center">{estrellas}<br><span style="font-size:{self.config.tamano_letra + 8}pt;'
                     f'font-weight:700">{palabras}</span><br><span style="color:{COLORES["suave"]}">'
                     f'Se escuchó: “{html.escape(r["oido"])}”</span></div>')
        lbl.setObjectName("burbuja_profe")
        lbl.setTextFormat(Qt.RichText)
        self._agregar_al_chat(lbl, Qt.AlignCenter)

    def _mostrar_practica(self, frase: str | None) -> None:
        self.practica = frase
        self.caja_practica.setVisible(bool(frase))
        if frase:
            self.lbl_frase.setText(frase)
        self._actualizar_mic()

    def _aviso(self, mensaje: str, grave: bool = True) -> None:
        self.banner.setText("⚠  " + mensaje)
        self.banner.setStyleSheet("" if grave else f"background:{COLORES['aviso']};color:#6B5200")
        self.banner.show()
        QTimer.singleShot(9000, lambda: self.conexion.conectada and self.banner.hide())

    def _mostrar_lista(self, clases: list[dict]) -> None:
        self.lista.clear()
        if not clases:
            self.lista.addItem("Todavía no hay clases terminadas.")
        for c in clases:
            pr = c.get("promedio_pronunciacion")
            item = QListWidgetItem(f"Clase {c['numero']}: {c['titulo']}   ·   {c['fecha']}"
                                   + (f"   ·   pronunciación {pr}/100" if pr is not None else ""))
            item.setData(Qt.UserRole, c["id"])
            self.lista.addItem(item)

    def _mostrar_resumen(self, clase: dict) -> None:
        self._clase_mostrada = clase
        r = clase["resumen"]
        e = html.escape
        c = COLORES
        h = [f"<h1>Clase {clase['numero']}: {e(r.get('titulo', ''))}</h1>",
             f"<p style='color:{c['suave']}'>{e(clase['fecha'])}</p><p>{e(r.get('resumen', ''))}</p>"]
        if r.get("palabras_nuevas"):
            h.append(f"<h2 style='color:{c['principal']}'>Palabras nuevas</h2><table width='100%' cellpadding='6'>"
                     f"<tr style='color:{c['suave']}'><td>Inglés</td><td>Español</td><td>Cómo suena</td></tr>")
            for x in r["palabras_nuevas"]:
                h.append(f"<tr><td><a href='en:{e(x.get('en', ''))}' style='color:{c['ingles']};font-weight:700;"
                         f"text-decoration:none'>{e(x.get('en', ''))} 🔊</a></td><td>{e(x.get('es', ''))}</td>"
                         f"<td>{e(x.get('pronunciacion', ''))}</td></tr>")
            h.append("</table>")
        for titulo, clave in (("Frases para practicar", "frases_nuevas"), ("¡Lo que hiciste muy bien!", "logros"),
                              ("Sonidos para seguir practicando", "dificultades_pronunciacion")):
            if r.get(clave):
                h.append(f"<h2 style='color:{c['principal']}'>{titulo}</h2><ul>"
                         + "".join(f"<li>{e(x)}</li>" for x in r[clave]) + "</ul>")
        if clase.get("promedio_pronunciacion") is not None:
            h.append(f"<h2 style='color:{c['principal']}'>Pronunciación de hoy</h2>"
                     f"<p><b>{clase['promedio_pronunciacion']}/100</b> en {len(clase.get('practicas', []))} prácticas</p>")
        if r.get("tarea"):
            h.append(f"<h2 style='color:{c['principal']}'>Tarea para la casa</h2>"
                     f"<p style='background:{c['ingles_fondo']};padding:10px'>{e(r['tarea'])}</p>")
        self.resumen.setHtml("".join(h))
        self.paginas.setCurrentIndex(2)

    def closeEvent(self, evento) -> None:
        self.microfono.terminar_ya()
        self.parlante.detener()
        self.conexion.cerrar()
        super().closeEvent(evento)
