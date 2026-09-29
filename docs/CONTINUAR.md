---
tags: [profesora-ingles, proyecto, handoff]
proyecto: Profesora de Inglés con IA
repo: https://github.com/Aslannt/Profesor-IA-Ingles-
rama: claude/focused-mccarthy-qqmpxt
actualizado: 2026-09-29
---

# Profesora de Inglés con IA: estado del proyecto (para continuar en Claude Code)

> Documento para retomar el proyecto en otra sesión de Claude Code. Léelo completo antes de tocar código.
> Todo el proyecto y la comunicación con Deivid van **en español** (Deivid es de Colombia).

## 1. Qué es y para quién

- App para que **Katerin** (la mamá de Deivid) aprenda inglés **desde cero**. Ya intentó cursos y clases
  particulares sin éxito, y **le cuesta mucho la pronunciación**. Tiene reuniones de trabajo en inglés
  (por eso también usa el "Copiloto de Reuniones").
- Una profesora de voz, "Profe Lucía", que habla en **español colombiano**, enseña poco a poco, pide repetir
  frases en inglés, **califica la pronunciación palabra por palabra** y deja un **resumen** de cada clase.
- Deivid sigue el progreso en **Obsidian** (su vault personal).

## 2. Arquitectura (igual que el Copiloto de Reuniones)

```
Laptop de mamá (app PySide6)  <--WebSocket, red de la casa, SIN clave-->  PC de Deivid (servidor, RTX 3060)
  - graba su frase (detecta fin de frase por volumen)                    - Whisper "small" en GPU (ES en conversación, EN en práctica)
  - reproduce la voz de la profe                                         - Ollama qwen3.5:9b (el MISMO modelo del Copiloto)
  - chat, práctica, resúmenes                                            - Voz Edge TTS: es-CO-SalomeNeural + en-US-JennyNeural
                                                                         - progreso en datos/ + notas en Obsidian
```

- Puertos: **8770/TCP** (app) y **8771/UDP** (descubrimiento). El Copiloto usa 8765/8766.
- **Sin clave de conexión**, a pedido de Deivid. El firewall solo abre esos puertos en redes **privadas**.
- Repo del Copiloto (solo referencia, NO modificarlo sin permiso): `Aslannt/copiloto-reuniones`.
  De ahí se reutilizaron: conexión y reconexión, descubrimiento UDP, manejo de CUDA para Whisper,
  prevención de suspensión, el patrón del instalador (PyInstaller + Inno Setup) y la tarea programada.

## 3. Dónde está cada cosa

| Archivo | Qué hace |
|---|---|
| `profesora/servidor.py` | Servidor WebSocket; `SesionClase` = lógica de una clase (turnos, práctica, resumen) |
| `profesora/transcriptor.py` | Whisper; `corto=True` en la práctica (sin VAD, para palabras cortas como "hi") |
| `profesora/pronunciacion.py` | Calificación palabra por palabra (Levenshtein + probabilidad de Whisper) |
| `profesora/ia.py` | Ollama (`think: False`) o Claude (opcional, `proveedor_ia: "anthropic"`) |
| `profesora/voz.py` | Texto -> voz. Separa `[en]...[/en]` (voz inglesa) del español. Trozos en paralelo |
| `profesora/prompts.py` | Personalidad y método de la profesora + esquema JSON del resumen |
| `profesora/curriculo.py` | Plan de 15 unidades (saludos -> conversación libre) con foco de pronunciación |
| `profesora/almacen.py` | Progreso (`datos/progreso.json`), clases y clase en curso (para retomar si se cae la conexión) |
| `profesora/obsidian.py` | Notas: `Inglés Katerin/Progreso de Katerin.md`, `Vocabulario.md`, `Clases/*.md` |
| `profesora/protocolo.py` | Mensajes: JSON de control/eventos + binario (audio alumna float32 16 kHz; voz profe int16 24 kHz) |
| `profesora/cliente/motor.py` | Conexión, micrófono (`DetectorFrase`), parlante. Sin Qt |
| `profesora/cliente/ventana.py` | UI PySide6 |
| `profesora/cliente/tema.py` | Sistema de diseño "tipo Apple" (guía DESIGN-apple.md): tokens, Inter, un solo azul #0066cc |
| `packaging/` | `profesora.spec` (PyInstaller), `instalador.iss` (Inno Setup), `construir_instalador_mama.ps1` |
| `*.bat` / `*.ps1` en la raíz | Instalar servidor, iniciarlo, firewall, autoarranque, abrir la app en el PC |
| `tests/` | 11 pruebas, incluida una clase completa servidor-cliente con IA/oído/voz simulados (`pytest`) |

Marcas que la IA debe usar en sus respuestas: `[en]palabra[/en]` (inglés, voz nativa) y
`[repite]frase[/repite]` (la alumna debe repetirla; activa la práctica de pronunciación).

## 4. Cómo se corre (en el PC de Deivid, `C:\dev\profesora-ingles`)

1. `git pull` (rama `claude/focused-mccarthy-qqmpxt`).
2. `Iniciar Profesora (servidor).bat` y esperar `Escuchando en ws://0.0.0.0:8770`. Dejar la ventana abierta.
3. `Abrir App (probar en este PC).bat`. Encuentra el servidor sola.
4. Config del servidor: `config\servidor.local.json`. Config de la app: `config\cliente.json`
   (en la laptop instalada: `%LOCALAPPDATA%\ProfesoraDeIngles\config\cliente.json`).
5. Logs: `logs\servidor.log`, `logs\cliente.log`.

## 5. Historia y decisiones ya tomadas (no volver a discutir)

- Empezó como página web; se cambió a **app de escritorio** como el Copiloto (sin problema de HTTPS con el
  micrófono, Whisper local y seguimiento en Obsidian). La página web se eliminó.
- La laptop de mamá **no tiene Python**: recibe un `.exe` instalador con la IP del PC ya configurada.
- **Sin clave** de conexión (decisión de Deivid).
- **Smart App Control desactivado** en el PC de Deivid (bloqueaba la DLL de `av`/PyAV; también afectaba al Copiloto).
- El instalador acepta Python 3.11 a 3.14.
- Se arregló un bug de los `.bat`: el chequeo "¿ya está corriendo?" se encontraba a sí mismo.
  **El `Iniciar Servidor.bat` del Copiloto tiene el mismo bug** (pendiente preguntarle a Deivid si lo arregla).
- Diseño visual: guía tipo Apple. Único color de acción azul `#0066cc`. Excepción: verde/ámbar/rojo solo
  para la calificación de pronunciación.

## 6. Primera prueba real de Deivid (2026-09-29) y lo que se hizo

| Lo que notó | Qué se cambió (último commit) | ¿Resuelto? |
|---|---|---|
| La profe habla **demasiado calmada, aburrida** | Voz en español más rápida y aguda (`velocidad_espanol: "+10%"`, `tono_espanol: "+4Hz"`), inglés menos lento (`-5%`), y el prompt pide un tono **alegre y entusiasta** | Por probar |
| **Tarda mucho en empezar a hablar** | Trozos de voz pedidos a Edge **en paralelo**; respuestas de la IA más cortas (máx. 300 tokens, 2 o 3 frases); Whisper `beam_size=1`; la app detecta antes que ella terminó (1.3 s de silencio) | Mejoró algo; falta lo grande (ver §7) |
| **"hi" no lo detectaba** (3 intentos) | Práctica sin VAD ni filtro de "poca voz" en Whisper; micrófono más sensible (`umbral_voz: 0.007`); 0.5 s de audio previo | Por probar |

⚠️ Los valores viejos quedaron guardados en sus archivos de configuración. Para que apliquen los nuevos:
borrar `config\cliente.json` (se recrea solo) y en `config\servidor.local.json` cambiar
`"velocidad_ingles": "-15%"` por `"-5%"`.

## 7. Siguientes pasos (en orden de impacto)

1. **Latencia de verdad: streaming por frases.** Hoy el flujo es: IA completa -> TTS completo -> enviar ->
   reproducir. Mejor: pedir a Ollama con `stream: true`, cortar por oración, sintetizar y enviar cada oración
   apenas esté (el cliente ya reproduce trozos). La primera frase sonaría en ~1-2 s.
   Medir antes: agregar tiempos en el log (IA, TTS, Whisper) para ver dónde se va el tiempo.
2. Probar que "hi" y otras palabras cortas ya se detectan. Si no: bajar más `umbral_voz`, o probar
   `whisper_model: "medium"`.
3. Ajustar la personalidad según cómo suene (prompts.py + `velocidad_espanol`/`tono_espanol`). Otras voces
   colombianas: `es-CO-GonzaloNeural`. Voces multilingües más expresivas: `es-ES-XimenaMultilingualNeural`.
4. Construir el instalador de la laptop: `packaging\construir_instalador_mama.ps1` (necesita Inno Setup:
   `winget install JRSoftware.InnoSetup`). Nunca se ha probado en Windows. Antes de dárselo a mamá:
   borrar `datos\` y la carpeta `Inglés Katerin` del vault (datos de prueba).
5. Opcional: `instalar_autoarranque_servidor.ps1` para que el servidor arranque con Windows.
6. Opcional: arreglar el mismo bug del `.bat` en el Copiloto (con permiso de Deivid).

## 8. Cosas a tener en cuenta

- Qt: no poner fuentes en el QSS (pisa el tracking negativo). Las fuentes van con `tema.fuente()`.
  Las píldoras necesitan altura fija (`ALTURA_PILDORA`) porque Qt ignora radios mayores a la mitad de la altura.
- Ollama: `qwen3.5:9b` con `think: False`. Si la profe y el Copiloto se usan a la vez, comparten el modelo.
- El prompt de Claude (si algún día se usa `anthropic`) usa `claude-opus-5-5` con thinking adaptativo
  y `fallbacks: "default"`.
- Pruebas: `pip install -r requirements-dev.txt` y `pytest`. Las capturas de la UI se pueden generar con
  `QT_QPA_PLATFORM=offscreen`.
