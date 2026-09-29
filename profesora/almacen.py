"""Progreso de la alumna y registro de cada clase (en la carpeta de datos del servidor).

Esta es la fuente de verdad; Obsidian es una copia legible para que Deivid siga el progreso.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .curriculo import UNIDADES

PROGRESO_INICIAL = {
    "clases_completadas": 0,
    "unidad_actual": 0,
    "palabras_aprendidas": [],       # [{"en": "hello", "es": "hola", "pronunciacion": "jélou", "clase": 1}]
    "frases_aprendidas": [],
    "dificultades_pronunciacion": [],
    "notas_profesora": "",
    "historial_puntajes": [],        # [{"clase": 1, "fecha": "2026-09-29", "promedio": 72, "practicas": 6}]
}


def _sin_repetidos(lista: list, clave=lambda x: x) -> list:
    vistos, salida = set(), []
    for item in lista:
        k = str(clave(item)).strip().lower()
        if k and k not in vistos:
            vistos.add(k)
            salida.append(item)
    return salida


def promedio_practicas(practicas: list[dict]) -> int | None:
    return round(sum(p["puntaje"] for p in practicas) / len(practicas)) if practicas else None


class Almacen:
    def __init__(self, carpeta: Path) -> None:
        self.carpeta = Path(carpeta)
        self.carpeta_clases = self.carpeta / "clases"
        self.archivo_progreso = self.carpeta / "progreso.json"
        self.archivo_en_curso = self.carpeta / "clase_en_curso.json"

    def _preparar(self) -> None:
        self.carpeta_clases.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ progreso

    def progreso(self) -> dict:
        self._preparar()
        if self.archivo_progreso.exists():
            try:
                return {**json.loads(json.dumps(PROGRESO_INICIAL)),
                        **json.loads(self.archivo_progreso.read_text(encoding="utf-8"))}
            except json.JSONDecodeError:
                pass
        return json.loads(json.dumps(PROGRESO_INICIAL))

    def guardar_progreso(self, progreso: dict) -> None:
        self._preparar()
        self._escribir(self.archivo_progreso, progreso)

    @staticmethod
    def _escribir(ruta: Path, datos) -> None:
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(ruta)

    # ------------------------------------------------------------ clase en curso (por si se cae la conexión)

    def guardar_en_curso(self, historial: list, practicas: list) -> None:
        self._preparar()
        self._escribir(self.archivo_en_curso, {"historial": historial, "practicas": practicas})

    def leer_en_curso(self) -> dict | None:
        if not self.archivo_en_curso.exists():
            return None
        try:
            datos = json.loads(self.archivo_en_curso.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return datos if datos.get("historial") else None

    def borrar_en_curso(self) -> None:
        self.archivo_en_curso.unlink(missing_ok=True)

    # ------------------------------------------------------------ clases terminadas

    def guardar_clase(self, resumen: dict, historial: list, practicas: list) -> dict:
        """Guarda la clase terminada, actualiza el progreso y devuelve el registro."""
        self._preparar()
        progreso = self.progreso()
        numero = progreso["clases_completadas"] + 1
        ahora = datetime.now()
        registro = {
            "id": f"clase-{numero:03d}-{ahora:%Y-%m-%d}",
            "numero": numero,
            "fecha": ahora.strftime("%Y-%m-%d"),
            "hora": ahora.strftime("%H:%M"),
            "unidad": progreso["unidad_actual"],
            "unidad_titulo": UNIDADES[progreso["unidad_actual"]]["titulo"],
            "resumen": resumen,
            "practicas": practicas,
            "promedio_pronunciacion": promedio_practicas(practicas),
            "transcripcion": historial,
        }
        self._escribir(self.carpeta_clases / f"{registro['id']}.json", registro)
        self.guardar_progreso(self._aplicar(progreso, registro))
        self.borrar_en_curso()
        return registro

    @staticmethod
    def _aplicar(progreso: dict, registro: dict) -> dict:
        resumen = registro["resumen"]
        progreso["clases_completadas"] += 1
        nuevas = [{**p, "clase": registro["numero"]} for p in resumen.get("palabras_nuevas", [])]
        progreso["palabras_aprendidas"] = _sin_repetidos(progreso["palabras_aprendidas"] + nuevas,
                                                         lambda p: p.get("en", ""))
        progreso["frases_aprendidas"] = _sin_repetidos(progreso["frases_aprendidas"] + resumen.get("frases_nuevas", []))
        if resumen.get("dificultades_pronunciacion") is not None:
            progreso["dificultades_pronunciacion"] = resumen["dificultades_pronunciacion"][:8]
        progreso["notas_profesora"] = resumen.get("notas_para_proxima_clase", "")
        if registro["promedio_pronunciacion"] is not None:
            progreso["historial_puntajes"].append({
                "clase": registro["numero"], "fecha": registro["fecha"],
                "promedio": registro["promedio_pronunciacion"], "practicas": len(registro["practicas"])})
        if resumen.get("unidad_dominada") and progreso["unidad_actual"] < len(UNIDADES) - 1:
            progreso["unidad_actual"] += 1
        return progreso

    def listar_clases(self) -> list[dict]:
        self._preparar()
        clases = []
        for ruta in sorted(self.carpeta_clases.glob("clase-*.json"), reverse=True):
            try:
                r = json.loads(ruta.read_text(encoding="utf-8"))
                clases.append({"id": r["id"], "numero": r["numero"], "fecha": r["fecha"],
                               "titulo": r["resumen"].get("titulo", ""),
                               "promedio_pronunciacion": r.get("promedio_pronunciacion")})
            except (json.JSONDecodeError, KeyError):
                continue
        return clases

    def leer_clase(self, id_clase: str) -> dict | None:
        if not re.fullmatch(r"clase-\d{3,}-\d{4}-\d{2}-\d{2}", id_clase or ""):
            return None
        ruta = self.carpeta_clases / f"{id_clase}.json"
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
