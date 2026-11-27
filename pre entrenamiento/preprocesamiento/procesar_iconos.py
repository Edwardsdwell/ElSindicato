r"""Quita fondos a los vehículos fuente y exporta PNG transparentes uniformes.

Para la primera corrida: pip install "rembg[cpu]". El modelo de segmentación se
descarga la primera vez y queda en la caché de rembg para las siguientes.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy.ndimage import label
from rembg import new_session, remove

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "Apartado multimedia" / "assets" / "vehiculos" / "originales"
OUTPUT = ROOT / "Apartado multimedia" / "sprites" / "vehicles"
MODEL_CACHE = ROOT / ".cache" / "rembg"
OUTPUT_SIZE = (192, 128)
FILES = {
    "mini1": "mini1.jpg",
    "mini2": "mini2.jpg",
    "mini3": "mini3.jpg",
    "mini4": "mini4.jpg",
    # El archivo se llama mini6, pero ocupa la quinta ficha de la simulación.
    "mini5": "mini6.jpg",
    "transito": "transito.jpg",
}


def process(source: Path, destination: Path, session) -> dict:
    original = Image.open(source).convert("RGB")
    result = remove(original, session=session, alpha_matting=False)
    cutout = result.convert("RGBA") if isinstance(result, Image.Image) else Image.open(io.BytesIO(result)).convert("RGBA")
    alpha = cutout.getchannel("A")
    # Recorta residuos totalmente transparentes y deja aire alrededor del vehículo.
    bbox = alpha.point(lambda value: 255 if value > 10 else 0).getbbox()
    if bbox is None:
        raise RuntimeError(f"No se detectó el vehículo en {source.name}")
    crop = cutout.crop(bbox)
    margin = max(2, round(max(crop.size) * 0.035))
    crop = ImageOps.expand(crop, border=margin, fill=(0, 0, 0, 0))

    # Conserva la perspectiva y el contorno: solo reduce, centra y normaliza el lienzo.
    scale = min((OUTPUT_SIZE[0] - 8) / crop.width, (OUTPUT_SIZE[1] - 8) / crop.height)
    fitted = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(fitted, ((OUTPUT_SIZE[0] - fitted.width) // 2,
                                    (OUTPUT_SIZE[1] - fitted.height) // 2))
    # Elimina motas aisladas de segmentación, conservando el componente del vehículo.
    alpha = np.asarray(canvas.getchannel("A"))
    labels, _ = label(alpha > 24)
    sizes = np.bincount(labels.ravel())
    largest = int(sizes[1:].max()) if len(sizes) > 1 else 0
    keep = sizes >= max(20, int(largest * 0.002))
    clean_alpha = np.where(keep[labels], alpha, 0).astype("uint8")
    canvas.putalpha(Image.fromarray(clean_alpha, mode="L"))
    if destination.stem == "mini4":
        # Quita el neumático suelto del primer plano de la foto mini4.
        cut = Image.new("L", OUTPUT_SIZE, 0)
        ImageDraw.Draw(cut).polygon([(148, 104), (191, 100), (191, 127), (145, 127)], fill=255)
        current_alpha=np.asarray(canvas.getchannel("A"), dtype="uint16")
        cut_alpha=np.asarray(cut, dtype="uint16")
        canvas.putalpha(Image.fromarray((current_alpha*(255-cut_alpha)//255).astype("uint8"), "L"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG", optimize=True)
    return {"source": source.name, "output": destination.name,
            "source_size": list(original.size), "canvas_size": list(OUTPUT_SIZE),
            "transparent_pixels": int(np.count_nonzero(np.asarray(canvas.getchannel("A")) == 0))}


if __name__ == "__main__":
    os.environ.setdefault("U2NET_HOME", str(MODEL_CACHE))
    MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    print("Cargando modelo de segmentacion ISNet...")
    model = new_session("isnet-general-use", providers=["CPUExecutionProvider"])
    manifest = {"model": "isnet-general-use", "format": "PNG RGBA",
                "icons": []}
    for name, filename in FILES.items():
        src, dst = SOURCE / filename, OUTPUT / f"{name}.png"
        if not src.exists():
            raise FileNotFoundError(f"No se encontró {src}")
        print(f"Recortando {filename} -> {dst.name}...")
        manifest["icons"].append({"id": name, **process(src, dst, model)})
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Listo: {len(FILES)} PNG transparentes en {OUTPUT}")

