"""Entorno multiagente: 5 minibuseros (SARSA) + Tránsito (Q-learning) en una ruta de La Paz.

Modos de simulación:
  'preentreno'          -> sin eliminación, cárcel corta, Tránsito presente (los minis aprenden a conducir)
  'preentreno_transito' -> Tránsito practica contra minis con política ruidosa
  'simulacion'          -> el juego real de 5 años (eliminación, cárcel de 7 meses, finales)
"""
import numpy as np
from collections import deque
from . import config as C
from .ciudad import Ciudad, NODOS, PARADAS
from .aprendizaje import AgenteTabular, codificar

ACC = C.ACCIONES; N_ACC = len(ACC); IA = C.INDICE_ACCION
# estado del minibusero: combustible, tráfico pesado, buscado, perseguido, presión, integridad>50, semáforo, recarga disponible, atajo conocido
DIM_MINI = (3, 2, 3, 2, 3, 2, 2, 2, 2)
N_ESTADOS_MINI = int(np.prod(DIM_MINI))
DIM_TRANSITO = (4, 3, 3, 2); N_ESTADOS_TRANSITO = int(np.prod(DIM_TRANSITO)); N_ACC_TRANSITO = 5
ACC_LETALES = {IA["estrellar_unidad"], IA["atropellar_pasajero"]}   # no se exploran al azar en la simulación real
EVENTOS = ["corte_de_via", "entrada_folklorica", "atraco", "aparicion_fantasma", "bloqueo_vecinal", "mitín publicitario","Evo Quqeue"]
TANQUE_LITROS = 80.0
RENDIMIENTO_KM_L = 7.0
CONSUMO = TANQUE_LITROS / RENDIMIENTO_KM_L
UMBRAL_RECARGA = TANQUE_LITROS * 0.65
COMBUSTIBLE_BAJO = TANQUE_LITROS * 0.10
COMBUSTIBLE_MEDIO = TANQUE_LITROS * 0.45


def prior_acciones(P):
    """Q inicial = recompensa inmediata esperada de cada acción según la tabla y la personalidad (la 'identidad')."""
    v = np.zeros(N_ACC)
    for i, a in enumerate(ACC):
        if a.tipo == "neutro": v[i] = C.ESCALA_RECOMPENSA * a.ganancia
        else: v[i] = C.ESCALA_RECOMPENSA * (P["pesos"][a.tipo] * a.ganancia - a.penalizacion * P["aversion_riesgo"]) - 0.8 * a.buscado
    v[IA["estrellar_unidad"]] -= 3.0; v[IA["atropellar_pasajero"]] -= 11.0
    return v * 3.0


class Minibus:
    def __init__(self, idx, perfil, cerebro, rng):
        self.idx, self.perfil, self.cerebro, self.rng = idx, perfil, cerebro, rng
        self.nombre = perfil["nombre"]; self.personalidad = perfil["personalidad"]
        P = C.PERSONALIDADES[self.personalidad]
        self.agresividad, self.aversion, self.lam, self.pesos_base = P["agresividad"], P["aversion_riesgo"], P["lam"], P["pesos"]
        self.pesos = dict(self.pesos_base)
        self.v_est, self.v_max, self.familia = perfil["v_estandar"], perfil["v_maxima"], perfil["familia"]
        self.trafico_ultimo = 0
        self.dia_restriccion = idx % 5                       # día sin circular (lunes a viernes)
        self.estado = "activo"; self.billetera = 3000.0; self.combustible = TANQUE_LITROS; self.enfriamiento = 99
        self.billetera_inicial = self.billetera; self.deuda_maxima = 0.0; self.ganancia_maxima = 0.0
        self.integridad = 100.0; self.buscado = 0.0; self.estres = 20.0; self.comodidad = 0.0
        self.pos = rng.random() * 3; self.precision = 100.0; self.conocidos = set()
        self.deuda_sindicato = 0.0; self.preso_hasta = -1; self.malus_hasta = -1
        self.pendiente = None; self.recientes = deque(maxlen=4)
        self.conteo = np.zeros(N_ACC); self.eventos = 0; self.faltas = 0; self.arrestos = 0
        self.incidentes_peaton = 0
        self.vueltas = 0; self.ingreso = 0.0; self.pasajeros = 0; self.pasajeros_fuera = 0; self.crimenes = 0; self.accidentes = 0
        self.omite_sind = 0; self.omite_hogar = 0; self.ticks_trabajo = 0
        self.metas_anio = []; self.vueltas_anio = 0; self.omite_sind_anio = 0; self.omite_hogar_anio = 0; self.ticks_anio = 0
        self.billetera_anio0 = self.billetera; self.dia_fin = None; self.motivo_fin = ""
        self.ingreso_dia = 0.0; self.eventos_dia = 0; self.tick_ultimo_crimen = -99
        self.bitacora = []; self.trabajando = False; self.termino = False

    def atractivo(self, extra=0.0):
        return float(np.clip(1.0 + self.comodidad + extra, 0.3, 2.0))


class Transito:
    def __init__(self, cerebro):
        self.cerebro = cerebro; self.activo = False; self.objetivo = None
        self.pos = 0.0
        self.arrestos = 0; self.dia_activacion = None; self.ultimo_exito = 0
        self.bitacora = []; self.recompensa_total = 0.0


def multa_transito(sim, info, objetivo):
    """Multa a infractores egoístas cuando Tránsito está activo (huir la evita)."""
    acc = info["acc"]
    if not sim.transito.activo or acc.tipo != "egoista" or acc.nombre == "huir_transito": return False
    return sim.rng.random() < (0.25 if info["mini"] is objetivo else 0.06)


class Simulacion:
    def __init__(self, semilla=0, modo="simulacion", Q_minis=None, Q_transito=None, aprende_minis=True,
                 aprende_transito=True, eps_minis=0.05, eps_transito=0.05, bitacora=True, ciudad=None,
                 transito_manual=False):
        self.rng = np.random.default_rng(semilla); self.modo = modo; self.ciudad = ciudad or Ciudad()
        self.aprende_m, self.aprende_t, self.eps_m, self.eps_t, self.registrar = aprende_minis, aprende_transito, eps_minis, eps_transito, bitacora
        self.minis = []
        for i, p in enumerate(C.PERFILES):
            cerebro = AgenteTabular(N_ESTADOS_MINI, N_ACC, "sarsa", self.rng, C.ALFA, C.GAMMA)
            if Q_minis is not None: cerebro.Q = Q_minis[i].copy()
            else: cerebro.Q[:] = prior_acciones(C.PERSONALIDADES[p["personalidad"]])
            self.minis.append(Minibus(i, p, cerebro, self.rng))
        cerebro_t = AgenteTabular(N_ESTADOS_TRANSITO, N_ACC_TRANSITO, "q", self.rng, C.ALFA, C.GAMMA)
        if Q_transito is not None: cerebro_t.Q = Q_transito.copy()
        self.transito = Transito(cerebro_t); self.transito_manual = bool(transito_manual)
        self.dia = 0; self.rep = C.REP_MAX; self.faltas = 0; self.terminado = False; self.motivo_fin = ""
        self.cuota = C.CUOTA; self.pen_pasiva = 1.0; self.cuotas_recaudadas = 0.0
        self.tick_global = 0; self.diario = []; self.registro_anual = []; self.eventos_total = 0
        # Telemetría ligera para el panel en vivo; no altera el consumo del RNG del experimento.
        self.visual_tick = -1; self.visual_trafico = 0; self.visual_eventos = []
        # Peatones ocupan calles de todo el mapa; el minibús decide si cede el paso o asume el riesgo.
        largo = self.ciudad.largo_total
        puntos_ruta = self.ciudad.ruta_mapa
        minx, maxx = min(p["x"] for p in puntos_ruta) - 0.8, max(p["x"] for p in puntos_ruta) + 0.8
        miny, maxy = min(p["y"] for p in puntos_ruta) - 0.8, max(p["y"] for p in puntos_ruta) + 0.8
        lon0, lat0 = NODOS[PARADAS[0]]
        coslat = np.cos(np.radians(lat0))
        calles = [((d["x"] - lon0) * 111.32 * coslat, (d["y"] - lat0) * 111.32)
                  for _, d in self.ciudad.G.nodes(data=True)
                  if minx <= (d["x"] - lon0) * 111.32 * coslat <= maxx
                  and miny <= (d["y"] - lat0) * 111.32 <= maxy]
        if not calles:
            calles = [(self.ciudad.xy_en_posicion((i * 0.61803398875 % 1.0) * largo)) for i in range(28)]
        self.pedestrian_streets = calles
        self.visual_pedestrians = [calles[int(i * 0.61803398875 % 1.0 * len(calles))] for i in range(28)]
        self.visual_traffic_cars = [((i * 0.754877666 % 1.0) * largo,
                                     (1 if i % 2 else -1) * (0.72 + (i % 6) * 0.13))
                                    for i in range(62)]
        self.cupo = 0
        if modo in ("preentreno", "preentreno_transito"): self._activar_transito()

    # ------------------------------------------------------------ utilidades
    def anio_de(self, d):
        """Devuelve (índice_año, días_que_faltan_incluyendo_hoy, días_del_año)."""
        if self.modo != "simulacion": d = d % 365
        acum = 0
        for a, n in enumerate(C.DIAS_POR_ANO):
            acum += n
            if d < acum: return a, acum - d, n
        return len(C.DIAS_POR_ANO) - 1, 0, C.DIAS_POR_ANO[-1]

    def _activar_transito(self):
        if not self.transito.activo:
            self.transito.activo = True; self.transito.dia_activacion = self.dia

    def activar_transito(self):
        """Despliega Tránsito a pedido del operador, registrando el día de activación."""
        self._activar_transito()

    def _trafico(self, t, dsem):
        base = 2 if (t in (2, 3, 12, 13)) else (1 if t in (1, 4, 5, 11, 14) else 0)
        base += 0 if dsem < 5 else -1
        return int(np.clip(base + (self.rng.random() < 0.15), 0, 2))

    def _trafico_local(self, tramo, base, ocupacion):
        n = len(ocupacion)
        alrededor = sum(ocupacion[(tramo + d) % n] for d in (-1, 0, 1))
        local = 2 if alrededor >= 8 else 1 if alrededor >= 4 else 0
        return max(base, local)

    def _presion(self, m):
        """Obligaciones de los próximos 30 días (cuota + hogar + deuda) vs. billetera. 0=holgado, 2=crítico."""
        a, faltan, n = self.anio_de(self.dia)
        necesita = m.deuda_sindicato + self.cuota * 30 / n + m.familia * 30
        r = m.billetera / max(necesita, 1.0)
        return 2 if r < 0.3 else (1 if r < 1.0 else 0)

    def _estado(self, m, t, trafico, perseguido):
        tramo = self.ciudad.tramo_en(m.pos)
        fb = 0 if m.combustible <= COMBUSTIBLE_BAJO else 1 if m.combustible <= COMBUSTIBLE_MEDIO else 2
        wb = 0 if m.buscado < 2 else 1 if m.buscado <= C.BUSCADO_ARRESTO else 2
        return codificar((fb, int(trafico == 2), wb, int(perseguido), self._presion(m), int(m.integridad > 50),
                          int(self.ciudad.segmentos[tramo]["semaforo"]), int(m.enfriamiento >= C.ENFRIAMIENTO_RECARGA),
                          int(tramo in m.conocidos)), DIM_MINI)

    def _validas(self, m, perseguido):
        if m.estado == "prision" or m.estado in ("eliminado", "abandono"):
            return [IA["terminar_turno"]]
        if m.combustible <= 0:
            return [IA["cargar_combustible"]] if m.enfriamiento >= C.ENFRIAMIENTO_RECARGA else [IA["terminar_turno"]]
        v = []
        for i, a in enumerate(ACC):
            if a.nombre == "cargar_combustible" and not (m.enfriamiento >= C.ENFRIAMIENTO_RECARGA and m.combustible <= UMBRAL_RECARGA): continue
            if a.nombre == "huir_transito" and not perseguido: continue
            v.append(i)
        return v

    # ------------------------------------------------------------ Tránsito
    def _estado_transito(self, franja):
        w = sorted([m.buscado for m in self.minis if m.trabajando and not m.termino], reverse=True) or [0]
        tope = 0 if w[0] < 2 else 1 if w[0] <= 5 else 2 if w[0] <= 8 else 3
        n = sum(x > C.BUSCADO_ARRESTO for x in w)
        return codificar((tope, min(n, 2), franja, self.transito.ultimo_exito), DIM_TRANSITO)

    def _elegir_objetivo(self, acc_t, trabajadores):
        por_buscado = sorted(trabajadores, key=lambda m: -m.buscado)
        if acc_t == 0: return por_buscado[0]                                        # perseguir al más buscado
        if acc_t == 1: return por_buscado[1] if len(por_buscado) > 1 else por_buscado[0]   # al segundo más buscado
        if acc_t == 2:                                                              # al último infractor
            ultimo = max(trabajadores, key=lambda m: m.tick_ultimo_crimen)
            return ultimo if ultimo.tick_ultimo_crimen > self.tick_global - 8 else trabajadores[int(self.rng.integers(len(trabajadores)))]
        if acc_t == 4:                                                              # emboscada en semáforo
            con_semaforo = [m for m in por_buscado if self.ciudad.segmentos[self.ciudad.tramo_en(m.pos)]["semaforo"]]
            return con_semaforo[0] if con_semaforo else trabajadores[int(self.rng.integers(len(trabajadores)))]
        return trabajadores[int(self.rng.integers(len(trabajadores)))]              # patrullar

    # ------------------------------------------------------------ un tick
    def tick(self, t, dsem):
        ciu = self.ciudad; franja = t * 3 // C.TICKS; self.tick_global += 1
        for i in range(len(self.visual_pedestrians)):
            if self.rng.random() < 0.025 and self.pedestrian_streets:
                self.visual_pedestrians[i] = self.pedestrian_streets[int(self.rng.integers(len(self.pedestrian_streets)))]
        trafico = self._trafico(t, dsem)
        velocidad_auto = (9.0, 4.5, 1.2)[trafico]
        self.visual_traffic_cars = [((pos + np.sign(vel) * velocidad_auto * abs(vel)) % ciu.largo_total, vel)
                                    for pos, vel in self.visual_traffic_cars]
        self.visual_tick = self.tick_global; self.visual_trafico = trafico; self.visual_eventos = []
        ocupacion = [0] * len(ciu.segmentos)
        for pos, _ in self.visual_traffic_cars: ocupacion[ciu.tramo_en(pos)] += 1
        trabajadores = [m for m in self.minis if m.trabajando and not m.termino]
        if not trabajadores:
            if self.transito.activo: self.transito.pos = (self.transito.pos + 4.0) % ciu.largo_total
            return
        rep0 = self.rep
        tr = self.transito; objetivo = None; est_t = acc_t = None
        if tr.activo:
            est_t = self._estado_transito(franja)
            acc_t = tr.cerebro.elegir(est_t, range(N_ACC_TRANSITO), self.eps_t)
            objetivo = self._elegir_objetivo(acc_t, trabajadores)
        tr.objetivo = objetivo
        if tr.activo:
            if objetivo is None:
                tr.pos = (tr.pos + 4.0) % ciu.largo_total
            else:
                delta = objetivo.pos - tr.pos
                if delta > ciu.largo_total / 2: delta -= ciu.largo_total
                elif delta < -ciu.largo_total / 2: delta += ciu.largo_total
                paso = max(0.5, objetivo.v_est * C.HORAS_POR_TICK * 1.2)
                tr.pos = (tr.pos + np.sign(delta) * min(abs(delta), paso)) % ciu.largo_total
        infos = []
        # ---- fase A: decisión y movimiento
        for k in self.rng.permutation(len(trabajadores)):
            m = trabajadores[k]; perseguido = (m is objetivo)
            tramo_actual = ciu.tramo_en(m.pos)
            trafico_m = self._trafico_local(tramo_actual, trafico, ocupacion)
            m.trafico_ultimo = trafico_m
            s = self._estado(m, t, trafico_m, perseguido); validas = self._validas(m, perseguido)
            explorables = [x for x in validas if x not in ACC_LETALES] if self.modo == "simulacion" else validas
            a = m.cerebro.elegir(s, validas, self.eps_m, explorables)
            if m.pendiente is not None and self.aprende_m:
                ps, pa, pr = m.pendiente; m.cerebro.actualizar_sarsa(ps, pa, pr, s, a)
            acc = ACC[a]; m.conteo[a] += 1; m.ticks_trabajo += 1; m.ticks_anio += 1
            tramo_i = ciu.tramo_en(m.pos); tramo = ciu.segmentos[tramo_i]
            mx, my = ciu.xy_en_posicion(m.pos)
            peatones = sum(1 for px, py in self.visual_pedestrians if (px - mx) ** 2 + (py - my) ** 2 < 0.12 ** 2)
            info = dict(mini=m, s=s, a=a, acc=acc, perseguido=perseguido, pax=0, ingreso=0.0, pax_fuera=0, accidente=False,
                        peatones=peatones, trafico=trafico_m, tramo_i=tramo_i,
                        muerte=False, crimen=False, vueltas=0, huyo=False, multado=False, evento=None, gasto=0.0)
            m.enfriamiento = min(99, m.enfriamiento + 1); cruzo_rojo = False
            if acc.nombre == "cargar_combustible":
                gasto = acc.costo * (TANQUE_LITROS - m.combustible) / TANQUE_LITROS
                m.combustible = TANQUE_LITROS; m.enfriamiento = 0; m.billetera -= gasto; info["gasto"] = gasto; v = 0.0

            elif acc.nombre == "terminar_turno":
                m.termino = True; v = 0.0
            else:
                factor_trafico = (1.0, 0.8, 0.6)[trafico_m]; v = min(m.v_max, m.v_est * acc.velocidad * factor_trafico)
                if tramo["semaforo"]:
                    if acc.nombre in C.LEGALES: v *= 0.9
                    else: cruzo_rojo = True
                if acc.nombre == "ceder_paso" and peatones:
                    v *= 0.62
                bono = 0.0
                if acc.nombre == "tomar_atajo" and tramo_i in ciu.atajos:
                    if tramo_i in m.conocidos: bono = ciu.atajos[tramo_i][1]
                    elif self.rng.random() < 0.12:        # descubre el atajo
                        m.conocidos.add(tramo_i); bono = ciu.atajos[tramo_i][1]; m.precision -= 3; info["descubrio"] = tramo_i
                    else: m.precision -= 0.5
                elif acc.nombre == "tomar_atajo": m.precision -= 0.5
                antes = m.pos; m.pos += v * C.HORAS_POR_TICK + bono
                nv = int(m.pos // ciu.largo_total) - int(antes // ciu.largo_total)
                info["vueltas"] = nv; m.vueltas += nv; m.vueltas_anio += nv
                distancia_tick = v * C.HORAS_POR_TICK
                factor_trafico_combustible = (1.0, 1.12, 1.30)[trafico_m]
                factor_velocidad = 1.0 + 0.12 * max(0.0, v / m.v_est - 1.0)
                factor_accion = 0.95 if acc.nombre == "limite_velocidad" else 1.0
                m.combustible -= (distancia_tick / RENDIMIENTO_KM_L) * factor_trafico_combustible * factor_velocidad * factor_accion
                m.combustible = max(0.0, m.combustible)

                if acc.costo: m.billetera -= acc.costo; info["gasto"] = acc.costo
                if acc.nombre == "aseo_unidad": m.comodidad = min(0.5, m.comodidad + 0.12)
            info.update(v=v, rojo=cruzo_rojo, tramo=tramo); infos.append(info)
        # ---- fase B: pasajeros (finitos y en competencia)
        ticks_restantes = max(1, C.TICKS - t)
        disponibles = self.cupo / ticks_restantes * (1.25 if trafico == 2 else 1.0)
        pesos = []
        for inf in infos:
            m = inf["mini"]
            if inf["v"] <= 0: pesos.append(0.0); continue
            extra = inf["acc"].atractivo + (0.1 if self.rep >= 4 else -0.1 if self.rep < C.REP_ATROZ else 0)
            w = m.atractivo(extra) * (inf["v"] / m.v_est) ** 0.6 * inf["tramo"]["demanda"] * (1.0 if m.integridad > 30 else 0.7)
            pesos.append(w)
        total = sum(pesos)
        for inf, w in zip(infos, pesos):
            if w <= 0 or total <= 0: continue
            m = inf["mini"]; malus = C.FACTOR_MALUS if self.dia < m.malus_hasta else 1.0
            p = int(min(30, self.rng.poisson(disponibles * w / total * malus * self.pen_pasiva)))
            p = min(p, self.cupo); self.cupo -= p; inf["pax"] = p; inf["ingreso"] = p * C.TARIFA
            # Tomar el atajo es una decisión de desvío: puede recoger peatones fuera del recorrido regular.
            if inf["acc"].nombre == "tomar_atajo":
                fuera = min(max(0, self.cupo), int(self.rng.poisson(inf["peatones"] * 0.18)))
                inf["pax_fuera"] = fuera; inf["pax"] += fuera; self.cupo -= fuera
                inf["ingreso"] += fuera * 0.5
                m.pasajeros_fuera += fuera
        # ---- fase C: accidentes, eventos, faltas, reputación
        for inf in infos:
            m, acc = inf["mini"], inf["acc"]; fl = 0
            if acc.nombre == "no_aportar_sindicato": m.omite_sind += 1; m.omite_sind_anio += 1
            if acc.nombre == "no_aportar_hogar": m.omite_hogar += 1; m.omite_hogar_anio += 1
            forzado = acc.nombre in ("estrellar_unidad", "atropellar_pasajero")
            if inf["v"] > 0 or forzado:
                p = 0.0008 + acc.riesgo + (0.006 if inf["rojo"] else 0) + 0.001 * inf["trafico"]
                if inf["peatones"] and acc.nombre != "ceder_paso":
                    p += 0.003 * min(inf["peatones"], 3)
                p *= (0.6 + m.agresividad) * (1.5 if m.integridad < 35 else 1.0) * (1.3 if inf["v"] > m.v_est * 1.3 else 1.0)
                if forzado or self.rng.random() < max(p, 0):
                    inf["accidente"] = True; m.accidentes += 1; severidad = float(self.rng.integers(5, 25))
                    fuera_de_ruta = inf["tramo_i"] in ciu.atajos and acc.nombre == "tomar_atajo"
                    m.integridad -= (acc.integridad if forzado else severidad) * (1.5 if fuera_de_ruta else 1.0)
                    m.buscado += 0.4; fl += 1; self.rep -= 0.003 if fuera_de_ruta else 0.01
                    if fuera_de_ruta: m.estres += 12
                    inf["ingreso"] *= 0.5; m.estres += 4
                    if inf["peatones"] and acc.nombre != "ceder_paso":
                        inf["evento"] = "incidente_peatonal"; m.incidentes_peaton += 1
                        m.buscado += 0.5; fl += 1; self.rep -= 0.01
                    p_mortal = 0.004
                    if acc.nombre == "atropellar_pasajero" or self.rng.random() < p_mortal:  # hay una víctima mortal
                        inf["muerte"] = True; m.buscado += 5.0 if acc.nombre != "atropellar_pasajero" else 0
                        fl += 3; self.rep -= C.PENALIZACION_REP_ARRESTO * (0.5 if fuera_de_ruta else 1.0); inf["ingreso"] = 0.0
            if inf["pax_fuera"]:
                self.rep -= 0.004 * inf["pax_fuera"]
            if not forzado: m.integridad -= acc.integridad
            if acc.tipo == "criminal":
                inf["crimen"] = True; m.crimenes += 1; fl += 1; m.tick_ultimo_crimen = self.tick_global
            m.buscado += acc.buscado
            self.rep += acc.rep * C.ESCALA_REP; m.estres = float(np.clip(m.estres + acc.estres, 0, 100))
            if multa_transito(self, inf, tr.objetivo): inf["multado"] = True; m.billetera -= C.MULTA
            if self.rng.random() < 0.03:                      # evento aleatorio de penalización
                ev = int(self.rng.integers(len(EVENTOS))); inf["evento"] = EVENTOS[ev]
                m.eventos += 1; m.eventos_dia += 1; self.eventos_total += 1
                if ev == 2: m.billetera -= float(self.rng.integers(40, 120)); m.estres += 8        # atraco
                elif ev == 3: inf["ingreso"] = 0.0; m.estres += 6                                  # aparición fantasma
                else: inf["ingreso"] *= 0.4; m.combustible = max(0.0, m.combustible - 3)          # bloqueos / entradas / cortes
            if inf["evento"]:
                self.visual_eventos.append({"mini": m.idx + 1, "nombre": inf["evento"]})
            m.ingreso += inf["ingreso"]; m.pasajeros += inf["pax"]; m.ingreso_dia += inf["ingreso"]; m.billetera += inf["ingreso"]
            m.ganancia_maxima = max(m.ganancia_maxima, m.billetera - m.billetera_inicial)
            m.faltas += fl; self.faltas += fl
            m.integridad = max(0.0, m.integridad)
            if m.integridad <= 0 and self.modo == "simulacion": self._eliminar(m, "unidad destruida")
            if m.integridad <= 0 and self.modo != "simulacion": m.integridad = 40.0
        self.rep = float(np.clip(self.rep, 0, C.REP_MAX))
        if not tr.activo and not self.transito_manual and self.faltas >= C.LIMITE_FALTAS: self._activar_transito()
        # ---- fase D: arresto
        arrestado = None; rec_t = -0.05
        if tr.activo and objetivo is not None and not objetivo.termino and objetivo.estado == "activo":
            inf = next(i for i in infos if i["mini"] is objetivo)
            inf["huyo"] = inf["acc"].nombre == "huir_transito"
            distancia = abs(objetivo.pos - tr.pos)
            distancia = min(distancia, ciu.largo_total - distancia)
            if objetivo.buscado > C.BUSCADO_ARRESTO and distancia < 8.0:
                p = 0.18 * (1.5 if inf["crimen"] or inf["accidente"] else 1.0) * (1.3 if acc_t == 4 and inf["tramo"]["semaforo"] else 1.0)
                p *= 0.4 if inf["huyo"] else 1.0
                p *= 1 + min(0.5, (objetivo.buscado - 5) * 0.1)
                p *= max(0.2, 1.0 - distancia / 10.0)
                if self.rng.random() < min(0.75, p):
                    arrestado = objetivo; rec_t += 10 + objetivo.buscado
            elif objetivo.buscado <= C.BUSCADO_ARRESTO: rec_t -= 1.0
            else: rec_t -= 0.25
            rec_t -= 0.3 * sum(i["crimen"] for i in infos)
        if arrestado is not None: self._arrestar(arrestado); tr.ultimo_exito = 1
        else: tr.ultimo_exito = 0
        if tr.activo and est_t is not None:
            if self.aprende_t: tr.cerebro.actualizar_q(est_t, acc_t, rec_t, self._estado_transito(franja), range(N_ACC_TRANSITO))
            tr.recompensa_total += rec_t
            if self.registrar:
                tr.bitacora.append((self.dia, t, acc_t, objetivo.idx if objetivo else -1, round(rec_t, 2), int(arrestado is not None)))
        # ---- fase E: recompensas y bitácora
        d_rep = self.rep - rep0
        for inf in infos:
            m, acc = inf["mini"], inf["acc"]
            repetidas = sum(1 for x in m.recientes if x == inf["a"]); saciedad = 0.85 ** repetidas; m.recientes.append(inf["a"])
            if acc.tipo == "neutro":
                r = C.ESCALA_RECOMPENSA * acc.ganancia * saciedad
            else:
                r = C.ESCALA_RECOMPENSA * (m.pesos[acc.tipo] * acc.ganancia * saciedad - acc.penalizacion * m.aversion)
            if acc.nombre == "terminar_turno":   # abandonar el turno cuesta ingresos futuros; sólo compensa un fin de semana sin presión
                r -= 0.5 * (C.TICKS - t) / C.TICKS * (1 + self._presion(m)) - (0.3 if dsem >= 5 and self._presion(m) == 0 else 0)
            r += inf["ingreso"] / 12.0 - inf["gasto"] / 12.0 - (3.0 if inf["accidente"] else 0) - (8.0 if inf["muerte"] else 0)
            r -= 0.02 * max(0.0, m.buscado - 2) + 0.8 * acc.buscado     # costo esperado de ser "buscado" (arresto futuro)
            r += 1.0 * inf["vueltas"] - (1.0 if inf["multado"] else 0) - 0.03 * self._presion(m)
            if inf["peatones"]:
                r += 1.25 * min(inf["peatones"], 3) if acc.nombre == "ceder_paso" else -0.2 * min(inf["peatones"], 3)
            r += m.lam * C.PESO_COLECTIVO * d_rep / len(trabajadores)   # término colectivo
            if inf["evento"]: r -= 0.5
            m.pendiente = (inf["s"], inf["a"], r)
            if arrestado is m: m.pendiente = (m.pendiente[0], m.pendiente[1], m.pendiente[2] - 30.0)
            if self.registrar:
                m.bitacora.append((self.dia, t, acc.nombre, acc.tipo, inf["pax"], round(inf["ingreso"], 1), round(m.buscado, 2),
                                   round(m.combustible, 1), round(m.integridad, 1), inf["evento"] or "", round(r, 3),
                                   inf["peatones"], inf["trafico"]))

    # ------------------------------------------------------------ cambios de estado
    def _arrestar(self, m):
        dias_prision, dias_malus = (C.DIAS_PRISION, C.DIAS_MALUS) if self.modo == "simulacion" else (3, 0)
        m.estado = "prision"; m.trabajando = False; m.preso_hasta = self.dia + dias_prision
        m.malus_hasta = m.preso_hasta + dias_malus; m.buscado = 0.0; m.arrestos += 1
        self.transito.arrestos += 1; self.rep = max(0.0, self.rep - C.PENALIZACION_REP_ARRESTO)

    def _eliminar(self, m, motivo):
        if m.estado in ("eliminado", "abandono"): return
        m.estado = "abandono" if motivo.startswith("abandono") else "eliminado"; m.trabajando = False; m.termino = True
        m.dia_fin = self.dia; m.motivo_fin = motivo
        if m.pendiente is not None and self.aprende_m:
            ps, pa, pr = m.pendiente; m.cerebro.actualizar_sarsa(ps, pa, pr - 60.0, 0, 0, terminal=True); m.pendiente = None

    def _iniciar_dia(self, dsem):
        entre_semana = dsem < 5
        self.cupo = int(self.rng.normal(C.CUPO_ENTRE_SEMANA if entre_semana else C.CUPO_FIN_SEMANA, 40))
        for m in self.minis:
            if m.estado == "prision" and self.dia >= m.preso_hasta: m.estado = "activo"
            m.trabajando = m.estado == "activo" and not (entre_semana and dsem == m.dia_restriccion)
            m.termino = False; m.omite_sind = m.omite_hogar = m.ticks_trabajo = 0; m.ingreso_dia = 0.0; m.eventos_dia = 0
            m.comodidad *= 0.97
            if m.personalidad == "volatil":     # la personalidad volátil cambia sus pesos cada día
                m.pesos = {k: v * float(np.exp(self.rng.normal(0, 0.5))) for k, v in m.pesos_base.items()}
            if m.estado in ("eliminado", "abandono"): m.trabajando = False

    def _terminar_dia(self, dsem):
        a, faltan, n = self.anio_de(self.dia); cuota_dia = self.cuota / n
        for m in self.minis:
            if m.estado in ("eliminado", "abandono"): continue
            frac_s = m.omite_sind / m.ticks_trabajo if m.ticks_trabajo else 0.0
            frac_h = m.omite_hogar / m.ticks_trabajo if m.ticks_trabajo else 0.0
            impuesto = C.TASA_IMPUESTO * m.ingreso_dia
            repuestos = C.TASA_REPUESTOS * m.ingreso_dia * (1 + (100 - m.integridad) / 100)
            hogar_debido = m.familia * 1.5 * (0.5 if m.estado == "prision" else 1.0)
            hogar_pagado = hogar_debido * (1 - frac_h)
            sind_pagado = cuota_dia * (1 - frac_s) if m.estado == "activo" else 0.0
            reparacion = min(max(0.0, 80 - m.integridad), 10.0); m.integridad += reparacion
            m.billetera -= impuesto + repuestos + hogar_pagado + sind_pagado + reparacion * C.COSTO_REPARACION_POR_PT
            m.deuda_sindicato += cuota_dia - sind_pagado; self.cuotas_recaudadas += sind_pagado
            m.deuda_maxima = max(m.deuda_maxima, m.deuda_sindicato, -min(0.0, m.billetera))
            m.buscado = max(0.0, m.buscado - 0.25)
            p = self._presion(m)                           # estrés por presión económica
            m.estres = float(np.clip(m.estres + 1.5 * p + (frac_h * 5) - 2 - (4 if dsem >= 5 else 0), 0, 100))
            if m.estres > 95 and self.rng.random() < 0.02 and self.modo == "simulacion":
                self._eliminar(m, "abandono por sobrepresión")
        if self.modo != "simulacion" and self.dia % 90 == 89:   # en pre-entreno se reinician billeteras para ver todos los niveles de presión
            for m in self.minis: m.billetera = float(self.rng.uniform(300, 7000)); m.deuda_sindicato = 0.0
        # buen servicio: el sindicato recupera reputación lentamente mientras haya minis operando
        self.rep = min(C.REP_MAX, self.rep + C.RECUPERACION_REP * sum(m.estado == "activo" for m in self.minis) / len(self.minis))
        if faltan == 1 and self.modo == "simulacion": self._cierre_anio(a)
        if self.rep <= 0 and self.modo == "simulacion":
            self.terminado = True; self.motivo_fin = "reputación del sindicato en 0"
        self.diario.append(dict(dia=self.dia, rep=self.rep, faltas=self.faltas, transito=int(self.transito.activo),
                                ingreso=sum(m.ingreso_dia for m in self.minis), eventos=sum(m.eventos_dia for m in self.minis),
                                activos=sum(m.estado == "activo" for m in self.minis), arrestos=self.transito.arrestos,
                                accidentes=sum(m.accidentes for m in self.minis), crimenes=sum(m.crimenes for m in self.minis),
                                cupo_restante=self.cupo))

    def _cierre_anio(self, a):
        vivos = [m for m in self.minis if m.estado in ("activo", "prision")]
        pueden = [m for m in vivos if m.billetera >= m.deuda_sindicato]
        # metas individuales del año (6): ahorro, vueltas, integridad, aporte al sindicato, aporte al hogar, historial limpio
        for m in self.minis:
            if m.estado in ("eliminado", "abandono") and m.dia_fin is not None and m.dia_fin < self.dia - 365:
                m.metas_anio.append(0.0); continue
            g = [np.clip((m.billetera - m.billetera_anio0) / C.CUOTA, 0, 1), np.clip(m.vueltas_anio / 400, 0, 1),
                 np.clip(m.integridad / 60, 0, 1), 1 - m.omite_sind_anio / max(1, m.ticks_anio),
                 1 - m.omite_hogar_anio / max(1, m.ticks_anio), 1.0 if m.buscado < 2 else 0.0]
            m.metas_anio.append(float(np.mean(g)) if m.estado != "eliminado" else 0.0)
        if vivos and not pueden:      # nadie pudo pagar: nadie se elimina, pero hay deuda y penalización pasiva
            self.pen_pasiva = 0.9
            for m in vivos:
                if m.pendiente and self.aprende_m: m.pendiente = (m.pendiente[0], m.pendiente[1], m.pendiente[2] - 10)
        else:
            self.pen_pasiva = 1.0
            for m in vivos:
                if m in pueden:
                    m.billetera -= m.deuda_sindicato; self.cuotas_recaudadas += m.deuda_sindicato; m.deuda_sindicato = 0.0
                    if m.pendiente: m.pendiente = (m.pendiente[0], m.pendiente[1], m.pendiente[2] + 25.0)
                else: self._eliminar(m, f"no pagó la cuota del año {a + 1}")
        if self.rep < C.REP_MIN_REQ: self.cuota *= C.PENALIZACION_CUOTA
        self.registro_anual.append(dict(anio=a + 1, rep=self.rep, cuota=self.cuota,
                                        sobrevivientes=sum(m.estado in ("activo", "prision") for m in self.minis),
                                        recaudado=self.cuotas_recaudadas))
        for m in self.minis:
            m.vueltas_anio = 0; m.omite_sind_anio = 0; m.omite_hogar_anio = 0; m.ticks_anio = 0; m.billetera_anio0 = m.billetera
        if not any(m.estado in ("activo", "prision") for m in self.minis):
            self.terminado = True; self.motivo_fin = "todos fueron eliminados"

    # ------------------------------------------------------------ bucle principal
    def correr(self, n_dias, plan_eps=None, verbose=True):
        """plan_eps(k, n_dias) -> ε de los minis en el día k del tramo (para decaimiento de exploración)."""
        for k in range(n_dias):
            if self.terminado: break
            if plan_eps: self.eps_m = plan_eps(k, n_dias)
            dsem = self.dia % 7; self._iniciar_dia(dsem)
            for t in range(C.TICKS): self.tick(t, dsem)
            self._terminar_dia(dsem); self.dia += 1
            if verbose and self.dia % 365 == 0:
                print(f"  día {self.dia:>4} | rep={self.rep:.2f} | faltas={self.faltas} | tránsito={'ACTIVO' if self.transito.activo else 'aún no'} | "
                      f"activos={sum(m.estado == 'activo' for m in self.minis)} | arrestos={self.transito.arrestos}")

    # ------------------------------------------------------------ resultado final
    def resultado(self):
        vivos = [m for m in self.minis if m.estado in ("activo", "prision")]
        def puntaje(m):
            anios = len(C.DIAS_POR_ANO); g = m.metas_anio + [0.0] * (anios - len(m.metas_anio))
            return float(np.mean(g))
        puntajes = {m.idx: puntaje(m) for m in self.minis}
        meta_cumplida = self.cuotas_recaudadas >= C.META_SINDICATO_RATIO * len(self.minis) * C.CUOTA * len(C.DIAS_POR_ANO)
        ganadores = None
        if self.terminado or not vivos: final = f"MALO: todos pierden ({self.motivo_fin or 'sin sobrevivientes'})"
        elif self.rep < C.REP_MIN_REQ: final = "AMARGO: sobreviven, pero el sindicato está desprestigiado (rep < 4.2) y nadie gana"
        else:
            mejor = max(vivos, key=lambda m: puntajes[m.idx])
            empatados = [m for m in vivos if abs(puntajes[m.idx] - puntajes[mejor.idx]) < 0.03]
            if len(empatados) > 1: final = "BUENO: varios sobreviven empatados en cumplimiento de metas"; ganadores = [m.idx for m in empatados]
            else: final = "GANADOR ÚNICO"; ganadores = [mejor.idx]
            if not meta_cumplida: final += " (meta colectiva del sindicato NO alcanzada)"
        esperado = self.eventos_total / max(1, len(self.minis))
        suerte = {m.idx: float(np.clip(1 - m.eventos / max(1.0, esperado * 1.5), 0, 1)) for m in self.minis}
        return dict(final=final, ganadores=ganadores, puntajes=puntajes, suerte=suerte, rep=self.rep,
                    winner_balances={m.idx: round(m.billetera, 2) for m in vivos if ganadores and m.idx in ganadores},
                    losers=[dict(id=m.idx + 1, nombre=m.nombre, dia=m.dia_fin, ronda=(m.dia_fin or 0) // 365 + 1,
                                 motivo=m.motivo_fin, balance=round(m.billetera, 2))
                            for m in self.minis if m.estado in ("eliminado", "abandono")],
                    maxima_deuda=max((m.deuda_maxima for m in self.minis), default=0.0),
                    maxima_deuda_quien=max(self.minis, key=lambda m: m.deuda_maxima).nombre if self.minis else None,
                    maxima_ganancia=max((m.ganancia_maxima for m in self.minis), default=0.0),
                    maxima_ganancia_quien=max(self.minis, key=lambda m: m.ganancia_maxima).nombre if self.minis else None,
                    cuotas_recaudadas=self.cuotas_recaudadas, meta_cumplida=bool(meta_cumplida), faltas=self.faltas,
                    dia_transito=self.transito.dia_activacion)

