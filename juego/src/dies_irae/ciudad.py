
import heapq
import math
import bisect
import networkx as nx
import osmnx as ox
from pathlib import Path

NODOS = {
    "Villa Fatima": (-68.1235, -16.4850), "Mercado Villa Fatima": (-68.1220, -16.4870), "Av. Busch Norte": (-68.1210, -16.4900), "Rosasani": (-68.1190, -16.4930), "Plaza Villarroel": (-68.1205, -16.4960),
    "Plaza San Martin": (-68.1215, -16.4990), "Av. Busch Central": (-68.1210, -16.5020), "Estadio Hernando Siles": (-68.1190, -16.5045), "Plaza Uyuni": (-68.1170, -16.5010), "Av. Saavedra": (-68.1150, -16.5000), "Hospital Obrero": (-68.1175, -16.5050), "Plaza Tejada Sorzano": (-68.1195, -16.5070), "Rotonda Garcia Lanza": (-68.1160, -16.5100),
    "Parque Laikakota": (-68.1260, -16.4990), "Teatro al Aire Libre": (-68.1300, -16.4980), "Plaza del Estudiante": (-68.1260, -16.5045), "El Prado": (-68.1290, -16.5005), "Obelisco": (-68.1315, -16.5015), "Av. Camacho": (-68.1325, -16.5030), "Plaza del Bicentenario": (-68.1305, -16.5050), "Calle Ayacucho": (-68.1330, -16.5060), "Plaza Murillo": (-68.1335, -16.4955),
    "Calle Comercio": (-68.1345, -16.4960), "Perez Velasco": (-68.1355, -16.4970), "San Francisco": (-68.1380, -16.4975), "Av. Mariscal Santa Cruz": (-68.1390, -16.4985), "Pza. Eguino": (-68.1400, -16.4995), "Max Paredes": (-68.1420, -16.5010),
    "Plaza San Pedro": (-68.1400, -16.5040), "Mercado Rodriguez": (-68.1420, -16.5060), "Av. 20 de Octubre": (-68.1390, -16.5070), "Landaeta": (-68.1370, -16.5090), "Alto San Pedro": (-68.1420, -16.5100), "Hospital General": (-68.1370, -16.5120),
    "Plaza Abaroa": (-68.1245, -16.5105), "Fernando Guachalla": (-68.1270, -16.5115), "Belisario Salinas": (-68.1290, -16.5095), "Sopocachi Central": (-68.1260, -16.5130), "Plaza España": (-68.1300, -16.5150), "Plaza Isabel La Catolica": (-68.1315, -16.5120),
    "San Jorge": (-68.1330, -16.5140), "Av. 6 de Agosto": (-68.1350, -16.5160), "Plaza Bolivia": (-68.1370, -16.5170), "Av. Arce": (-68.1320, -16.5080), "Puentes Trillizos": (-68.1400, -16.5150), "Av. del Libertador": (-68.1420, -16.5180), "Tembladerani": (-68.1450, -16.5190), "Cotahuma": (-68.1450, -16.5100),
}

DEMANDA = {
    "Villa Fatima": 2.65, "Mercado Villa Fatima": 2.90, "Av. Busch Norte": 1.85, "Rosasani": 1.70, "Plaza Villarroel": 2.35,
    "Plaza San Martin": 2.30, "Av. Busch Central": 2.45, "Estadio Hernando Siles": 2.70, "Plaza Uyuni": 2.25, "Av. Saavedra": 2.40, "Hospital Obrero": 2.75, "Plaza Tejada Sorzano": 2.80, "Rotonda Garcia Lanza": 2.15,
    "Parque Laikakota": 2.15, "Teatro al Aire Libre": 1.65, "Plaza del Estudiante": 2.90, "El Prado": 3.00, "Obelisco": 2.85, "Av. Camacho": 2.80, "Plaza del Bicentenario": 2.30, "Calle Ayacucho": 2.60, "Plaza Murillo": 2.95,
    "Calle Comercio": 2.85, "Perez Velasco": 3.00, "San Francisco": 3.00, "Av. Mariscal Santa Cruz": 3.00, "Pza. Eguino": 2.85, "Max Paredes": 2.80,
    "Plaza San Pedro": 2.75, "Mercado Rodriguez": 3.00, "Av. 20 de Octubre": 2.80, "Landaeta": 2.15, "Alto San Pedro": 2.20, "Hospital General": 2.85,
    "Plaza Abaroa": 2.45, "Fernando Guachalla": 2.20, "Belisario Salinas": 2.35, "Sopocachi Central": 2.70, "Plaza España": 2.60, "Plaza Isabel La Catolica": 2.40,
    "San Jorge": 2.25, "Av. 6 de Agosto": 2.55, "Plaza Bolivia": 2.65, "Av. Arce": 2.80, "Puentes Trillizos": 1.65, "Av. del Libertador": 1.70, "Tembladerani": 2.15, "Cotahuma": 2.45,
}

OCULTAS = [("Plaza del Estudiante", "San Francisco"), ("Plaza San Pedro", "Sopocachi Central"),("Plaza Tejada Sorzano", "Plaza España"),("San Francisco", "Plaza Abaroa"),]

PARADAS = [
    "Villa Fatima", "Mercado Villa Fatima", "Av. Busch Norte", "Rosasani", "Plaza Villarroel",
    "Plaza San Martin", "Av. Busch Central", "Estadio Hernando Siles", "Plaza Uyuni", "Av. Saavedra", "Hospital Obrero",
    "Plaza Tejada Sorzano", "Rotonda Garcia Lanza", "Parque Laikakota", "Teatro al Aire Libre", "Plaza del Estudiante", "El Prado", "Obelisco", "Av. Camacho", "Plaza del Bicentenario", "Calle Ayacucho", "Plaza Murillo",
    "Calle Comercio", "Perez Velasco", "San Francisco", "Av. Mariscal Santa Cruz", "Pza. Eguino", "Max Paredes", "Plaza San Pedro", "Mercado Rodriguez", "Av. 20 de Octubre", "Landaeta", "Alto San Pedro", "Hospital General",
    "Plaza Abaroa", "Fernando Guachalla", "Belisario Salinas", "Sopocachi Central", "Plaza España", "Plaza Isabel La Catolica", "San Jorge", "Av. 6 de Agosto", "Plaza Bolivia", "Av. Arce", "Puentes Trillizos",
    "Av. del Libertador", "Tembladerani", "Cotahuma",
]

class Ciudad:
    def __init__(self, graph=None):
        raiz = Path(__file__).resolve().parents[3]
        cache_osmnx = raiz / ".cache" / "osmnx"
        cache_osmnx.mkdir(parents=True, exist_ok=True)
        ox.settings.cache_folder = str(cache_osmnx)
        faltantes = [p for p in PARADAS if p not in NODOS]
        if faltantes:
            raise ValueError(f"PARADAS sin coordenadas en NODOS: {faltantes}")
        bbox = (-68.2000, -16.6000, -68.0500, -16.4200)
        if graph is None:
            print("Descargando calles de La Paz desde OpenStreetMap...")
            graph = ox.graph_from_bbox(bbox=bbox, network_type="drive", simplify=True)
        self.G = graph
        if len(self.G) == 0:
            raise RuntimeError("OSMnx devolvió un grafo vacío.")

        self.G_proj = ox.project_graph(self.G)
        self.nodos_parada = {nombre: ox.distance.nearest_nodes(self.G, X=lon, Y=lat) for nombre, (lon, lat) in NODOS.items()}
        lon0, lat0 = NODOS[PARADAS[0]]
        self.xy = {nombre: (((lon - lon0) * 111.32 * math.cos(math.radians(lat0))), (lat - lat0) * 111.32) for nombre, (lon, lat) in NODOS.items()}
        self.G_costos = nx.DiGraph()
        self.G_costos.add_nodes_from(self.G.nodes(data=True))
        for u, v, data in self.G.edges(data=True):
            peso = data.get("length", math.inf)
            if peso < self.G_costos.get_edge_data(u, v, {}).get("length", math.inf):
                self.G_costos.add_edge(u, v, length=peso)

        self._rutas_cache = {}
        self.vecinos = {p: [] for p in PARADAS}
        self._construir_conexiones_reales()
        self._construir_ruta()
        self._construir_geometria_ruta()
        print(f"Grafo OSM listo: {len(self.G.nodes):,} nodos, {len(self.G.edges):,} aristas. Ruta simulada: {len(self.segmentos)} segmentos, {self.largo_total:.2f} km.")

    @staticmethod
    def _dist_coord(a, b):
        lon1, lat1 = a
        lon2, lat2 = b
        R = 6371000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * R * math.atan2(math.sqrt(h), math.sqrt(1 - h))

    def _dist(self, a, b): return self._dist_coord(NODOS[a], NODOS[b]) / 1000.0
    def _peso_arista(self, u, v): return self.G_costos[u][v]["length"]
    def _dijkstra_osm(self, origen, meta):
        inicio, objetivo = self.nodos_parada[origen], self.nodos_parada[meta]
        try:
            distancia, camino = nx.single_source_dijkstra(self.G_costos, inicio, objetivo, weight="length")
            return camino, distancia / 1000.0
        except nx.NetworkXNoPath:
            raise nx.NetworkXNoPath(f"No existe camino OSM: {origen} -> {meta}")

    def _tiene_semaforo(self, nodo):
        data = self.G.nodes[nodo]
        return data.get("highway") == "traffic_signals" or "traffic_signals" in data

    def _ruta_tiene_semaforo(self, camino): return any(self._tiene_semaforo(nodo) for nodo in camino)
    def _ruta_osm(self, origen, meta):
        clave = (origen, meta)
        if clave not in self._rutas_cache:
            self._rutas_cache[clave] = self._dijkstra_osm(origen, meta)
        return self._rutas_cache[clave]

    def a_estrella(self, origen, meta, ocultas=False):
        if ocultas:
            for a, b in OCULTAS:
                if (origen, meta) in ((a, b), (b, a)):
                    distancia = self._dist(origen, meta) * 0.80
                    return [self.nodos_parada[origen], self.nodos_parada[meta]], distancia
        return self._ruta_osm(origen, meta)

    def _construir_conexiones_reales(self):
        for a, b in zip(PARADAS[:-1], PARADAS[1:]):
            try:
                camino, distancia = self._ruta_osm(a, b)
                self.vecinos[a].append((b, distancia, self._ruta_tiene_semaforo(camino), False))
            except nx.NetworkXNoPath:
                print(f"Advertencia: no se encontró ruta OSM entre {a} y {b}.")

    def _construir_ruta(self):
        self.segmentos = []
        for a, b in zip(PARADAS[:-1], PARADAS[1:]):
            camino, distancia = self._ruta_osm(a, b)
            demanda = (DEMANDA.get(a, 1.0) + DEMANDA.get(b, 1.0)) / 2.0
            self.segmentos.append({"a": a, "b": b, "largo": distancia, "semaforo": self._ruta_tiene_semaforo(camino), "demanda": demanda, "camino": camino})

        self.acumulado = [0.0]
        for segmento in self.segmentos:
            self.acumulado.append(self.acumulado[-1] + segmento["largo"])
        self.largo_total = self.acumulado[-1]

        self.atajos = {}
        for a, b in OCULTAS:
            if a not in PARADAS or b not in PARADAS:
                continue
            ia, ib = PARADAS.index(a), PARADAS.index(b)
            salto = ib - ia
            if salto < 1:
                continue
            normal = sum(self.segmentos[k]["largo"] for k in range(ia, ib))
            distancia_atajo = self._dist(a, b) * 0.80
            ahorro = max(0.0, normal - distancia_atajo)
            self.atajos[ia] = (salto, ahorro)

    def tramo_en(self, pos):
        if self.largo_total <= 0:
            return 0
        pos %= self.largo_total
        for i, segmento in enumerate(self.segmentos):
            if pos < self.acumulado[i + 1]:
                return i
        return len(self.segmentos) - 1

    def _construir_geometria_ruta(self):
        """Puntos de la ruta medidos sobre los nodos OSM, en las mismas unidades que pos."""
        lon0, lat0 = NODOS[PARADAS[0]]
        coslat = math.cos(math.radians(lat0))
        self.ruta_mapa = []
        for i, segmento in enumerate(self.segmentos):
            base = self.acumulado[i]
            camino = segmento["camino"]
            if not camino: continue
            def xy_node(n):
                nd = self.G.nodes[n]
                return ((nd["x"]-lon0)*111.32*coslat, (nd["y"]-lat0)*111.32)
            if not self.ruta_mapa or abs(self.ruta_mapa[-1]["dist"] - base) > 1e-9:
                x,y=xy_node(camino[0]); self.ruta_mapa.append({"dist":base,"x":x,"y":y})
            aristas=[self.G_costos[u][v]["length"] for u,v in zip(camino[:-1],camino[1:])]
            total=sum(aristas); local=0.0
            for j,(u,v) in enumerate(zip(camino[:-1],camino[1:])):
                local += (aristas[j]/total*segmento["largo"]) if total else 0.0
                distancia=self.acumulado[i+1] if j==len(aristas)-1 else base+local
                x,y=xy_node(v); self.ruta_mapa.append({"dist":distancia,"x":x,"y":y})
        if not self.ruta_mapa:
            self.ruta_mapa=[{"dist":0.0,"x":self.xy[PARADAS[0]][0],"y":self.xy[PARADAS[0]][1]},
                            {"dist":self.largo_total,"x":self.xy[PARADAS[-1]][0],"y":self.xy[PARADAS[-1]][1]}]
        self._ruta_distancias=[p["dist"] for p in self.ruta_mapa]

    def xy_en_posicion(self, pos):
        """Interpola una posición longitudinal del juego sobre la calle OSM correspondiente."""
        p=pos % max(self.largo_total,1e-9)
        i=max(0,min(len(self.ruta_mapa)-2,bisect.bisect_right(self._ruta_distancias,p)-1))
        a,b=self.ruta_mapa[i],self.ruta_mapa[i+1]
        f=(p-a["dist"])/max(b["dist"]-a["dist"],1e-9)
        return (a["x"]+(b["x"]-a["x"])*f,a["y"]+(b["y"]-a["y"])*f)


