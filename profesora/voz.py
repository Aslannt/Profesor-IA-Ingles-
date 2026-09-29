"""La voz de la profesora (se genera en el PC y se envía como audio a la laptop).

El texto viene con marcas [en]...[/en] y [repite]...[/repite]: lo que está en inglés lo dice una
voz nativa en inglés (más despacio) y el resto una voz colombiana, así la alumna siempre escucha
la pronunciación correcta.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re

import numpy as np

from .config import ConfigServidor

logger = logging.getLogger(__name__)
FRECUENCIA_VOZ = 24000
_MARCAS = re.compile(r"\[(en|repite)\](.*?)\[/\1\]", re.S | re.I)
_SUELTAS = re.compile(r"\[/?(en|repite)\]", re.I)


def segmentar(texto: str) -> list[tuple[str, str]]:
    """'Hola se dice [en]hello[/en].' -> [('es', 'Hola se dice'), ('en', 'hello')]"""
    segmentos, pos = [], 0
    for m in _MARCAS.finditer(texto):
        if m.start() > pos:
            segmentos.append(("es", texto[pos:m.start()]))
        segmentos.append(("en", m.group(2)))
        pos = m.end()
    segmentos.append(("es", texto[pos:]))
    limpios = []
    for idioma, t in segmentos:
        t = _SUELTAS.sub("", t).strip()
        if re.search(r"\w", t):
            limpios.append((idioma, t))
    return limpios


def texto_plano(texto: str) -> str:
    return _SUELTAS.sub("", texto)


def frase_para_repetir(texto: str) -> str | None:
    frases = re.findall(r"\[repite\](.*?)\[/repite\]", texto, flags=re.S | re.I)
    return frases[-1].strip() if frases else None


class Voz:
    def __init__(self, config: ConfigServidor) -> None:
        self.config = config
        self._kokoro: dict = {}

    def sintetizar(self, texto: str, despacio: bool = False) -> np.ndarray:
        """Audio float32 mono a FRECUENCIA_VOZ. Lanza excepción si el motor falla."""
        segmentos = segmentar(texto)
        if not segmentos:
            return np.zeros(0, dtype=np.float32)
        pausa = np.zeros(int(FRECUENCIA_VOZ * 0.12), dtype=np.float32)
        partes = []
        for idioma, t in segmentos:
            if self.config.motor_voz == "kokoro":
                partes.append(self._kokoro_voz(idioma, t, despacio))
            else:
                partes.append(self._edge(idioma, t, despacio))
            partes.append(pausa)
        return np.concatenate(partes)

    # ------------------------------------------------------------ Edge (voces neuronales de Microsoft)

    def _edge(self, idioma: str, texto: str, despacio: bool) -> np.ndarray:
        import edge_tts

        if idioma == "en":
            voz, velocidad = self.config.voz_ingles, ("-35%" if despacio else self.config.velocidad_ingles)
        else:
            voz, velocidad = self.config.voz_espanol, ("-10%" if despacio else "+0%")

        async def _descargar() -> bytes:
            audio = bytearray()
            async for trozo in edge_tts.Communicate(texto, voz, rate=velocidad).stream():
                if trozo["type"] == "audio":
                    audio.extend(trozo["data"])
            return bytes(audio)

        return decodificar_mp3(asyncio.run(_descargar()))

    # ------------------------------------------------------------ Kokoro (100% local)

    def _kokoro_voz(self, idioma: str, texto: str, despacio: bool) -> np.ndarray:
        from kokoro import KPipeline  # pip install kokoro soundfile (el español necesita espeak-ng)

        codigo = "a" if idioma == "en" else "e"
        if codigo not in self._kokoro:
            self._kokoro[codigo] = KPipeline(lang_code=codigo)
        if idioma == "en":
            voz, vel = self.config.kokoro_voz_ingles, (0.7 if despacio else 0.85)
        else:
            voz, vel = self.config.kokoro_voz_espanol, (0.9 if despacio else 1.0)
        trozos = [np.asarray(a, dtype=np.float32) for _, _, a in self._kokoro[codigo](texto, voice=voz, speed=vel)]
        return np.concatenate(trozos) if trozos else np.zeros(0, dtype=np.float32)


def decodificar_mp3(datos: bytes) -> np.ndarray:
    """MP3 -> float32 mono a FRECUENCIA_VOZ, con PyAV (ya viene con faster-whisper)."""
    import av

    muestras = []
    with av.open(io.BytesIO(datos)) as contenedor:
        remuestreo = av.AudioResampler(format="flt", layout="mono", rate=FRECUENCIA_VOZ)
        for cuadro in contenedor.decode(audio=0):
            for c in remuestreo.resample(cuadro):
                muestras.append(c.to_ndarray().reshape(-1))
        for c in remuestreo.resample(None):
            muestras.append(c.to_ndarray().reshape(-1))
    return np.concatenate(muestras).astype(np.float32) if muestras else np.zeros(0, dtype=np.float32)
