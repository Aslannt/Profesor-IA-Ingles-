"""Califica la pronunciación: compara, palabra por palabra, la frase que debía repetir con lo que
Whisper entendió. Whisper también dice qué tan seguro está de cada palabra; una palabra
reconocida pero con poca seguridad se marca como "casi" (se entendió, pero con esfuerzo).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .transcriptor import Palabra

NUMEROS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
           "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
CONTRACCIONES = {
    "i'm": "i am", "you're": "you are", "he's": "he is", "she's": "she is", "it's": "it is", "we're": "we are",
    "they're": "they are", "what's": "what is", "don't": "do not", "can't": "can not", "cannot": "can not",
    "i'd": "i would", "that's": "that is", "where's": "where is", "let's": "let us", "doesn't": "does not",
    "isn't": "is not", "i've": "i have", "i'll": "i will",
}
SEGURIDAD_MINIMA = 0.45  # por debajo, una palabra "reconocida" cuenta como "casi"


def palabras(texto: str) -> list[str]:
    salida = []
    for p in re.sub(r"[^a-z0-9' ]+", " ", texto.lower().replace("’", "'").replace("`", "'")).split():
        if p in CONTRACCIONES:
            salida += CONTRACCIONES[p].split()
        elif p.isdigit() and int(p) < len(NUMEROS):
            salida.append(NUMEROS[int(p)])
        else:
            limpia = p.replace("'", "")
            if limpia:
                salida.append(limpia)
    return salida


def parecido(a: str, b: str) -> float:
    if a == b:
        return 1.0
    anterior = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        actual = [i]
        for j in range(1, len(b) + 1):
            actual.append(min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + (a[i - 1] != b[j - 1])))
        anterior = actual
    return 1 - anterior[-1] / max(len(a), len(b))


@dataclass(slots=True)
class ResultadoPalabra:
    palabra: str
    oido: str
    nivel: str  # "bien" | "casi" | "falta"
    nota: float


@dataclass(slots=True)
class Resultado:
    frase: str
    oido: str
    puntaje: int
    palabras: list[ResultadoPalabra]

    def a_dict(self) -> dict:
        return asdict(self)

    def para_la_profesora(self) -> str:
        detalle = ", ".join(
            f"{p.palabra} (bien)" if p.nivel == "bien"
            else f'{p.palabra} (casi: se oyó "{p.oido}")' if p.nivel == "casi"
            else f"{p.palabra} (no se reconoció)"
            for p in self.palabras
        )
        return (f'[Resultado de práctica de pronunciación] Frase: "{self.frase}". El reconocedor de voz en inglés '
                f'escuchó: "{self.oido or "(nada)"}". Por palabra: {detalle}. Puntaje aproximado: {self.puntaje}/100.')


def calificar(frase: str, oido: str, seguridad: list[Palabra] | None = None) -> Resultado:
    objetivo, dicho = palabras(frase), palabras(oido)
    # Seguridad de Whisper por palabra normalizada (en orden).
    probs: list[float] = []
    for p in seguridad or []:
        probs += [p.probabilidad] * len(palabras(p.texto))
    desde, resultado = 0, []
    for p in objetivo:
        mejor, idx = 0.0, -1
        for j in range(desde, min(len(dicho), desde + 4)):
            s = parecido(p, dicho[j])
            if s > mejor:
                mejor, idx = s, j
        if mejor >= 0.5:
            desde = idx + 1
        prob = probs[idx] if 0 <= idx < len(probs) else 1.0
        if mejor >= 0.99 and prob >= SEGURIDAD_MINIMA:
            nivel, nota = "bien", 1.0
        elif mejor >= 0.99:
            nivel, nota = "casi", 0.75
        elif mejor >= 0.5:
            nivel, nota = "casi", mejor * 0.8
        else:
            nivel, nota = "falta", 0.0
        resultado.append(ResultadoPalabra(p, dicho[idx] if mejor >= 0.5 else "", nivel, round(nota, 2)))
    puntaje = round(100 * sum(r.nota for r in resultado) / len(resultado)) if resultado else 0
    return Resultado(frase, oido, puntaje, resultado)
