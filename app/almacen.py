"""Guarda el progreso de la alumna y los resúmenes de cada clase en la carpeta datos/."""
import json
import re
from datetime import datetime

from . import config
from .curriculo import UNIDADES

PROGRESO_INICIAL = {
    "clases_completadas": 0,
    "unidad_actual": 0,
    "palabras_aprendidas": [],       # [{"en": "hello", "es": "hola", "pronunciacion": "jélou"}]
    "frases_aprendidas": [],         # ["Nice to meet you"]
    "dificultades_pronunciacion": [],
    "notas_profesora": "",           # observaciones de la profesora para la próxima clase
}


def _asegurar_carpetas() -> None:
    config.CARPETA_CLASES.mkdir(parents=True, exist_ok=True)


def cargar_progreso() -> dict:
    _asegurar_carpetas()
    if config.ARCHIVO_PROGRESO.exists():
        try:
            datos = json.loads(config.ARCHIVO_PROGRESO.read_text(encoding="utf-8"))
            return {**PROGRESO_INICIAL, **datos}
        except json.JSONDecodeError:
            pass
    return json.loads(json.dumps(PROGRESO_INICIAL))


def guardar_progreso(progreso: dict) -> None:
    _asegurar_carpetas()
    config.ARCHIVO_PROGRESO.write_text(json.dumps(progreso, ensure_ascii=False, indent=2), encoding="utf-8")


def _sin_repetidos(lista: list, clave=lambda x: x) -> list:
    vistos, salida = set(), []
    for item in lista:
        k = str(clave(item)).strip().lower()
        if k and k not in vistos:
            vistos.add(k)
            salida.append(item)
    return salida


def aplicar_resumen(progreso: dict, resumen: dict) -> dict:
    """Actualiza el progreso con lo aprendido en la clase que acaba de terminar."""
    progreso["clases_completadas"] += 1
    progreso["palabras_aprendidas"] = _sin_repetidos(
        progreso["palabras_aprendidas"] + resumen.get("palabras_nuevas", []), lambda p: p.get("en", "")
    )
    progreso["frases_aprendidas"] = _sin_repetidos(progreso["frases_aprendidas"] + resumen.get("frases_nuevas", []))
    # Las dificultades se reemplazan: son las vigentes según la última clase.
    if resumen.get("dificultades_pronunciacion") is not None:
        progreso["dificultades_pronunciacion"] = resumen["dificultades_pronunciacion"][:8]
    progreso["notas_profesora"] = resumen.get("notas_para_proxima_clase", "")
    if resumen.get("unidad_dominada") and progreso["unidad_actual"] < len(UNIDADES) - 1:
        progreso["unidad_actual"] += 1
    return progreso


def resumen_a_markdown(numero: int, fecha: str, resumen: dict) -> str:
    lineas = [f"# Clase {numero}: {resumen.get('titulo', '')}", f"*{fecha}*", "", resumen.get("resumen", ""), ""]
    if resumen.get("palabras_nuevas"):
        lineas += ["## Palabras nuevas", "", "| Inglés | Español | Cómo se pronuncia |", "|---|---|---|"]
        for p in resumen["palabras_nuevas"]:
            lineas.append(f"| **{p.get('en', '')}** | {p.get('es', '')} | {p.get('pronunciacion', '')} |")
        lineas.append("")
    if resumen.get("frases_nuevas"):
        lineas += ["## Frases para practicar", ""] + [f"- {f}" for f in resumen["frases_nuevas"]] + [""]
    if resumen.get("logros"):
        lineas += ["## ¡Lo que hiciste muy bien!", ""] + [f"- {l}" for l in resumen["logros"]] + [""]
    if resumen.get("dificultades_pronunciacion"):
        lineas += ["## Sonidos para seguir practicando", ""] + [f"- {d}" for d in resumen["dificultades_pronunciacion"]] + [""]
    if resumen.get("tarea"):
        lineas += ["## Tarea", "", resumen["tarea"], ""]
    return "\n".join(lineas)


def guardar_clase(resumen: dict, transcripcion: list) -> dict:
    """Guarda la clase (JSON con transcripción + Markdown para leer/imprimir). Devuelve el registro."""
    _asegurar_carpetas()
    progreso = cargar_progreso()
    numero = progreso["clases_completadas"] + 1
    ahora = datetime.now()
    fecha = ahora.strftime("%d/%m/%Y %I:%M %p")
    base = f"clase-{numero:03d}-{ahora:%Y-%m-%d}"
    registro = {
        "id": base,
        "numero": numero,
        "fecha": fecha,
        "unidad": progreso["unidad_actual"],
        "resumen": resumen,
        "transcripcion": transcripcion,
    }
    (config.CARPETA_CLASES / f"{base}.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.CARPETA_CLASES / f"{base}.md").write_text(resumen_a_markdown(numero, fecha, resumen), encoding="utf-8")
    guardar_progreso(aplicar_resumen(progreso, resumen))
    return registro


def listar_clases() -> list:
    _asegurar_carpetas()
    clases = []
    for ruta in sorted(config.CARPETA_CLASES.glob("clase-*.json"), reverse=True):
        try:
            r = json.loads(ruta.read_text(encoding="utf-8"))
            clases.append({"id": r["id"], "numero": r["numero"], "fecha": r["fecha"],
                           "titulo": r["resumen"].get("titulo", "")})
        except (json.JSONDecodeError, KeyError):
            continue
    return clases


def leer_clase(id_clase: str) -> dict | None:
    if not re.fullmatch(r"clase-\d{3,}-\d{4}-\d{2}-\d{2}", id_clase):
        return None
    ruta = config.CARPETA_CLASES / f"{id_clase}.json"
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))
