"""Convierte el texto de la profesora en voz.

El texto viene con marcas [en]...[/en] y [repite]...[/repite]. Las partes en inglés se leen con
una voz nativa en inglés (más despacio) y el resto con una voz colombiana, para que la
pronunciación que escucha la alumna sea siempre la correcta.
"""
import io
import re
import wave

from . import config

_MARCAS = re.compile(r"\[(en|repite)\](.*?)\[/\1\]", re.S | re.I)


def segmentar(texto: str) -> list[tuple[str, str]]:
    """'Hola se dice [en]hello[/en].' -> [('es','Hola se dice'), ('en','hello'), ('es','.')]"""
    segmentos, pos = [], 0
    for m in _MARCAS.finditer(texto):
        if m.start() > pos:
            segmentos.append(("es", texto[pos:m.start()]))
        segmentos.append(("en", m.group(2)))
        pos = m.end()
    segmentos.append(("es", texto[pos:]))
    # Quita marcas sueltas o mal cerradas y segmentos sin nada pronunciable.
    limpios = []
    for idioma, t in segmentos:
        t = re.sub(r"\[/?(en|repite)\]", "", t, flags=re.I).strip()
        if re.search(r"\w", t):
            limpios.append((idioma, t))
    return limpios


def texto_plano(texto: str) -> str:
    return re.sub(r"\[/?(en|repite)\]", "", texto, flags=re.I)


# ---------------------------------------------------------------- Edge (voces neuronales de Microsoft)

async def _edge(segmentos: list[tuple[str, str]], despacio: bool) -> tuple[bytes, str]:
    import edge_tts

    audio = bytearray()
    for idioma, t in segmentos:
        if idioma == "en":
            voz, velocidad = config.VOZ_INGLES, ("-35%" if despacio else config.VELOCIDAD_INGLES)
        else:
            voz, velocidad = config.VOZ_ESPANOL, ("-10%" if despacio else "+0%")
        async for trozo in edge_tts.Communicate(t, voz, rate=velocidad).stream():
            if trozo["type"] == "audio":
                audio.extend(trozo["data"])
    return bytes(audio), "audio/mpeg"


# ---------------------------------------------------------------- Kokoro (100% local, opcional)

_kokoro = {}


def _kokoro_pipeline(codigo: str):
    if codigo not in _kokoro:
        from kokoro import KPipeline  # pip install kokoro soundfile  (español necesita espeak-ng)
        _kokoro[codigo] = KPipeline(lang_code=codigo)
    return _kokoro[codigo]


def _kokoro_voz(segmentos: list[tuple[str, str]], despacio: bool) -> tuple[bytes, str]:
    import numpy as np

    muestras = []
    for idioma, t in segmentos:
        if idioma == "en":
            pipe, voz, vel = _kokoro_pipeline("a"), config.KOKORO_VOZ_INGLES, (0.7 if despacio else 0.85)
        else:
            pipe, voz, vel = _kokoro_pipeline("e"), config.KOKORO_VOZ_ESPANOL, (0.9 if despacio else 1.0)
        for _, _, audio in pipe(t, voice=voz, speed=vel):
            muestras.append(np.asarray(audio, dtype=np.float32))
        muestras.append(np.zeros(int(24000 * 0.15), dtype=np.float32))  # pequeña pausa
    datos = (np.clip(np.concatenate(muestras), -1, 1) * 32767).astype(np.int16)
    salida = io.BytesIO()
    with wave.open(salida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(datos.tobytes())
    return salida.getvalue(), "audio/wav"


async def sintetizar(texto: str, despacio: bool = False) -> tuple[bytes, str] | None:
    """Devuelve (audio, tipo) o None si se debe usar la voz del navegador."""
    segmentos = segmentar(texto)
    if not segmentos or config.MOTOR_VOZ == "navegador":
        return None
    if config.MOTOR_VOZ == "kokoro":
        import asyncio
        return await asyncio.to_thread(_kokoro_voz, segmentos, despacio)
    return await _edge(segmentos, despacio)
