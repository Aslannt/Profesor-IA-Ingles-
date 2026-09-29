import numpy as np

from profesora import protocolo as p
from profesora.cliente.motor import DetectorFrase, remuestrear
from profesora.pronunciacion import calificar, palabras
from profesora.transcriptor import Palabra
from profesora.voz import frase_para_repetir, segmentar


def test_palabras_normaliza_contracciones_y_numeros():
    assert palabras("I'm 3, OK!") == ["i", "am", "three", "ok"]


def test_calificar():
    assert calificar("hello", "hello").puntaje == 100
    assert calificar("I am fine", "I'm fine").puntaje == 100
    r = calificar("three", "tree")
    assert r.palabras[0].nivel == "casi"  # 'tree' no es 'three': no puede contar como perfecto
    assert calificar("thank you", "").puntaje == 0
    # Reconocida pero con poca seguridad de Whisper -> "casi"
    r = calificar("hello", "hello", [Palabra("hello", 0.2)])
    assert r.palabras[0].nivel == "casi" and r.puntaje == 75


def test_segmentar_voz():
    assert segmentar("Hola [en]hello[/en]. Dilo: [repite]nice to meet you[/repite]") == [
        ("es", "Hola"), ("en", "hello"), ("es", ". Dilo:"), ("en", "nice to meet you")]
    assert frase_para_repetir("a [repite]x[/repite] b [repite]Hi there[/repite]") == "Hi there"
    assert frase_para_repetir("sin práctica") is None


def test_protocolo_ida_y_vuelta():
    assert p.leer_control(p.control(p.HABLAR_TEXTO, texto="hola")) == {"type": "control", "accion": "texto", "texto": "hola"}
    assert p.leer_control("basura") is None
    audio = np.array([0.5, -0.5, 1.2], dtype=np.float32)
    assert np.allclose(p.bytes_a_voz(p.voz_a_bytes(audio)), [0.5, -0.5, 1.0], atol=1e-3)
    assert np.allclose(p.bytes_a_audio(p.audio_a_bytes(audio)), audio)


def _bloque(nivel, frecuencia=48000, seg=0.1):
    return np.full(int(frecuencia * seg), nivel, dtype=np.float32)


def test_detector_frase_termina_tras_silencio():
    d = DetectorFrase(48000, umbral=0.012, silencio_fin=1.0, espera_maxima=10, frase_maxima=30)
    for _ in range(5):  # ruido del cuarto
        assert not d.empujar(_bloque(0.002))
    for _ in range(10):  # habla 1 s
        assert not d.empujar(_bloque(0.1))
    terminado = False
    for _ in range(12):  # silencio
        terminado = d.empujar(_bloque(0.002))
        if terminado:
            break
    assert terminado and d.audio() is not None
    assert 1.0 < len(d.audio()) / 48000 < 2.5


def test_detector_frase_se_rinde_si_no_habla():
    d = DetectorFrase(48000, umbral=0.012, silencio_fin=1.0, espera_maxima=2, frase_maxima=30)
    for _ in range(25):
        if d.empujar(_bloque(0.001)):
            break
    assert d.terminado and d.audio() is None


def test_remuestrear():
    assert len(remuestrear(np.zeros(48000, dtype=np.float32), 48000, 16000)) == 16000
