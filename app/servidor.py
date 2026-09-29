"""Servidor web local: sirve la página de la clase y conecta con la IA y la voz."""
import logging
import webbrowser
from threading import Timer

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import almacen, config, ia, prompts, voz
from .curriculo import UNIDADES, unidad

log = logging.getLogger("profesor")
app = FastAPI(title="Profesora de Inglés")
CARPETA_WEB = config.RAIZ / "static"
MAX_MENSAJES = 40  # historial que se le envía a la IA en cada turno


class Mensaje(BaseModel):
    role: str
    content: str


class Historial(BaseModel):
    historial: list[Mensaje] = []


class PedidoVoz(BaseModel):
    texto: str
    despacio: bool = False


def _mensajes_para_ia(historial: list[Mensaje]) -> list[dict]:
    """[inicio de clase] + historial (que empieza con la profesora), recortado si es muy largo."""
    mensajes = [{"role": m.role, "content": m.content} for m in historial if m.role in ("user", "assistant")]
    if len(mensajes) > MAX_MENSAJES:
        mensajes = mensajes[-MAX_MENSAJES:]
        while mensajes and mensajes[0]["role"] != "assistant":
            mensajes.pop(0)
    return [{"role": "user", "content": prompts.inicio_clase()}] + mensajes


@app.get("/api/estado")
def estado():
    progreso = almacen.cargar_progreso()
    return {
        "alumna": config.NOMBRE_ALUMNA,
        "profesora": config.NOMBRE_PROFESORA,
        "clase_numero": progreso["clases_completadas"] + 1,
        "unidad_numero": progreso["unidad_actual"] + 1,
        "unidad_titulo": unidad(progreso["unidad_actual"])["titulo"],
        "total_unidades": len(UNIDADES),
        "palabras_aprendidas": len(progreso["palabras_aprendidas"]),
        "motor_voz": config.MOTOR_VOZ,
    }


@app.post("/api/hablar")
def hablar(pedido: Historial):
    if pedido.historial and pedido.historial[-1].role != "user":
        raise HTTPException(400, "El último mensaje debe ser de la alumna.")
    sistema = prompts.sistema_clase(almacen.cargar_progreso())
    try:
        return {"respuesta": ia.responder(sistema, _mensajes_para_ia(pedido.historial))}
    except ia.ErrorIA as e:
        raise HTTPException(503, str(e)) from e


@app.post("/api/terminar")
def terminar(pedido: Historial):
    transcripcion = [m.model_dump() for m in pedido.historial]
    if sum(1 for m in transcripcion if m["role"] == "user") < 2:
        raise HTTPException(400, "La clase fue muy corta para hacer un resumen.")
    sistema, usuario = prompts.pedido_resumen(almacen.cargar_progreso(), transcripcion)
    try:
        resumen = ia.responder_json(sistema, usuario, prompts.ESQUEMA_RESUMEN)
    except ia.ErrorIA as e:
        raise HTTPException(503, str(e)) from e
    return almacen.guardar_clase(resumen, transcripcion)


@app.post("/api/voz")
async def hablar_en_voz(pedido: PedidoVoz):
    try:
        resultado = await voz.sintetizar(pedido.texto, pedido.despacio)
    except Exception as e:  # sin internet, voz no instalada, etc. -> el navegador usa su propia voz
        log.warning("No se pudo generar la voz (%s). Se usará la voz del navegador.", e)
        raise HTTPException(503, "voz no disponible") from e
    if resultado is None:
        return Response(status_code=204)
    audio, tipo = resultado
    return Response(content=audio, media_type=tipo)


@app.get("/api/clases")
def clases():
    return almacen.listar_clases()


@app.get("/api/clases/{id_clase}")
def clase(id_clase: str):
    registro = almacen.leer_clase(id_clase)
    if not registro:
        raise HTTPException(404, "No existe esa clase")
    return registro


@app.get("/api/progreso")
def progreso():
    return almacen.cargar_progreso()


@app.get("/")
def inicio():
    return FileResponse(CARPETA_WEB / "index.html")


app.mount("/", StaticFiles(directory=CARPETA_WEB), name="web")


def main():
    import uvicorn

    url = f"http://localhost:{config.PUERTO}"
    print(f"\n  Profesora {config.NOMBRE_PROFESORA} lista en {url}\n  (Para cerrar, cierra esta ventana)\n")
    Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=config.PUERTO, log_level="warning")


if __name__ == "__main__":
    main()
