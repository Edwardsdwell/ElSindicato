"""Servidor local ligero: API estándar de Python + simulación en hilo aparte."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import osmnx as ox

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'juego'
MEDIA = ROOT / 'Apartado multimedia'
WEB = Path(__file__).resolve().parent / "web"
os.sys.path.insert(0, str(APP / "src"))
from dies_irae import config as C, analisis
from dies_irae.entorno import Simulacion
from dies_irae.ciudad import Ciudad, NODOS, PARADAS

MODELS = Path(os.environ.get("MODELOS_DIR", str(ROOT / "modelosML" / "preentrenados")))
OUT = ROOT / "outputs" / "sindicato"
GRAPH_CACHE = ROOT / ".cache" / "maps" / "la_paz_drive.graphml"


def pretraining_snapshot():
    """Resume los metadatos y las tablas que dejó el último preentrenamiento."""
    metadata_path = MODELS / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata = None

    tables = []
    names = [f"mini{i}.npy" for i in range(1, 6)] + ["transito.npy"]
    for index, name in enumerate(names):
        path = MODELS / name
        table = {"file": name, "available": path.is_file()}
        if path.is_file():
            table["bytes"] = path.stat().st_size
            try:
                values = np.load(path, allow_pickle=False, mmap_mode="r")
                table["states"], table["actions"] = map(int, values.shape)
                table["finite"] = bool(np.isfinite(values).all())
            except (OSError, ValueError):
                table["finite"] = False
        tables.append(table)

    complete = bool(metadata) and all(table["available"] and table.get("finite", False) for table in tables)
    return {
        "status": "completo" if complete else "incompleto" if metadata or any(t["available"] for t in tables) else "sin-registro",
        "metadata": metadata,
        "tables": tables,
        "available_tables": sum(table["available"] and table.get("finite", False) for table in tables),
    }


class Runner:
    def __init__(self):
        self.lock = threading.RLock()
        self.sim = None
        self.seed = 42
        self.model_hash = None
        self.code_hash = None
        self.street_hash = None
        self.error = None
        self.loading = False
        self.running = False
        self.target_days = 1826
        self.transit_mode = "automatic"
        self.difficulty = "normal"
        self.ticks_per_second = 8
        self.pending_steps = 0
        self.finished_saved = False
        self.map_cache = None
        self.history = {i: [] for i in range(1, len(C.PERFILES) + 1)}
        self.history_revision = 0
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def model_data(self):
        paths = [MODELS / f"mini{i}.npy" for i in range(1, 6)] + [MODELS / "transito.npy"]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            raise FileNotFoundError("Faltan modelos: " + ", ".join(missing))
        q = [np.load(p, allow_pickle=False) for p in paths]
        expected = [(1728, len(C.ACCIONES))] * 5 + [(72, 5)]
        for p, arr, shape in zip(paths, q, expected):
            if arr.shape != shape or not np.isfinite(arr).all():
                raise ValueError(f"Modelo inválido {p.name}: forma {arr.shape}, esperada {shape}")
        digest = hashlib.sha256()
        for p in paths:
            digest.update(p.name.encode()); digest.update(p.read_bytes())
        code_digest=hashlib.sha256()
        for source in [APP/"src"/"dies_irae"/name for name in ("config.py", "entorno.py", "ciudad.py", "aprendizaje.py", "analisis.py")] + [Path(__file__)]:
            code_digest.update(source.name.encode()); code_digest.update(source.read_bytes())
        return q[:5], q[5], digest.hexdigest(), code_digest.hexdigest()

    @staticmethod
    def hash_street_graph(graph):
        digest=hashlib.sha256()
        for node,data in sorted(graph.nodes(data=True),key=lambda row:str(row[0])):
            digest.update(f"N|{node}|{data.get('x')}|{data.get('y')}|{data.get('highway')}\n".encode())
        edges=graph.edges(keys=True,data=True) if graph.is_multigraph() else ((u,v,0,d) for u,v,d in graph.edges(data=True))
        for u,v,key,data in sorted(edges,key=lambda row:(str(row[0]),str(row[1]),str(row[2]))):
            geom=data.get("geometry")
            digest.update(f"E|{u}|{v}|{key}|{data.get('length')}|{data.get('highway')}|".encode())
            if geom is not None: digest.update(geom.wkb)
            digest.update(b"\n")
        return digest.hexdigest()

    def start(self, seed, days, transit_mode="automatic", difficulty="normal"):
        transit_mode = "automatic" if transit_mode == "automatic" else "manual"
        difficulty = difficulty if difficulty in C.DIFICULTADES else "normal"
        with self.lock:
            if self.loading:
                return
            self.loading = True; self.error = None; self.running = False
            self.sim = None; self.seed = int(seed); self.target_days = int(days)
            self.transit_mode = transit_mode
            self.difficulty = difficulty
            self.finished_saved = False; self.pending_steps = 0
            self.history = {i: [] for i in range(1, len(C.PERFILES) + 1)}
            self.history_revision = 0
        threading.Thread(target=self.initialize, args=(int(seed), transit_mode, difficulty), daemon=True).start()

    def reset(self):
        with self.lock:
            if self.loading or self.sim is None or self.finished_saved:
                return False
            seed, days, transit_mode, difficulty = self.seed, self.target_days, self.transit_mode, self.difficulty
        self.start(seed, days, transit_mode, difficulty)
        return True

    def launch_transit(self):
        with self.lock:
            if self.loading or self.sim is None:
                return {"error": "Primero despacha la simulación."}, 409
            if self.sim.terminado or self.sim.dia >= self.target_days:
                return {"error": "La simulación ya terminó."}, 409
            if self.sim.transito.activo:
                return {"error": "Tránsito ya está en ruta."}, 409
            self.sim.activar_transito()
            return self.snapshot(), 200

    def initialize(self, seed, transit_mode, difficulty="normal"):
        try:
            qm, qt, digest, code_digest = self.model_data()
            graph_file=GRAPH_CACHE
            city=None
            if graph_file.is_file():
                try: city=Ciudad(ox.io.load_graphml(graph_file))
                except Exception: city=None
            sim = Simulacion(semilla=seed, modo="simulacion", Q_minis=qm, Q_transito=qt,
                             eps_minis=.05, eps_transito=.05, ciudad=city,
                             transito_manual=(transit_mode == "manual"), dificultad=difficulty)
            if city is None:
                graph_file.parent.mkdir(parents=True,exist_ok=True)
                ox.io.save_graphml(sim.ciudad.G,graph_file)
            street_hash=self.hash_street_graph(sim.ciudad.G)
            with self.lock:
                self.sim = sim; self.model_hash = digest; self.code_hash = code_digest
                self.street_hash = street_hash
                self.map_cache = None
                self.record_history()
                self.loading = False; self.running = True
        except Exception as exc:
            with self.lock:
                self.error = f"{type(exc).__name__}: {exc}"; self.loading = False

    def loop(self):
        while True:
            with self.lock:
                sim = self.sim
                active = sim is not None and (self.running or self.pending_steps > 0)
                if active and (sim.terminado or sim.dia >= self.target_days):
                    self.running = False; self.pending_steps = 0; active = False
                    self.save_if_finished()
                if active:
                    if sim.tick_global % C.TICKS == 0:
                        sim._iniciar_dia(sim.dia % 7)
                    tick = sim.tick_global % C.TICKS
                    sim.tick(tick, sim.dia % 7)
                    if tick == C.TICKS - 1:
                        sim._terminar_dia(sim.dia % 7); sim.dia += 1
                        self.record_history()
                    if not self.running:
                        self.pending_steps = max(0, self.pending_steps - 1)
                    if sim.terminado or sim.dia >= self.target_days:
                        self.running = False; self.pending_steps = 0; self.save_if_finished()
                    delay = 1 / max(1, self.ticks_per_second)
                else:
                    delay = .04
            time.sleep(delay)

    def record_history(self):
        """Guarda una muestra de cada conductor al inicio y al cierre de cada día."""
        if not self.sim:
            return
        for mini in self.sim.minis:
            series = self.history[mini.idx + 1]
            if series and series[-1]["day"] == self.sim.dia:
                continue
            series.append({
                "day": self.sim.dia,
                "daily_income": round(float(mini.ingreso_dia), 2),
                "total_income": round(float(mini.ingreso), 2),
                "wallet": round(float(mini.billetera), 2),
                "passengers": int(mini.pasajeros),
                "laps": int(mini.vueltas),
                "integrity": round(float(mini.integridad), 1),
                "fuel": round(float(mini.combustible), 1),
                "stress": round(float(mini.estres), 1),
                "faults": int(mini.faltas),
                "arrests": int(mini.arrestos),
                "accidents": int(mini.accidentes),
                "pedestrian_incidents": int(mini.incidentes_peaton),
                "status": mini.estado,
            })
        self.history_revision += 1

    def history_snapshot(self, driver_id):
        with self.lock:
            if driver_id not in self.history:
                return {"error": "conductor desconocido", "driver_id": driver_id,
                        "revision": self.history_revision, "points": []}
            return {"driver_id": driver_id, "revision": self.history_revision,
                    "points": list(self.history[driver_id])}

    def analytics_snapshot(self):
        with self.lock:
            sim = self.sim
            if sim is None:
                return {"ready": False, "revision": 0, "drivers": [], "clusters": [], "days": []}

            drivers = []
            total_events = max(1, sim.eventos_total)
            for mini in sim.minis:
                actions = [
                    {"name": action.nombre, "type": action.tipo, "count": float(mini.conteo[i]),
                     "gain": action.ganancia, "rep": action.rep * C.ESCALA_REP,
                     "integrity": action.integridad}
                    for i, action in enumerate(C.ACCIONES)
                ]
                total_decisions = max(1.0, float(sum(mini.conteo)))
                criminal_actions = sum(a["count"] for a in actions if a["type"] == "criminal")
                ego = [a for a in actions if a["type"] == "egoista"]
                drivers.append({
                    "id": mini.idx + 1,
                    "name": mini.nombre,
                    "stress": round(float(mini.estres), 1),
                    "aggression": round(float(mini.agresividad), 2),
                    "integrity": round(float(mini.integridad), 1),
                    "decisions": int(sum(mini.conteo)),
                    "criminal_actions": int(criminal_actions),
                    "criminal_share_pct": round(100 * criminal_actions / total_decisions, 2),
                    "crimes_per_100_ticks": round(100 * mini.crimenes / max(1, mini.ticks_trabajo), 2),
                    "events": int(mini.eventos),
                    "events_per_100_ticks": round(100 * mini.eventos / max(1, mini.ticks_trabajo), 2),
                    "luck": round(float(np.clip(1 - mini.eventos / max(1.0, (sim.eventos_total / len(sim.minis)) * 1.5), 0, 1)), 3),
                    "income_per_work_tick": round(float(mini.ingreso) / max(1, mini.ticks_trabajo), 2),
                    "ego_gain": round(sum(a["count"] * a["gain"] for a in ego), 2),
                    "ego_rep_delta": round(sum(a["count"] * a["rep"] for a in ego), 3),
                    "ego_integrity_cost": round(sum(a["count"] * max(0, a["integrity"]) for a in ego), 2),
                    "crimes": int(mini.crimenes),
                    "accidents": int(mini.accidentes),
                    "faults": int(mini.faltas),
                })

            matrix, feature_names, names = analisis.caracteristicas(sim)
            normalized = (matrix - matrix.mean(0)) / (matrix.std(0) + 1e-9)
            k = min(3, len(matrix))
            labels, centers = analisis.kmeans(normalized, k, semilla=self.seed)
            cluster_rows = []
            for cluster_id in range(k):
                members = [names[i] for i in range(len(names)) if int(labels[i]) == cluster_id]
                if not members:
                    continue
                high = np.argsort(-centers[cluster_id])[:2]
                cluster_rows.append({
                    "id": cluster_id + 1,
                    "members": members,
                    "traits": [feature_names[int(i)] for i in high],
                })
            for i, driver in enumerate(drivers):
                driver["cluster"] = int(labels[i]) + 1

            return {
                "ready": True,
                "revision": sim.dia,
                "drivers": drivers,
                "clusters": cluster_rows,
                "features": feature_names,
                "days": list(sim.diario),
                "transit_day": sim.transito.dia_activacion,
                "transit_threshold": C.LIMITE_FALTAS,
                "ticks_per_day": C.TICKS,
            }

    def save_if_finished(self):
        if self.finished_saved or not self.sim:
            return
        OUT.mkdir(parents=True, exist_ok=True)
        analisis.reporte(self.sim, str(OUT))
        for i, mini in enumerate(self.sim.minis, 1):
            np.save(OUT / f"mini{i}_final.npy", mini.cerebro.Q)
        np.save(OUT / "transito_final.npy", self.sim.transito.cerebro.Q)
        info = {"semilla": self.seed, "dias_completados": self.sim.dia,
                "modelo_sha256": self.model_hash, "codigo_sha256": self.code_hash,
                "red_osm_sha256":self.street_hash,"osmnx_version":ox.__version__,
                "modo_transito": self.transit_mode,
                "dificultad": self.difficulty,
                "dia_lanzamiento_transito": self.sim.transito.dia_activacion,
                "epsilon_minis": self.sim.eps_m,
                "epsilon_transito": self.sim.eps_t, "resultado": self.sim.resultado(), "version": 1}
        (OUT / "replicabilidad.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        self.finished_saved = True

    def map_snapshot(self):
        with self.lock:
            if not self.sim:
                return {"ready": False, "loading": self.loading}
            if self.map_cache is not None:
                return self.map_cache
            city = self.sim.ciudad
            points = [(p["x"],p["y"]) for p in city.ruta_mapa]
            minx, maxx = min(p[0] for p in points) - 0.9, max(p[0] for p in points) + 0.9
            miny, maxy = min(p[1] for p in points) - 0.9, max(p[1] for p in points) + 0.9
            lon0, lat0 = NODOS[PARADAS[0]]
            import math
            def project(lon, lat):
                return ((lon-lon0)*111.32*math.cos(math.radians(lat0)), (lat-lat0)*111.32)
            roads=[]; seen=set()
            for u,v,data in city.G.edges(data=True):
                if len(roads) >= 12000: break
                key=frozenset((u,v))
                if key in seen: continue
                nu,nv=city.G.nodes[u],city.G.nodes[v]
                a=project(nu["x"],nu["y"]); b=project(nv["x"],nv["y"])
                if not (minx-0.3 <= a[0] <= maxx+0.3 and miny-0.3 <= a[1] <= maxy+0.3 and
                        minx-0.3 <= b[0] <= maxx+0.3 and miny-0.3 <= b[1] <= maxy+0.3): continue
                seen.add(key)
                geom=data.get("geometry")
                if geom is None: coords=[(nu["x"],nu["y"]),(nv["x"],nv["y"])]
                elif hasattr(geom,"coords"): coords=list(geom.coords)
                else: coords=[point for line in geom.geoms for point in line.coords]
                stride=max(1,(len(coords)-1)//7)
                path=[project(lon,lat) for lon,lat in coords[::stride]]
                if path[-1] != project(*coords[-1]): path.append(project(*coords[-1]))
                roads.append(path)
            route_line=[{"x":p["x"],"y":p["y"]} for p in city.ruta_mapa]
            self.map_cache={"ready":True,"roads":roads,"route_line":route_line,
                            "bounds":[minx,maxx,miny,maxy],"road_count":len(roads)}
            return self.map_cache

    def snapshot(self):
        with self.lock:
            s = self.sim
            if not s:
                return {"loading": self.loading, "error": self.error, "ready": False}
            city = s.ciudad
            nodes = list(dict.fromkeys([seg["a"] for seg in city.segmentos] + [city.segmentos[-1]["b"]]))
            route = [{"name": n, "x": city.xy[n][0], "y": city.xy[n][1]} for n in nodes]
            agents = []
            drivers = []
            for m in s.minis:
                top_actions = sorted(
                    ((int(count), C.ACCIONES[i].nombre) for i, count in enumerate(m.conteo) if count > 0),
                    reverse=True,
                )[:3]
                drivers.append({
                    "id": m.idx + 1,
                    "name": m.nombre,
                    "model": m.perfil["modelo"].strip(),
                    "personality": m.personalidad,
                    "family": m.perfil["tipo_familia"],
                    "family_cost": m.familia,
                    "standard_speed": m.v_est,
                    "max_speed": m.v_max,
                    "aggression": round(float(m.agresividad), 2),
                    "risk_aversion": round(float(m.aversion), 2),
                    "status": m.estado,
                    "money": round(m.billetera),
                    "maximum_debt": round(m.deuda_maxima, 2),
                    "maximum_gain": round(m.ganancia_maxima, 2),
                    "passengers_off_route": int(m.pasajeros_fuera),
                    "end_day": m.dia_fin,
                    "end_reason": m.motivo_fin,
                    "income": round(m.ingreso),
                    "passengers": int(m.pasajeros),
                    "laps": int(m.vueltas),
                    "fuel": round(m.combustible),
                    "integrity": round(m.integridad),
                    "stress": round(m.estres),
                    "faults": int(m.faltas),
                    "arrests": int(m.arrestos),
                    "accidents": int(m.accidentes),
                    "pedestrian_incidents": int(m.incidentes_peaton),
                    "crimes": int(m.crimenes),
                    "events": int(m.eventos),
                    "top_actions": [{"name": name, "count": count} for count, name in top_actions],
                })
                if m.estado in ("eliminado", "abandono"):
                    continue
                idx = city.tramo_en(m.pos); pos_xy=city.xy_en_posicion(m.pos)
                agents.append({"id":m.idx+1,"name":m.nombre,"x":pos_xy[0],"y":pos_xy[1],
                    "status":m.estado,"money":round(m.billetera),"fuel":round(m.combustible),
                    "integrity":round(m.integridad),"wanted":round(m.buscado,1),"stress":round(m.estres),"laps":m.vueltas,
                    "traffic":m.trafico_ultimo,
                    "pedestrian_incidents":m.incidentes_peaton,
                    "pedestrians_nearby":sum(1 for px,py in s.visual_pedestrians if (px-pos_xy[0])**2+(py-pos_xy[1])**2 < 0.12**2)})
            transito = None
            if s.transito.activo:
                pos_xy=city.xy_en_posicion(s.transito.pos)
                transito = {"x":pos_xy[0],"y":pos_xy[1],
                            "arrests":s.transito.arrestos}
            events=[]
            for e in s.visual_eventos:
                agent=next((a for a in agents if a["id"]==e["mini"]),None)
                if agent: events.append({"x":agent["x"],"y":agent["y"],"label":e["nombre"],"mini":e["mini"]})
            pedestrians=[]
            for px,py in s.visual_pedestrians:
                pedestrians.append({"x":px,"y":py})
            traffic_cars=[]
            for car_id,(pos,_velocity) in enumerate(s.visual_traffic_cars):
                px,py=city.xy_en_posicion(pos); traffic_cars.append({"id":car_id,"x":px,"y":py})
            return {"ready":True,"loading":False,"running":self.running,"seed":self.seed,
                "day":s.dia,"target_days":self.target_days,"tick":s.tick_global,"tick_in_day":s.tick_global%C.TICKS,
                "ticks_per_second":self.ticks_per_second,"reputation":round(s.rep,2),"faults":s.faltas,
                "transit_mode":self.transit_mode,"transit_threshold":C.LIMITE_FALTAS,
                "difficulty":self.difficulty,"difficulty_name":C.DIFICULTADES[self.difficulty]["nombre"],
                "transit_day":s.transito.dia_activacion,
                "traffic":s.visual_trafico,"transit_active":s.transito.activo,"agents":agents,"route":route,
                "transit":transito,"events":events,"pedestrians":pedestrians,
                "traffic_cars":traffic_cars,
                "passengers_left":s.cupo,"saved":self.finished_saved,"ended":s.terminado,
                "drivers":drivers,"history_revision":self.history_revision,
                "end_reason":s.motivo_fin,"model_hash":self.model_hash,"code_hash":self.code_hash,"street_hash":self.street_hash,
                "result":s.resultado() if s.dia>=self.target_days or s.terminado else None,
                "maxima_deuda": round(max((m.deuda_maxima for m in s.minis), default=0.0), 2),
                "maxima_deuda_quien": max(s.minis, key=lambda m:m.deuda_maxima).nombre if s.minis else None,
                "maxima_ganancia": round(max((m.ganancia_maxima for m in s.minis), default=0.0), 2),
                "maxima_ganancia_quien": max(s.minis, key=lambda m:m.ganancia_maxima).nombre if s.minis else None}


RUNNER = Runner()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt, *args):
        print(f"HTTP {self.client_address[0]} · {fmt % args}", flush=True)

    def end_headers(self):
        if getattr(self, "no_cache_static", False):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def respond(self, data, status=200):
        raw=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def serve_music(self, filename):
        # Solo se exponen las dos pistas elegidas para la interfaz.
        path = MEDIA / "assets" / "musica" / filename
        if not path.is_file():
            self.send_error(404, "No se encontró la pista de audio.")
            return

        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        requested_range = self.headers.get("Range")
        if requested_range:
            try:
                unit, bounds = requested_range.split("=", 1)
                first, last = bounds.split("-", 1)
                if unit != "bytes" or "," in bounds:
                    raise ValueError
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                else:
                    length = int(last)
                    start = max(0, size - length)
                    end = size - 1
                if start >= size or end < start:
                    raise ValueError
                end = min(end, size - 1)
                status = 206
            except (ValueError, TypeError):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining:
                chunk = source.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def serve_project_image(self, request_path):
        relative_name = request_path.removeprefix("/assets/imagenes/")
        allowed_extensions = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
        image_path = MEDIA / "assets" / "imagenes" / relative_name
        if Path(relative_name).name != relative_name or Path(relative_name).suffix.lower() not in allowed_extensions:
            self.send_error(404)
            return
        if not image_path.is_file():
            image_stem = Path(relative_name).stem
            image_dir = MEDIA / "assets" / "imagenes"
            image_path = next(
                (candidate for candidate in image_dir.glob(f"{image_stem}.*")
                 if candidate.is_file() and candidate.suffix.lower() in allowed_extensions),
                image_path,
            )
        if not image_path.is_file():
            self.send_error(404, "Aún no se ha añadido esta imagen.")
            return
        content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(image_path.stat().st_size))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with image_path.open("rb") as image_file:
            self.copyfile(image_file, self.wfile)

    def serve_vehicle_asset(self, request_path):
        relative_name = request_path.removeprefix("/multimedia/sprites/vehicles/")
        if Path(relative_name).name != relative_name or Path(relative_name).suffix.lower() not in {".png", ".json"}:
            self.send_error(404)
            return
        asset_path = MEDIA / "sprites" / "vehicles" / relative_name
        if not asset_path.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(asset_path.stat().st_size))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with asset_path.open("rb") as source:
            self.copyfile(source, self.wfile)

    def serve_portal_background(self, request_path):
        relative_name = request_path.removeprefix("/fondos/")
        parts = relative_name.split("/")
        if len(parts) != 1 or parts[0] not in {f"fondo{i}.webp" for i in range(1, 6)}:
            self.send_error(404)
            return
        image_path = MEDIA / "assets" / "fondos" / parts[0]
        if not image_path.is_file():
            self.send_error(404, "Añade fondo1.webp a fondo5.webp en assets/fondos.")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/webp")
        self.send_header("Content-Length", str(image_path.stat().st_size))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with image_path.open("rb") as source:
            self.copyfile(source, self.wfile)

    def do_GET(self):
        request_path = urlparse(self.path).path
        music_files = {
            "/assets/musica/soundtrack.mp3": "soundtrack.mp3",
            "/assets/musica/menus.mp3": "menus.mp3",
        }
        if request_path in music_files:
            self.serve_music(music_files[request_path])
            return
        if request_path.startswith("/assets/imagenes/"):
            self.serve_project_image(request_path)
            return
        if request_path.startswith("/multimedia/sprites/vehicles/"):
            self.serve_vehicle_asset(request_path)
            return
        if request_path.startswith("/fondos/"):
            self.serve_portal_background(request_path)
            return
        if request_path == "/api/health":
            self.respond({"ok": True, "service": "dies-irae", "port": self.server.server_port})
            return
        if request_path == "/api/pretraining":
            self.respond(pretraining_snapshot())
            return
        if urlparse(self.path).path=="/api/rules":
            self.respond({"ticks_per_day": C.TICKS, "hours_per_tick": C.HORAS_POR_TICK,
                          "fare_bs": C.TARIFA, "family_cost_multiplier": 1.5,
                          "annual_fee_bs": C.CUOTA, "reputation_minimum": C.REP_MIN_REQ,
                          "transit_fault_threshold": C.LIMITE_FALTAS,
                          "actions": [dict(name=a.nombre, kind=a.tipo, speed=a.velocidad,
                              accident_risk=a.riesgo, integrity_cost=a.integridad,
                              wanted_change=a.buscado, reputation=a.rep,
                              passenger_appeal=a.atractivo, reward=a.ganancia,
                              penalty=a.penalizacion, cost_bs=a.costo, stress=a.estres)
                              for a in C.ACCIONES]}); return
        if urlparse(self.path).path=="/api/state":
            self.respond(RUNNER.snapshot()); return
        if urlparse(self.path).path=="/api/map":
            self.respond(RUNNER.map_snapshot()); return
        if urlparse(self.path).path=="/api/history":
            query=parse_qs(urlparse(self.path).query)
            try: driver_id=int(query.get("id",["1"])[0])
            except ValueError: driver_id=-1
            self.respond(RUNNER.history_snapshot(driver_id)); return
        if urlparse(self.path).path=="/api/analytics":
            self.respond(RUNNER.analytics_snapshot()); return
        if urlparse(self.path).path=="/": self.path="/index.html"
        self.no_cache_static = True
        super().do_GET()

    def do_POST(self):
        try:
            size=int(self.headers.get("Content-Length","0")); data=json.loads(self.rfile.read(size) or b"{}")
            path=urlparse(self.path).path
            if path=="/api/start":
                RUNNER.start(data.get("seed",7),data.get("days",1826),data.get("transit_mode","automatic"),data.get("difficulty","normal"))
            elif path=="/api/reset":
                if not RUNNER.reset():
                    self.respond({"error":"No se puede reiniciar una simulación inexistente, cargando o ya guardada."},409); return
            elif path=="/api/transit":
                result,status=RUNNER.launch_transit()
                self.respond(result,status); return
            elif path=="/api/control":
                with RUNNER.lock:
                    action=data.get("action")
                    if action=="pause": RUNNER.running=False
                    elif action=="resume": RUNNER.running=True
                    elif action=="step": RUNNER.running=False; RUNNER.pending_steps+=int(data.get("ticks",1))
                    elif action=="speed": RUNNER.ticks_per_second=max(1,min(30,int(data.get("value",8))))
            else: self.respond({"error":"endpoint desconocido"},404); return
            self.respond(RUNNER.snapshot())
        except Exception as exc: self.respond({"error":str(exc)},400)


def create_server(preferred_port=8765):
    server = None
    preferred_port = max(1024, min(65535, int(preferred_port)))
    for port in range(preferred_port, min(preferred_port + 21, 65536)):
        try:
            # La interfaz es local; no publicar el servidor en otras interfaces de red.
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError as exc:
            if exc.errno not in (48, 98, 10048):
                raise
    if server is None:
        raise OSError("No hay puertos libres entre 8765 y 8785 para iniciar el juego.")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Servidor local activo en {url}", flush=True)
    if server.server_port != preferred_port:
        print(f"El puerto {preferred_port} ya estaba ocupado; usa la dirección indicada arriba.", flush=True)
    print("Mantén abierta esta ventana mientras juegas. Ctrl+C detiene el servidor.", flush=True)
    return server, url


def main():
    server, _url = create_server()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=="__main__":
    main()



