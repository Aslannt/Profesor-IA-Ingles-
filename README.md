# Profesora de Inglés con IA 👩🏽‍🏫

Una profesora de inglés **hablada** para Katerin: empieza desde **nivel cero**, explica en **español**,
se enfoca en la **pronunciación** y deja un **resumen** de cada clase. Deivid sigue el progreso en **Obsidian**.

Funciona igual que el [Copiloto de Reuniones](https://github.com/Aslannt/copiloto-reuniones): el **PC de Deivid**
(RTX 3060) hace todo el trabajo pesado, y la **laptop de mamá** solo tiene una app liviana que graba, envía y
reproduce.

```
 Laptop de mamá (app de escritorio)                 PC de Deivid (servidor, RTX 3060)
 ┌──────────────────────────────┐   WebSocket      ┌─────────────────────────────────────────┐
 │ 🎤 graba su frase            │ ── audio ──────▶ │ Whisper (GPU): qué dijo, en ES o en EN  │
 │   (detecta cuándo terminó)   │                  │ Calificación de pronunciación           │
 │ 🔊 reproduce a la profesora  │ ◀── voz ──────── │ Ollama qwen3.5:9b (el mismo del Copiloto)│
 │ 🪟 chat, práctica, resúmenes │ ◀── eventos ──── │ Voz natural (Edge): colombiana + nativa │
 └──────────────────────────────┘    red de casa   │ Progreso + notas en Obsidian            │
                                                    └─────────────────────────────────────────┘
```

## Cómo es una clase

1. Katerin abre la app y toca **"Empezar la clase"**. La profe Lucía la saluda con voz.
2. Cuando la profe termina de hablar, **el micrófono se abre solo**. La app detecta cuándo terminó de
   hablar (espera pausas largas, porque quien aprende se toma su tiempo pensando).
3. Cuando debe repetir algo en inglés, la frase aparece **en grande** y puede oírla **despacio**.
4. **Whisper** en el PC escucha la pronunciación **palabra por palabra** (verde = bien, amarillo = casi,
   rojo = falta) y la profe le explica qué hacer con la lengua, los labios o el aire.
5. **"Terminar clase"** genera el resumen: palabras nuevas con su pronunciación, logros y tarea.
   La próxima clase, la profe **recuerda** lo que aprendió y lo que le cuesta.

Si se cae el wifi a mitad de clase, la app se reconecta sola y **retoma donde iba**. Si el PC cambia de IP,
la app lo vuelve a encontrar en la red.

## Seguimiento en Obsidian

En tu vault (el mismo del Copiloto), carpeta `Inglés Katerin/`:

- **`Progreso de Katerin.md`**: clases, palabras, unidad actual (1–15), **gráfica de pronunciación por clase**,
  lo que más le cuesta y el plan de la profesora para la próxima clase.
- **`Vocabulario.md`**: todas las palabras aprendidas, con su pronunciación.
- **`Clases/2026-09-29 - Clase 001 - Saludos.md`**: resumen, cada práctica con su puntaje y lo que se oyó,
  tarea (como checkbox) y la transcripción completa (plegada).

Las notas tienen *frontmatter* (`clase`, `unidad`, `pronunciacion`, `tags: [ingles-katerin]`), así que sirven
con Dataview. Se regeneran en cada clase: mejor no editarlas a mano.

## Instalación

### 1. En el PC (una sola vez)

1. Doble clic en **`Instalar Servidor.bat`**. Crea el entorno de Python (3.11 a 3.14), instala todo, descarga
   `qwen3.5:9b` en Ollama (si ya lo tienes por el Copiloto no descarga nada) y abre el firewall **solo para
   la red privada** (pide permiso de administrador).
2. Revisa **`config/servidor.local.json`**, sobre todo `obsidian_vault_path` (ya trae la ruta del Copiloto).
3. Abre **`Iniciar Profesora (servidor).bat`** y deja la ventana abierta. La primera vez descarga el modelo de Whisper (~500 MB).
4. Opcional: `instalar_autoarranque_servidor.ps1` para que arranque solo al iniciar Windows, como el Copiloto.

Para probar la app en el mismo PC antes de pasarla a la laptop: `Abrir App (probar en este PC).bat`.

### 2. El instalador para la laptop

En el PC, en PowerShell:

```powershell
.\packaging\construir_instalador_mama.ps1
```

Toma la IP del PC y la mete **dentro** del instalador (igual que
`build_mom_client.ps1` del Copiloto). Resultado: `dist\ProfesoraDeIngles-setup.exe`. Pásalo a la laptop y
ábrelo: no pide permisos de administrador ni hay que configurar nada.
Necesita [Inno Setup](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`).

> Consejo: reserva la IP del PC en el router (DHCP) para que no cambie. Si cambia, la app la vuelve a buscar
> sola, pero así es más rápido.

## Puertos

| Puerto | Uso |
|---|---|
| 8770/TCP | Conexión de la app (el Copiloto usa 8765) |
| 8771/UDP | Descubrimiento del PC en la red (el Copiloto usa 8766) |

## Configuración del servidor (`config/servidor.local.json`)

| Campo | Qué hace |
|---|---|
| `nombre_alumna`, `nombre_profesora` | Nombres |
| `contexto_alumna` | Algo de su vida para que los ejemplos le sirvan (p. ej. sus reuniones de trabajo en inglés) |
| `proveedor_ia` | `ollama` (local, gratis) o `anthropic` (Claude: enseña mejor, cuesta ~USD 0,20–0,60 por clase; necesita `anthropic_api_key`) |
| `ollama_model` | `qwen3.5:9b`, el mismo del Copiloto, para que no se peleen la memoria de la GPU |
| `whisper_model` | `small` (recomendado) o `medium` (entiende mejor los acentos, un poco más lento) |
| `motor_voz` | `edge` (voces neuronales, muy naturales, necesita internet en el PC) o `kokoro` (100% local, instalar aparte) |
| `voz_espanol`, `voz_ingles` | `es-CO-SalomeNeural` (colombiana) y `en-US-JennyNeural` |
| `obsidian_vault_path`, `obsidian_carpeta` | Dónde escribir las notas. Vacío = sin Obsidian |

La app de la laptop tiene su propia configuración en `%LOCALAPPDATA%\ProfesoraDeIngles\config\cliente.json`
(sensibilidad del micrófono, tamaño de letra, etc.).

## Problemas comunes

- **"No me puedo conectar con la profesora"**: el PC está apagado, o el servidor no está corriendo, o el wifi
  quedó como red **Pública** en Windows (el firewall la bloquea; `abrir_firewall.ps1` ofrece cambiarla).
- **No detecta cuándo termina de hablar / la corta muy pronto**: en `cliente.json` ajusta `umbral_voz`
  (más bajo = más sensible) y `silencio_fin_segundos`.
- **La profe no tiene voz**: la voz `edge` necesita internet en el PC. El texto igual se ve en pantalla.
- **Clase y reunión al mismo tiempo**: comparten `qwen3.5:9b`, así que Ollama no tiene que cambiar de modelo.
- Registros: `logs/servidor.log` en el PC y `%LOCALAPPDATA%\ProfesoraDeIngles\logs\cliente.log` en la laptop.

## Diseño

La app sigue la guía de estilo tipo Apple (`profesora/cliente/tema.py` tiene todos los tokens):
un solo color de acción (azul `#0066cc`: todo lo que se toca es azul), superficies que alternan
blanco / parchment / casi negro en vez de bordes y sombras, píldoras para las acciones, y la tipografía
Inter Display + Inter (el reemplazo libre de SF Pro; incluida en `assets/fuentes`, licencia OFL).
La única excepción es el verde/ámbar/rojo de la calificación de pronunciación.
Para agrandar todo (letra, botones, espacios) sube `tamano_letra` en `cliente.json` (17 = tamaño de la guía).

## Estructura

```
profesora/servidor.py        servidor WebSocket: una clase por conexión
profesora/transcriptor.py    Whisper (mismo manejo de CUDA que el Copiloto)
profesora/pronunciacion.py   calificación palabra por palabra
profesora/ia.py              Ollama o Claude
profesora/voz.py             texto → voz (Edge/Kokoro), separando español e inglés
profesora/prompts.py         personalidad y método de la profesora + formato del resumen
profesora/curriculo.py       plan de 15 unidades desde nivel 0
profesora/almacen.py         progreso y clases (fuente de verdad, en datos/)
profesora/obsidian.py        notas en el vault
profesora/protocolo.py       formato de los mensajes
profesora/descubrimiento.py  encontrar el PC en la red (UDP)
profesora/cliente/           app de la laptop: motor.py (red, micrófono, parlante), ventana.py (PySide6), tema.py (diseño)
assets/                      fuentes Inter (OFL) e íconos Feather (MIT)
packaging/                   PyInstaller + Inno Setup
tests/                       pruebas (incluida una clase completa servidor↔cliente)
```

Pruebas: `pip install -r requirements-dev.txt` y luego `pytest`.
