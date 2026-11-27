"""Generación reproducible de las políticas iniciales de la simulación."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "juego" / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from dies_irae import config as C
from dies_irae.entorno import Simulacion
from dies_irae.pipeline import guardar_modelos

MODELS = Path(os.environ.get("MODELOS_DIR", str(ROOT / "modelosML" / "preentrenados")))


def evaluar_politicas(q_minis, q_transito, semilla: int = 99, dias: int = 365, ciudad=None) -> dict:
    """Mide las políticas sin modificar sus tablas Q."""
    evaluacion = Simulacion(
        semilla=semilla,
        modo="simulacion",
        Q_minis=q_minis,
        Q_transito=q_transito,
        aprende_minis=False,
        aprende_transito=False,
        eps_minis=0.02,
        eps_transito=0.0,
        bitacora=False,
        ciudad=ciudad,
    )
    evaluacion.correr(dias, verbose=False)
    resultado = evaluacion.resultado()
    dias_completados = max(1, evaluacion.dia)
    return {
        "dias_completados": evaluacion.dia,
        "reputacion_final": round(evaluacion.rep, 2),
        "ingreso_medio_minibus_dia": round(
            sum(mini.ingreso for mini in evaluacion.minis) / (len(evaluacion.minis) * dias_completados), 2
        ),
        "faltas_dia": round(evaluacion.faltas / dias_completados, 2),
        "accidentes_dia": round(sum(mini.accidentes for mini in evaluacion.minis) / dias_completados, 2),
        "arrestos_transito_dia": round(evaluacion.transito.arrestos / dias_completados, 2),
        "dia_activacion_transito": evaluacion.transito.dia_activacion,
        "resultado": resultado["final"],
    }


def preentrenar(dias_minis: int = 6000, dias_transito: int = 2000, semilla: int = 0) -> None:
    """Entrena SARSA para los minibuses y Q-learning para Tránsito."""
    if dias_minis < 1 or dias_transito < 1:
        raise ValueError("Los días de preentrenamiento deben ser mayores que cero.")

    print(f"[Preentrenamiento SARSA] {dias_minis} días de minibuses", flush=True)
    plan_eps = lambda k, n: max(0.05, 0.6 * (1 - k / (0.8 * n)))
    minis = Simulacion(semilla=semilla, modo="preentreno", aprende_transito=False, bitacora=False)
    minis.correr(dias_minis, plan_eps=plan_eps, verbose=False)
    q_minis = [mini.cerebro.Q for mini in minis.minis]

    print(f"[Preentrenamiento Q-learning] {dias_transito} días de Tránsito", flush=True)
    transito = Simulacion(
        semilla=semilla + 1,
        modo="preentreno_transito",
        Q_minis=q_minis,
        aprende_minis=False,
        eps_minis=0.35,
        eps_transito=0.3,
        bitacora=False,
    )
    transito.correr(dias_transito, verbose=False)
    minis.transito.cerebro.Q = transito.transito.cerebro.Q

    dias_evaluacion = 365
    print(f"[Evaluación sin aprendizaje] {dias_evaluacion} días", flush=True)
    metricas = evaluar_politicas(q_minis, transito.transito.cerebro.Q, semilla + 99, dias_evaluacion, minis.ciudad)

    MODELS.mkdir(parents=True, exist_ok=True)
    guardar_modelos(minis, MODELS)
    try:
        anterior = json.loads((MODELS / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        anterior = {}
    historial = anterior.get("historial", []) if isinstance(anterior, dict) else []
    if anterior and not historial:
        historial = [{
            "fecha": anterior.get("fecha"),
            "semilla": anterior.get("semilla"),
            "dias_minis": anterior.get("dias_minis"),
            "dias_transito": anterior.get("dias_transito"),
            "dias_evaluacion": anterior.get("dias_evaluacion"),
            "metricas": anterior.get("metricas"),
            "resultado": "registro previo; sin resumen de evaluación",
        }]
    metadata = {
        "proyecto": "Dies Irae",
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "semilla": semilla,
        "dias_minis": dias_minis,
        "dias_transito": dias_transito,
        "dias_evaluacion": dias_evaluacion,
        "epsilon": {"minis_inicial": 0.6, "minis_minimo": 0.05, "transito": 0.3},
        "epsilon_evaluacion": {"minis": 0.02, "transito": 0.0},
        "alfa": C.ALFA,
        "gamma": C.GAMMA,
        "n_estados_mini": int(minis.minis[0].cerebro.Q.shape[0]),
        "n_acciones_mini": int(minis.minis[0].cerebro.Q.shape[1]),
        "n_estados_transito": int(minis.transito.cerebro.Q.shape[0]),
        "agentes": [
            {"archivo": f"mini{i + 1}.npy", "nombre": mini.nombre,
             "personalidad": mini.personalidad, "modelo": mini.perfil["modelo"]}
            for i, mini in enumerate(minis.minis)
        ] + [{"archivo": "transito.npy", "nombre": "Tránsito", "algoritmo": "Q-learning"}],
        "acciones": [accion.nombre for accion in C.ACCIONES],
        "metricas": metricas,
        "historial": (historial + [{
            "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
            "semilla": semilla,
            "dias_minis": dias_minis,
            "dias_transito": dias_transito,
            "dias_evaluacion": dias_evaluacion,
            "metricas": metricas,
        }])[-12:],
    }
    (MODELS / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Políticas preentrenadas guardadas en {MODELS}")
