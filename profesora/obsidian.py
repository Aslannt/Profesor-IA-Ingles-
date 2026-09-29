"""Notas en el vault de Obsidian para seguir el progreso (mismo vault del Copiloto, carpeta aparte).

    <vault>/Inglés Katerin/
        Progreso de Katerin.md     <- tablero: unidad, gráfica de pronunciación, dificultades, clases
        Vocabulario.md             <- todas las palabras aprendidas
        Clases/2026-09-29 - Clase 001 - Saludos.md

Un vault de Obsidian es solo una carpeta de archivos Markdown: no hace falta tener Obsidian abierto.
Las notas se regeneran completas cada vez, así que no conviene editarlas a mano (se pisarían).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .curriculo import UNIDADES

logger = logging.getLogger(__name__)
ETIQUETA = "ingles-katerin"


def _limpio(texto: str) -> str:
    texto = re.sub(r'[\\/:*?"<>|#^\[\]]', "", texto or "").strip()
    return re.sub(r"\s+", " ", texto)[:60] or "Clase"


def _celda(texto) -> str:
    return str(texto if texto is not None else "").replace("|", "/").replace("\n", " ")


def nombre_nota_clase(registro: dict) -> str:
    return f"{registro['fecha']} - Clase {registro['numero']:03d} - {_limpio(registro['resumen'].get('titulo', ''))}"


class NotasObsidian:
    def __init__(self, vault: str | Path | None, carpeta: str, alumna: str) -> None:
        self.base = Path(vault) / carpeta if vault else None
        self.alumna = alumna

    @property
    def activo(self) -> bool:
        return self.base is not None

    def escribir_todo(self, registro: dict, progreso: dict, clases: list[dict]) -> None:
        """Nota de la clase recién terminada + tablero de progreso + vocabulario. Nunca rompe la clase."""
        if not self.activo:
            return
        try:
            (self.base / "Clases").mkdir(parents=True, exist_ok=True)
            (self.base / "Clases" / f"{nombre_nota_clase(registro)}.md").write_text(
                self.nota_clase(registro), encoding="utf-8")
            (self.base / f"Progreso de {self.alumna}.md").write_text(self.nota_progreso(progreso, clases), encoding="utf-8")
            (self.base / "Vocabulario.md").write_text(self.nota_vocabulario(progreso), encoding="utf-8")
        except OSError:
            logger.exception("No se pudieron escribir las notas de Obsidian en %s", self.base)

    # ------------------------------------------------------------ nota de una clase

    def nota_clase(self, r: dict) -> str:
        res = r["resumen"]
        l = ["---", f"fecha: {r['fecha']}", f"hora: \"{r['hora']}\"", f"clase: {r['numero']}",
             f"unidad: {r['unidad'] + 1}", f"pronunciacion: {r['promedio_pronunciacion'] if r['promedio_pronunciacion'] is not None else ''}",
             f"palabras_nuevas: {len(res.get('palabras_nuevas', []))}", f"tags: [{ETIQUETA}, clase]", "---", "",
             f"# Clase {r['numero']}: {res.get('titulo', '')}", "",
             f"**Unidad {r['unidad'] + 1}:** {r['unidad_titulo']} · [[Progreso de {self.alumna}|Ver progreso]]", "",
             res.get("resumen", ""), ""]
        if res.get("palabras_nuevas"):
            l += ["## Palabras nuevas", "", "| Inglés | Español | Cómo suena |", "|---|---|---|"]
            l += [f"| **{_celda(p.get('en'))}** | {_celda(p.get('es'))} | {_celda(p.get('pronunciacion'))} |"
                  for p in res["palabras_nuevas"]] + [""]
        if res.get("frases_nuevas"):
            l += ["## Frases", ""] + [f"- {f}" for f in res["frases_nuevas"]] + [""]
        if r["practicas"]:
            l += ["## Práctica de pronunciación", "", f"Promedio: **{r['promedio_pronunciacion']}/100**", "",
                  "| Frase | Puntaje | Lo que se oyó | Palabras con dificultad |", "|---|---|---|---|"]
            for p in r["practicas"]:
                dificiles = ", ".join(w["palabra"] for w in p["palabras"] if w["nivel"] != "bien") or "—"
                l.append(f"| {_celda(p['frase'])} | {p['puntaje']} | {_celda(p['oido']) or '—'} | {_celda(dificiles)} |")
            l.append("")
        if res.get("logros"):
            l += ["## Lo que hizo muy bien", ""] + [f"- {x}" for x in res["logros"]] + [""]
        if res.get("dificultades_pronunciacion"):
            l += ["## Sonidos por mejorar", ""] + [f"- {x}" for x in res["dificultades_pronunciacion"]] + [""]
        if res.get("tarea"):
            l += ["## Tarea", "", f"- [ ] {res['tarea']}", ""]
        if res.get("notas_para_proxima_clase"):
            l += ["## Notas de la profesora para la próxima clase", "", res["notas_para_proxima_clase"], ""]
        l += ["> [!note]- Transcripción de la clase"]
        for m in r["transcripcion"]:
            quien = "Profe" if m["role"] == "assistant" else self.alumna
            texto = re.sub(r"\[/?(en|repite)\]", "", m["content"]).replace("\n", " ")
            l.append(f"> **{quien}:** {texto}")
            l.append(">")
        return "\n".join(l) + "\n"

    # ------------------------------------------------------------ tablero de progreso

    def nota_progreso(self, progreso: dict, clases: list[dict]) -> str:
        unidad = progreso["unidad_actual"]
        barra = "🟩" * unidad + "🟨" + "⬜" * (len(UNIDADES) - unidad - 1)
        l = ["---", f"tags: [{ETIQUETA}, progreso]", f"clases: {progreso['clases_completadas']}",
             f"unidad: {unidad + 1}", f"palabras: {len(progreso['palabras_aprendidas'])}", "---", "",
             f"# Progreso de {self.alumna} en inglés", "",
             f"- **Clases terminadas:** {progreso['clases_completadas']}",
             f"- **Palabras aprendidas:** {len(progreso['palabras_aprendidas'])} ([[Vocabulario]])",
             f"- **Frases aprendidas:** {len(progreso['frases_aprendidas'])}",
             f"- **Unidad actual:** {unidad + 1} de {len(UNIDADES)} — {UNIDADES[unidad]['titulo']}", "", barra, ""]
        puntajes = progreso.get("historial_puntajes", [])
        if puntajes:
            recientes = puntajes[-20:]
            l += ["## Pronunciación por clase", "", "```mermaid", "xychart-beta",
                  '    title "Puntaje promedio de pronunciación"',
                  "    x-axis [" + ", ".join(f'"C{p["clase"]}"' for p in recientes) + "]",
                  '    y-axis "Puntaje" 0 --> 100',
                  "    line [" + ", ".join(str(p["promedio"]) for p in recientes) + "]", "```", ""]
        if progreso["dificultades_pronunciacion"]:
            l += ["## Lo que más le cuesta ahora", ""] + [f"- {d}" for d in progreso["dificultades_pronunciacion"]] + [""]
        if progreso["notas_profesora"]:
            l += ["## Plan de la profesora para la próxima clase", "", progreso["notas_profesora"], ""]
        l += ["## Plan de estudios", ""]
        for i, u in enumerate(UNIDADES):
            marca = "x" if i < unidad else " "
            actual = " ← **aquí va**" if i == unidad else ""
            l.append(f"- [{marca}] {i + 1}. {u['titulo']}{actual}")
        l.append("")
        if clases:
            l += ["## Clases", "", "| Clase | Fecha | Tema | Pronunciación |", "|---|---|---|---|"]
            for c in clases:
                nota = nombre_nota_clase({"fecha": c["fecha"], "numero": c["numero"], "resumen": {"titulo": c["titulo"]}})
                pr = c.get("promedio_pronunciacion")
                l.append(f"| [[{nota}\\|{c['numero']}]] | {c['fecha']} | {_celda(c['titulo'])} | {pr if pr is not None else '—'} |")
            l.append("")
        return "\n".join(l)

    def nota_vocabulario(self, progreso: dict) -> str:
        l = ["---", f"tags: [{ETIQUETA}, vocabulario]", "---", "", f"# Vocabulario de {self.alumna}", "",
             f"{len(progreso['palabras_aprendidas'])} palabras · [[Progreso de {self.alumna}|Ver progreso]]", "",
             "| Inglés | Español | Cómo suena | Clase |", "|---|---|---|---|"]
        for p in progreso["palabras_aprendidas"]:
            l.append(f"| **{_celda(p.get('en'))}** | {_celda(p.get('es'))} | {_celda(p.get('pronunciacion'))} | {p.get('clase', '')} |")
        if progreso["frases_aprendidas"]:
            l += ["", "## Frases", ""] + [f"- {f}" for f in progreso["frases_aprendidas"]]
        return "\n".join(l) + "\n"
