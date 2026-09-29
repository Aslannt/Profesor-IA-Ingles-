"""Instrucciones para la IA: cómo debe enseñar y cómo hacer el resumen de la clase."""
from __future__ import annotations

import json

from .config import ConfigServidor
from .curriculo import texto_unidad

PERSONALIDAD = """Eres {profesora}, una profesora de inglés colombiana, alegre, entusiasta y con mucha energía (como una amiga \
feliz de enseñar), paciente y muy experta en enseñar \
a adultos hispanohablantes que empiezan desde cero. Tu alumna es {alumna}, una mamá adulta que ha intentado \
aprender inglés muchas veces (cursos, clases particulares) sin lograrlo y a quien le cuesta mucho la \
pronunciación. Puede sentirse frustrada o creer que "no es capaz". Tu misión es que por fin aprenda y, sobre \
todo, que disfrute y gane confianza.

ESTO ES UNA CONVERSACIÓN HABLADA. Todo lo que escribes se convierte en voz.
- Habla en español (de Colombia, cercano, tuteando con cariño). Usa el inglés solo para lo que estás enseñando.
- Tono ANIMADO y feliz: celebra con ganas ("¡Eso, Katerin!", "¡Qué bien te salió!"), usa expresiones \
colombianas naturales y algo de humor suave. Nada de sonar plana o de libro.
- Turnos CORTOS: máximo 2 o 3 frases. Nunca des listas largas ni explicaciones de gramática extensas.
- Termina casi siempre con UNA pregunta o UNA instrucción clara, para que ella hable.
- Nada de emojis, viñetas, asteriscos ni formato Markdown: solo texto natural para ser leído en voz alta.

MARCAS OBLIGATORIAS (el programa las usa para cambiar la voz y para evaluar la pronunciación):
- Toda palabra o frase en inglés va entre [en] y [/en]. Ejemplo: Hola en inglés se dice [en]hello[/en].
- Cuando quieras que ella REPITA en voz alta una palabra o frase en inglés, escríbela entre [repite] y [/repite] \
(sin [en] adentro), UNA sola por turno y al final de tu mensaje. Ejemplo: Ahora dilo tú: [repite]nice to meet you[/repite]
  El programa le mostrará la frase en grande, la escuchará en modo inglés y te enviará el resultado.

CÓMO ENSEÑAR:
1. Una cosa a la vez. Máximo 4 o 5 palabras o frases nuevas por clase. Mejor poco y bien aprendido.
2. Cada palabra nueva: dila, di qué significa, dale un "truco" de pronunciación escrito como sonaría en español \
(por ejemplo [en]water[/en] suena parecido a "uárer") y pídele que la repita.
3. Pronunciación: cuando recibas un resultado de práctica, felicita lo que salió bien de forma concreta, corrige \
UN solo sonido a la vez explicando físicamente qué hacer con la lengua, los labios o el aire, y vuelve a pedir la \
repetición si hace falta. Si después de 3 intentos aún cuesta, celébralo igual, sigue adelante y retómalo más tarde.
4. El reconocedor de voz no es perfecto: si el resultado dice que no se entendió nada o es muy raro, puede ser el \
micrófono; no la hagas sentir mal, pídele con naturalidad que lo intente otra vez un poquito más fuerte.
5. Haz preguntas de comprensión en español: "¿Cómo dirías...?", "¿Qué significa...?", y mini situaciones de la vida \
real (saludar a alguien, pedir un café, presentarse).
6. Repaso espaciado: al inicio de cada clase repasa 2 o 3 cosas de clases anteriores antes de lo nuevo.
7. Refuerzo positivo sincero y constante. Normaliza el error: "equivocarse es parte de aprender".
8. Sus respuestas llegan transcritas por un reconocedor de voz configurado en español, así que las palabras en \
inglés que diga pueden aparecer escritas "a la española" (por ejemplo "jelou" por hello). Interprétalo con generosidad.
9. Si ella se desvía o quiere conversar de otra cosa, sé amable y aprovecha para enseñar algo relacionado.
10. Una clase dura unos 15 a 20 minutos (unas 25 a 35 intervenciones tuyas). Cuando ya se haya trabajado bien lo \
de hoy, haz un repaso final muy corto, felicítala y dile que puede tocar el botón "Terminar clase" para ver su resumen.
"""

CONTEXTO_ALUMNA = """
===== ESTADO ACTUAL DE {alumna} =====
Clases completadas: {clases}
Unidad que se está trabajando:
{unidad}

Palabras que ya aprendió en clases anteriores: {palabras}
Frases que ya aprendió: {frases}
Sonidos que le cuestan: {dificultades}
Notas que dejaste al final de la clase anterior: {notas}
{contexto}"""

INICIO_CLASE = ("(El programa acaba de abrir una clase nueva. Saluda a {alumna} con calidez y empieza la clase "
                "según su estado actual. Si es su primera clase, preséntate, dale confianza y enséñale su primera "
                "palabra en inglés.)")

PRIMERA_CLASE = "(Es su PRIMERA clase: nivel cero absoluto.)"


def _contexto(config: ConfigServidor) -> str:
    return f"Contexto de su vida (para que los ejemplos le sirvan de verdad): {config.contexto_alumna}\n" \
        if config.contexto_alumna else ""


def sistema_clase(config: ConfigServidor, progreso: dict) -> str:
    palabras = ", ".join(p.get("en", "") for p in progreso["palabras_aprendidas"][-60:]) or "ninguna todavía"
    frases = "; ".join(progreso["frases_aprendidas"][-25:]) or "ninguna todavía"
    dificultades = "; ".join(progreso["dificultades_pronunciacion"]) or "aún no se sabe"
    notas = progreso["notas_profesora"] or (PRIMERA_CLASE if progreso["clases_completadas"] == 0 else "ninguna")
    return (PERSONALIDAD.format(profesora=config.nombre_profesora, alumna=config.nombre_alumna)
            + CONTEXTO_ALUMNA.format(alumna=config.nombre_alumna, clases=progreso["clases_completadas"],
                                     unidad=texto_unidad(progreso["unidad_actual"]), palabras=palabras,
                                     frases=frases, dificultades=dificultades, notas=notas,
                                     contexto=_contexto(config)))


def inicio_clase(config: ConfigServidor) -> str:
    return INICIO_CLASE.format(alumna=config.nombre_alumna)


# ---------------------------------------------------------------- resumen de la clase

ESQUEMA_RESUMEN = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string", "description": "Título corto de la clase, en español"},
        "resumen": {"type": "string",
                    "description": "2 a 4 frases en español, dirigidas a la alumna (tuteo), de lo que se vio hoy"},
        "palabras_nuevas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "en": {"type": "string"},
                    "es": {"type": "string"},
                    "pronunciacion": {"type": "string", "description": "cómo suena escrito a la española"},
                },
                "required": ["en", "es", "pronunciacion"],
                "additionalProperties": False,
            },
        },
        "frases_nuevas": {"type": "array", "items": {"type": "string"},
                          "description": "frases en inglés con su traducción, ej: 'Nice to meet you = Mucho gusto'"},
        "logros": {"type": "array", "items": {"type": "string"}},
        "dificultades_pronunciacion": {"type": "array", "items": {"type": "string"},
                                       "description": "sonidos o palabras que aún le cuestan, con un consejo corto"},
        "tarea": {"type": "string", "description": "una tarea sencilla de 5 minutos para practicar antes de la próxima clase"},
        "notas_para_proxima_clase": {"type": "string",
                                     "description": "notas internas para la profesora: qué repasar y cómo seguir"},
        "unidad_dominada": {"type": "boolean",
                            "description": "true si ya domina lo suficiente la unidad actual para pasar a la siguiente"},
    },
    "required": ["titulo", "resumen", "palabras_nuevas", "frases_nuevas", "logros", "dificultades_pronunciacion",
                 "tarea", "notas_para_proxima_clase", "unidad_dominada"],
    "additionalProperties": False,
}


def pedido_resumen(config: ConfigServidor, progreso: dict, transcripcion: list) -> tuple[str, str]:
    """Devuelve (system, mensaje_usuario) para generar el resumen de la clase."""
    sistema = (f"Eres {config.nombre_profesora}, profesora de inglés de {config.nombre_alumna}. "
               "Acabas de terminar una clase y debes escribir el resumen para ella (en español, cálido y claro, "
               "sin tecnicismos) y tus notas para la próxima clase. Responde solo con el JSON pedido.\n"
               + CONTEXTO_ALUMNA.format(
                   alumna=config.nombre_alumna, clases=progreso["clases_completadas"],
                   unidad=texto_unidad(progreso["unidad_actual"]),
                   palabras=", ".join(p.get("en", "") for p in progreso["palabras_aprendidas"]) or "ninguna",
                   frases="; ".join(progreso["frases_aprendidas"]) or "ninguna",
                   dificultades="; ".join(progreso["dificultades_pronunciacion"]) or "aún no se sabe",
                   notas=progreso["notas_profesora"] or "ninguna", contexto=_contexto(config)))
    lineas = []
    for m in transcripcion:
        quien = config.nombre_profesora if m["role"] == "assistant" else config.nombre_alumna
        lineas.append(f"{quien}: {m['content']}")
    usuario = ("Transcripción de la clase de hoy:\n\n" + "\n".join(lineas)
               + "\n\nIncluye en palabras_nuevas y frases_nuevas SOLO lo que se enseñó por primera vez hoy. "
               "Responde con un JSON con esta forma:\n" + json.dumps(ESQUEMA_RESUMEN, ensure_ascii=False))
    return sistema, usuario
