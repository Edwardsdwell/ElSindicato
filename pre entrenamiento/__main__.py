"""Punto de entrada: python \"pre entrenamiento\"."""
import argparse

from preentrenamiento import preentrenar


def main() -> None:
    parser = argparse.ArgumentParser(description="Preentrenar minis y Tránsito.")
    parser.add_argument("--dias-minis", type=int, default=6000)
    parser.add_argument("--dias-transito", type=int, default=2000)
    parser.add_argument("--semilla", type=int, default=0)
    args = parser.parse_args()
    preentrenar(args.dias_minis, args.dias_transito, args.semilla)


if __name__ == "__main__":
    main()
