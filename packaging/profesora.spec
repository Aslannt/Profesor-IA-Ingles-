# PyInstaller: app de la laptop (solo cliente). Basado en copiloto.spec del Copiloto de Reuniones.
#
#   pyinstaller packaging/profesora.spec --noconfirm
#
# Lo pesado (Whisper, la IA, la voz) vive en el PC servidor, así que aquí no se empaqueta.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

PROJECT = Path(SPECPATH).parent

datas = [(str(PROJECT / "assets"), "assets")]  # fuentes Inter e íconos
cliente_json = PROJECT / "config" / "cliente.json"  # lo pone construir_instalador_mama.ps1
if cliente_json.exists():
    datas.append((str(cliente_json), "config"))
binaries = []
hiddenimports = []

# SoundCard llega al audio de Windows por cffi y trae archivos de datos.
c_datas, c_binaries, c_hidden = collect_all("soundcard")
datas += c_datas
binaries += c_binaries
hiddenimports += c_hidden

excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras", "PySide6.Qt3DAnimation",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtQuick", "PySide6.QtQuick3D",
    "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtBluetooth",
    "PySide6.QtPositioning", "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtOpenGL",
    "tkinter", "matplotlib", "scipy", "pandas", "IPython", "notebook", "pytest",
    # Solo del servidor:
    "faster_whisper", "ctranslate2", "av", "edge_tts", "anthropic", "httpx", "torch", "onnxruntime", "kokoro",
]

a = Analysis(
    [str(PROJECT / "packaging" / "entry.py")],
    pathex=[str(PROJECT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ProfesoraDeIngles", console=False,
          icon=None, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ProfesoraDeIngles")
