# Profesora de Inglés con IA 👩🏽‍🏫

Una profesora de inglés **hablada**, hecha a la medida de Katerin: empieza desde **nivel cero**, explica todo
en **español**, se enfoca en la **pronunciación** y al final de cada clase deja un **resumen** guardado
(palabras nuevas, cómo se pronuncian, logros y tarea).

## ¿Cómo funciona una clase?

1. Katerin toca **“Empezar la clase”**. La profe Lucía la saluda con voz y le enseña algo nuevo.
2. Cuando la profe termina de hablar, **el micrófono se abre solo**: Katerin contesta hablando, como con una persona.
3. Cuando la profe quiere que repita algo en inglés, la frase aparece **en grande**. Katerin puede tocar
   **“🔊 Escuchar despacio”** las veces que quiera y luego decirla.
4. El programa escucha su pronunciación **palabra por palabra** (verde = bien, amarillo = casi, rojo = falta)
   y la profe le explica **qué hacer con la lengua, los labios o el aire** para mejorar ese sonido.
5. Al tocar **“✔ Terminar clase”** se genera el resumen, que queda guardado en **“Mis clases”** (se puede
   escuchar o imprimir). La próxima clase la profe **se acuerda** de lo que aprendió y de lo que le cuesta.

Otros botones: **🔁 Repetir**, **🐢 Más despacio**, **⌨️ Escribir** (si no quiere hablar), y tocar cualquier
palabra azul en inglés la vuelve a pronunciar.

### Por qué así (pensado para alguien a quien “nada le ha funcionado”)

- **Todo en español**, el inglés entra poquito a poquito: máximo 4–5 cosas nuevas por clase.
- **Turnos cortos** y siempre una pregunta al final: ella habla mucho más que en un curso normal.
- **Dos voces**: el español lo dice una voz colombiana y el inglés una voz **nativa estadounidense, más despacio**,
  así siempre escucha la pronunciación correcta.
- **Trucos de pronunciación “a la española”** (water → “uárer”) y un sonido difícil a la vez
  (la H suave, la TH, la V, las vocales largas, la S final, la -ED…).
- **Repaso espaciado** al comenzar cada clase y un **plan de 15 unidades** (saludos → números → familia →
  comida → rutina → pasado → conversación libre) en `app/curriculo.py`.
- Mucho refuerzo positivo: equivocarse es parte de aprender.

## Instalación (Windows)

1. Instala **Python** desde <https://www.python.org/downloads/> (marca **“Add Python to PATH”**).
2. Descarga esta carpeta y haz doble clic en **`iniciar.bat`**.
   - La primera vez instala todo y abre el archivo de configuración `.env` en el Bloc de notas.
   - Pon ahí la clave de la IA (ver abajo), guarda y cierra.
3. Se abre el navegador en `http://localhost:8000`. Usar **Google Chrome o Microsoft Edge**
   (son los que pueden escuchar el micrófono). La primera vez hay que **permitir el micrófono**.

Para las siguientes clases basta con doble clic en `iniciar.bat`.
En Mac/Linux: `./iniciar.sh`.

## El “cerebro”: elige una opción en `.env`

| Opción | Calidad | Costo | Requisitos |
|---|---|---|---|
| **Claude** (`PROVEEDOR_IA=anthropic`) — recomendado | La mejor: paciente, natural, buen criterio pedagógico | Se paga por uso. Una clase de ~20 min cuesta aprox. **USD 0,20–0,60** con `claude-opus-5-5` (con `claude-haiku-4-5`, unos centavos) | Clave en <https://console.anthropic.com> (se recarga saldo aparte) |
| **Ollama** (`PROVEEDOR_IA=ollama`) — 100% local | Buena, pero un modelo local se equivoca más y es más lento | Gratis | PC con 16 GB de RAM (ideal con tarjeta gráfica). Instalar <https://ollama.com> y ejecutar `ollama pull gemma3:12b` |

> Nota: el saldo de Claude Code (la herramienta con la que se construyó esto) **no es** el mismo saldo
> de la API. Para usar Claude en la app hay que crear una clave en console.anthropic.com y cargarle saldo;
> con USD 5 alcanza para muchas clases.

## La voz

| `MOTOR_VOZ` | Cómo suena | Notas |
|---|---|---|
| `edge` (por defecto) | **Muy natural** (voces neuronales de Microsoft). Español con acento colombiano (`es-CO-SalomeNeural`) e inglés nativo (`en-US-JennyNeural`) | Gratis, necesita internet. Otras voces: `es-CO-GonzaloNeural`, `en-US-AriaNeural`, `en-US-GuyNeural`… |
| `kokoro` | Natural y **100% local** | Instalar aparte: `pip install kokoro soundfile` (y `espeak-ng` para el español). Más pesado |
| `navegador` | La del navegador (más robótica) | Sin instalar nada. También se usa automáticamente si la voz falla |

El **reconocimiento de voz** (escuchar a Katerin) lo hace el navegador Chrome/Edge, gratis.

## Dónde queda todo guardado

- `datos/progreso.json`: nivel, unidad actual, palabras aprendidas, dificultades y notas de la profe.
- `datos/clases/clase-001-AAAA-MM-DD.md`: resumen de cada clase (se puede abrir con cualquier editor).
- `datos/clases/clase-001-AAAA-MM-DD.json`: resumen + transcripción completa.

Para empezar de cero, borra la carpeta `datos/`.

## Personalizar

- Nombres: `NOMBRE_ALUMNA` y `NOMBRE_PROFESORA` en `.env`.
- Forma de enseñar: `app/prompts.py`.
- Plan de estudios: `app/curriculo.py`.

## Estructura

```
app/servidor.py   servidor web local (FastAPI)
app/ia.py         conexión con Claude u Ollama
app/voz.py        texto → voz (Edge / Kokoro), separando español e inglés
app/prompts.py    personalidad y método de la profesora + formato del resumen
app/curriculo.py  plan de 15 unidades desde nivel 0
app/almacen.py    progreso y resúmenes en datos/
static/           la página (HTML, CSS, JS): micrófono, chat, práctica de pronunciación
```
