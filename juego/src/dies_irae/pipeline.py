"""Operaciones por etapas para preparar y entrenar políticas."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from . import analisis, config as C
from .entorno import Simulacion

ROOT = Path(__file__).resolve().parents[3]
MODELS = Path(os.environ.get("MODELOS_DIR", str(ROOT / "modelosML" / "preentrenados")))


def guardar_modelos(sim: Simulacion, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    for mini in sim.minis:
        mini.cerebro.guardar(str(destino / f"mini{mini.idx + 1}.npy"))
    sim.transito.cerebro.guardar(str(destino / "transito.npy"))


def cargar_modelos() -> tuple[list[np.ndarray], np.ndarray]:
    minis = [np.load(MODELS / f"mini{i + 1}.npy", allow_pickle=False) for i in range(len(C.PERFILES))]
    transito = np.load(MODELS / "transito.npy", allow_pickle=False)
    return minis, transito


def entrenar(dias: int = C.TOTAL_DIAS, semilla: int = 0) -> Simulacion:
    """Continúa el aprendizaje de las políticas en una corrida de entrenamiento."""
    q_minis, q_transito = cargar_modelos()
    print(f"[Entrenamiento] {dias} días · aprendizaje activo (ε=0.05)")
    sim = Simulacion(
        semilla=semilla,
        modo="simulacion",
        Q_minis=q_minis,
        Q_transito=q_transito,
        eps_minis=0.05,
        eps_transito=0.05,
    )
    sim.correr(dias)

    salida = ROOT / "outputs" / "entrenamiento"
    guardar_modelos(sim, salida / "modelos_finales")
    analisis.reporte(sim, str(salida))
    print(f"Resultados de entrenamiento guardados en {salida}")
    return sim


