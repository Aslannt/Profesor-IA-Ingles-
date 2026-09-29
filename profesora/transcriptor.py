"""Oído de la profesora: faster-whisper en la GPU del PC (mismo manejo de CUDA que el Copiloto).

A diferencia del Copiloto (solo inglés), aquí se usa un modelo multilingüe y se le dice el idioma
en cada frase: español en la conversación, inglés cuando la alumna practica pronunciación. En la
práctica también se piden las palabras con su probabilidad, para calificar la pronunciación.
"""
from __future__ import annotations

from dataclasses import dataclass

import ctypes
import importlib.util
import os
import threading
from typing import Any

import numpy as np


class TranscriberError(RuntimeError):
    pass


# ctranslate2's CUDA backend needs these specific DLLs at the moment it
# actually runs the encoder - not merely a CUDA-capable device being
# present (see _cuda_is_available below, and the module docstring-length
# comment on why this distinction matters). Listed newest-first; only the
# 12.x name has actually been seen needed by this project's ctranslate2
# build, 11.x is kept as a defensive fallback for an older CUDA toolkit.
_CUDA_RUNTIME_DLL_NAMES = ("cublas64_12.dll", "cublas64_11.dll")

_cuda_path_prepared = False


def _ensure_cuda_runtime_on_path() -> None:
    """The nvidia-cublas-cu12 / nvidia-cudnn-cu12 pip packages ship the
    actual DLLs ctranslate2's CUDA path needs, but installing them does NOT
    put them on Windows' DLL search path by itself - and neither PATH nor
    os.add_dll_directory() alone is enough to cover both loaders actually
    involved:
      - ctranslate2's own native (C++) LoadLibraryW call, which honors the
        process's PATH environment variable;
      - ctypes.CDLL() (used below to verify this actually worked, and by
        any other Python-level loader) - Python 3.8+ deliberately stopped
        using PATH for this on Windows for security, so it needs
        os.add_dll_directory() specifically instead.
    Do both, or the two loaders disagree with each other."""
    global _cuda_path_prepared
    if _cuda_path_prepared:
        return
    _cuda_path_prepared = True
    dirs = []
    for pkg in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(pkg)
        except (ImportError, ValueError):
            continue
        if not spec or not spec.submodule_search_locations:
            continue
        for location in spec.submodule_search_locations:
            bin_dir = os.path.join(location, "bin")
            if os.path.isdir(bin_dir):
                dirs.append(bin_dir)
    for bin_dir in dirs:
        try:
            os.add_dll_directory(bin_dir)
        except (OSError, AttributeError):
            pass  # AttributeError: not on Windows; OSError: already added/invalid
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")


def _cuda_runtime_is_loadable() -> bool:
    _ensure_cuda_runtime_on_path()
    for name in _CUDA_RUNTIME_DLL_NAMES:
        try:
            ctypes.CDLL(name)
            return True
        except OSError:
            continue
    return False


def _cuda_is_available() -> bool:
    """True only when a CUDA transcription actually stands a chance of
    working - not just when an NVIDIA GPU is technically present. Those are
    different things: this machine's GPU was detected fine by
    ctranslate2.get_cuda_device_count() while still lacking the cuBLAS
    library the encoder needs, and a version that only checked device
    presence shipped "auto" -> "cuda" anyway - which then crashed the very
    first real transcription during a live test with the user watching
    (2026-09-07). Never repeat that: verify the thing that's actually about
    to be used, not a proxy for it."""
    try:
        import ctranslate2
    except ImportError:
        return False
    try:
        if ctranslate2.get_cuda_device_count() <= 0:
            return False
    except Exception:
        return False
    return _cuda_runtime_is_loadable()


def resolve_device(device: str) -> str:
    """"auto" (the default) picks CUDA when it's actually usable at the
    moment this runs, CPU otherwise - so the same setting works unmodified
    whether this is a laptop with no GPU or a desktop with one, instead of
    a device string baked in at config-write time that would error outright
    on hardware that doesn't match it."""
    if device != "auto":
        return device
    return "cuda" if _cuda_is_available() else "cpu"


def resolve_compute_type(compute_type: str, resolved_device: str) -> str:
    """"auto" picks the precision that actually makes sense for the device
    it ended up on: float16 is fast and accurate on a CUDA GPU, but not a
    valid/fast choice on CPU, where int8 is the efficient option."""
    if compute_type != "auto":
        return compute_type
    return "float16" if resolved_device == "cuda" else "int8"


@dataclass(slots=True)
class Palabra:
    texto: str
    probabilidad: float


@dataclass(slots=True)
class Transcripcion:
    texto: str
    palabras: list[Palabra]


class Transcriptor:
    # Mismos filtros anti-alucinación que el Copiloto.
    NO_SPEECH_PROB_LIMIT = 0.6
    COMPRESSION_RATIO_LIMIT = 2.4

    def __init__(self, modelo: str = "small", device: str = "auto", compute_type: str = "auto") -> None:
        self.modelo = modelo
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None
        self._lock = threading.Lock()

    def load(self) -> None:
        if self._model is not None:
            return
        device = resolve_device(self.device)
        compute_type = resolve_compute_type(self.compute_type, device)
        if device == "cuda":
            _ensure_cuda_runtime_on_path()
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriberError("faster-whisper no está instalado.") from exc
        self._model = WhisperModel(self.modelo, device=device, compute_type=compute_type, cpu_threads=0, num_workers=1)

    def transcribir(self, audio_16k: np.ndarray, idioma: str) -> Transcripcion:
        # Ojo: a propósito NO se le da a Whisper la frase esperada como pista (initial_prompt):
        # lo empujaría a "oír" la frase correcta aunque la pronunciación no lo fuera.
        self.load()
        audio = np.asarray(audio_16k, dtype=np.float32).reshape(-1)
        if len(audio) == 0:
            return Transcripcion("", [])
        with self._lock:
            segmentos, _ = self._model.transcribe(
                audio,
                language=idioma,
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
                word_timestamps=True,
                temperature=0.0,
            )
            textos, palabras = [], []
            for s in segmentos:
                if not s.text.strip():
                    continue
                if s.no_speech_prob > self.NO_SPEECH_PROB_LIMIT or s.compression_ratio > self.COMPRESSION_RATIO_LIMIT:
                    continue
                textos.append(s.text.strip())
                palabras += [Palabra(w.word.strip(), float(w.probability)) for w in (s.words or []) if w.word.strip()]
        return Transcripcion(" ".join(" ".join(textos).split()), palabras)
