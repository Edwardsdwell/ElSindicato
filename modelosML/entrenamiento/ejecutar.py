"""Punto de entrada para continuar el aprendizaje y generar reportes."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "juego" / "src"))
from dies_irae.pipeline import entrenar


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrenar las políticas preentrenadas.")
    parser.add_argument("--dias", type=int, default=1826)
    parser.add_argument("--semilla", type=int, default=7)
    args = parser.parse_args()
    entrenar(args.dias, args.semilla)


if __name__ == "__main__":
    main()

