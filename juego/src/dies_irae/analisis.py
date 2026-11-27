"""Bitácoras, estadísticas, clustering no supervisado (k-means propio) y gráficos."""
import os, csv, json
import numpy as np
from . import config as C

def kmeans(X, k, semilla=0, iteraciones=100):
    rng = np.random.default_rng(semilla); centros = X[rng.choice(len(X), k, replace=False)]
    for _ in range(iteraciones):
        etiquetas = np.argmin(((X[:, None] - centros[None]) ** 2).sum(-1), 1)
        nuevos = np.array([X[etiquetas == j].mean(0) if (etiquetas == j).any() else centros[j] for j in range(k)])
        if np.allclose(nuevos, centros): break
        centros = nuevos
    return etiquetas, centros
def caracteristicas(sim):
    """Rasgos de comportamiento de cada minibusero a partir de su bitácora."""
    tipos = ["egoista", "altruista", "filosofica", "criminal"]; filas, nombres = [], []
    for m in sim.minis:
        reg = m.bitacora; n = max(1, len(reg)); dias = max(1, (m.dia_fin or sim.dia))
        reparto = [sum(1 for r in reg if r[3] == t) / n for t in tipos]
        filas.append(reparto + [m.agresividad, m.ingreso / dias, m.accidentes / dias * 365, m.arrestos, m.eventos / dias * 365, m.estres])
        nombres.append(m.nombre)
    return (np.array(filas), ["%egoísta", "%altruista", "%filosófica", "%criminal", "agresividad",
                              "ingreso/día", "accidentes/año", "arrestos", "eventos/año", "estrés"], nombres)
def reporte(sim, salida):
    os.makedirs(salida, exist_ok=True); res = sim.resultado(); lineas = []
    cab = ["dia", "tick", "accion", "tipo", "pasajeros", "ingreso", "buscado", "combustible", "integridad", "evento", "recompensa", "peatones_cerca", "trafico"]
    todas = []
    for m in sim.minis:
        with open(f"{salida}/bitacora_mini{m.idx + 1}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(cab); w.writerows(m.bitacora)
        todas += [(m.idx + 1,) + r for r in m.bitacora]
    with open(f"{salida}/bitacora_transito.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["dia", "tick", "accion", "objetivo", "recompensa", "arresto"]); w.writerows(sim.transito.bitacora)
    with open(f"{salida}/bitacora_global.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["mini"] + cab); w.writerows(todas)
    with open(f"{salida}/diario_global.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sim.diario[0].keys())); w.writeheader(); w.writerows(sim.diario)

    lineas += ["# Reporte final — Sindicato de Transporte 11 de Septiembre", "",
               f"**Final:** {res['final']}",
               f"**Reputación final del sindicato:** {res['rep']:.2f}/5  ·  **Faltas acumuladas:** {res['faltas']}",
               f"**Cuotas recaudadas:** {res['cuotas_recaudadas']:.0f} Bs  ·  meta colectiva {'cumplida' if res['meta_cumplida'] else 'NO cumplida'}",
               f"**Tránsito apareció en el día:** {res['dia_transito']}  ·  arrestos: {sim.transito.arrestos}", "",
               "## Minibuseros", "",
               "| Mini | Conductor | Personalidad | Estado | Cumpl. metas | Suerte | Ingreso total | Arrestos | Accidentes | Incidentes peatonales |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for m in sim.minis:
        est = m.estado + (f" (día {m.dia_fin}: {m.motivo_fin})" if m.dia_fin is not None else "")
        lineas.append(f"| {m.idx + 1} | {m.nombre} | {m.personalidad} | {est} | {res['puntajes'][m.idx]:.2f} | "
                      f"{res['suerte'][m.idx]:.2f} | {m.ingreso:.0f} | {m.arrestos} | {m.accidentes} | {m.incidentes_peaton} |")
    for i in (res["ganadores"] or []):
        m = sim.minis[i]; top = np.argsort(-m.conteo)[:5]
        lineas += ["", f"### Perfil del ganador: {m.nombre}",
                   f"- {m.perfil['modelo']} · {m.personalidad} · {m.perfil['tipo_familia']} (gasto {m.familia} Bs/día)",
                   "- Decisiones más frecuentes: " + ", ".join(f"{C.ACCIONES[j].nombre} ({int(m.conteo[j])})" for j in top if m.conteo[j] > 0)]
    # --- efecto de Tránsito: antes vs después
    d = sim.diario; td = res["dia_transito"]
    if td is not None and 0 < td < len(d):
        antes, despues = d[:td], d[td:]
        tasa = lambda x, k: (x[-1][k] - x[0][k]) / max(1, len(x) - 1)
        prom = lambda x, k: np.mean([r[k] for r in x])
        lineas += ["", "## Efecto de Tránsito", "", "| Métrica | Antes | Después |", "|---|---|---|",
                   f"| Crímenes/día | {tasa(antes, 'crimenes'):.2f} | {tasa(despues, 'crimenes'):.2f} |",
                   f"| Accidentes/día | {tasa(antes, 'accidentes'):.2f} | {tasa(despues, 'accidentes'):.2f} |",
                   f"| Δ reputación/día | {tasa(antes, 'rep'):+.4f} | {tasa(despues, 'rep'):+.4f} |",
                   f"| Ingreso diario total | {prom(antes, 'ingreso'):.0f} | {prom(despues, 'ingreso'):.0f} |"]
    # --- clustering no supervisado
    X, nombres_rasgos, nombres = caracteristicas(sim); Z = (X - X.mean(0)) / (X.std(0) + 1e-9)
    k = min(3, len(X)); etiquetas, centros = kmeans(Z, k)
    lineas += ["", f"## Clustering no supervisado (k-means, k={k})", ""]
    for j in range(k):
        miembros = [nombres[i] for i in range(len(nombres)) if etiquetas[i] == j]
        if not miembros: continue
        altos = np.argsort(-centros[j])[:2]
        lineas.append(f"- **Grupo {j + 1}**: {', '.join(miembros)} — rasgos altos: {', '.join(nombres_rasgos[h] for h in altos)}")
    open(f"{salida}/reporte.md", "w", encoding="utf-8").write("\n".join(lineas))
    json.dump(dict(resultado=res, clusters=etiquetas.tolist(), rasgos=nombres_rasgos),
              open(f"{salida}/resultado.json", "w", encoding="utf-8"), indent=1, default=float, ensure_ascii=False)
    print("\n".join(lineas)); _graficos(sim, salida, Z, etiquetas)
def _graficos(sim, salida, Z, etiquetas):
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib no instalado: se omiten los gráficos)"); return
    d = sim.diario; x = [r["dia"] for r in d]
    fig, ax = plt.subplots(2, 2, figsize=(13, 8))
    ax[0, 0].plot(x, [r["rep"] for r in d]); ax[0, 0].axhline(C.REP_MIN_REQ, ls="--", c="g"); ax[0, 0].axhline(C.REP_ATROZ, ls="--", c="r")
    if sim.transito.dia_activacion: ax[0, 0].axvline(sim.transito.dia_activacion, c="k", ls=":")
    ax[0, 0].set_title("Reputación del sindicato (línea negra = aparece Tránsito)")
    ax[0, 1].plot(x, [r["activos"] for r in d]); ax[0, 1].set_title("Minibuseros activos")
    ax[1, 0].plot(x, [r["crimenes"] for r in d], label="crímenes acum."); ax[1, 0].plot(x, [r["accidentes"] for r in d], label="accidentes acum.")
    ax[1, 0].plot(x, [r["arrestos"] * 10 for r in d], label="arrestos ×10"); ax[1, 0].legend(); ax[1, 0].set_title("Faltas y arrestos")
    u, s, vt = np.linalg.svd(Z - Z.mean(0), full_matrices=False); P = (Z - Z.mean(0)) @ vt[:2].T
    ax[1, 1].scatter(P[:, 0], P[:, 1], c=etiquetas, s=140)
    for i, m in enumerate(sim.minis): ax[1, 1].annotate(f"mini{i + 1}\n{m.personalidad}", P[i], textcoords="offset points", xytext=(6, 6))
    ax[1, 1].set_title("Grupos de comportamiento (PCA)")
    plt.tight_layout(); plt.savefig(f"{salida}/panel.png", dpi=110); plt.close()
    c = sim.ciudad; from .ciudad import PARADAS
    fig, a = plt.subplots(figsize=(8, 7))
    for n, vecinos in c.vecinos.items():
        for v, _, semaforo, oculta in vecinos:
            if n < v: a.plot(*zip(c.xy[n], c.xy[v]), c="orange" if oculta else "gray", ls="--" if oculta else "-", lw=1.5)
    for n, (px, py) in c.xy.items():
        a.scatter(px, py, c="tab:blue" if n in PARADAS else "lightgray", zorder=3)
        a.annotate(n, (px, py), fontsize=7, xytext=(4, 4), textcoords="offset points")
    a.set_title("La Paz (grafo aproximado) — gris: calzada · naranja punteado: atajos ocultos"); a.set_aspect("equal")
    plt.savefig(f"{salida}/mapa.png", dpi=110); plt.close()
