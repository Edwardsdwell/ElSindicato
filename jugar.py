"""Arranca el entorno virtual y el juego visual del Sindicato."""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
import threading
import venv
import webbrowser
from pathlib import Path
ROOT = Path(__file__).resolve().parent
APP = ROOT / "juego"
ENV_DIR = ROOT / ".venv"


def env_python() -> Path:
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return ENV_DIR / relative


def ensure_environment() -> Path:
    interpreter = env_python()
    if Path(sys.prefix).resolve() == ENV_DIR.resolve():
        return Path(sys.executable)

    if not interpreter.is_file():
        print("Creando entorno virtual .venv…", flush=True)
        venv.EnvBuilder(with_pip=True).create(ENV_DIR)

    check = subprocess.run(
        [str(interpreter), "-c", "import numpy, networkx, osmnx"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if check.returncode != 0:
        req_file = ROOT / "requirements.txt"
        if req_file.is_file():
            print("Instalando dependencias de requirements.txt…", flush=True)
            subprocess.run(
                [str(interpreter), "-m", "pip", "install", "--upgrade", "pip"],
                cwd=str(ROOT),
                check=False,
            )
            subprocess.run(
                [str(interpreter), "-m", "pip", "install", "-r", str(req_file)],
                cwd=str(ROOT),
                check=True,
            )
    return interpreter


def main() -> None:
    parser = argparse.ArgumentParser(description="Preparar el entorno e iniciar el juego visual Sindicato.")
    parser.add_argument("--modelos", help="Carpeta de políticas .npy (por defecto: modelosML/preentrenados).")
    parser.add_argument("--puerto", type=int, default=int(os.environ.get("DIES_IRAE_PORT", "8765")),
                        help="Puerto local preferido (por defecto: 8765; si está ocupado se buscan los siguientes).")
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0].strip('"\'') == str(Path(__file__).resolve()):
        raw_args = raw_args[1:]
    args = parser.parse_args(raw_args)

    interpreter = ensure_environment()
    if Path(sys.prefix).resolve() != ENV_DIR.resolve():
        command = [str(interpreter), str(Path(__file__).resolve())]
        if args.modelos:
            command.extend(["--modelos", args.modelos])
        command.extend(["--puerto", str(args.puerto)])
        os.execv(str(interpreter), command)

    if args.modelos:
        path = Path(args.modelos)
        if not path.is_absolute():
            path = ROOT / path
        os.environ["MODELOS_DIR"] = str(path.resolve())

    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))

    from sindicato.server import create_server

    server, url = create_server(args.puerto)
    browser_thread = threading.Thread(
        target=webbrowser.open, args=(url,), kwargs={"new": 2}, name="sindicato-browser", daemon=True
    )
    try:
        browser_thread.start()
        # Mantener serve_forever en el hilo principal hace que Ctrl+C llegue
        # directamente al bucle del servidor en Windows y en otros sistemas.
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nCerrando el servidor…", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
    except Exception as exc:
        print(f"\nNo se pudo iniciar el juego: {exc}", file=sys.stderr)
        if sys.stdin.isatty():
            input("\nPresiona Enter para cerrar…")
        raise SystemExit(1) from exc





