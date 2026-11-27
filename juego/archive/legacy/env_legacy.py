"""Entorno multiagente: 5 minibuseros (SARSA) + Tránsito (Q-learning) en una ruta de La Paz."""
import numpy as np
from collections import deque
import config as C
from city import City
from rl import TabularAgent, encode

ACT = C.ACTIONS
NA = len(ACT)
AI = C.A_IDX
DIMS_M = (3, 2, 3, 2, 3, 2, 2, 2, 2)   # combustible, tráfico_pesado, buscado, perseguido, presión, integridad, semáforo, cd_ok, atajo_conocido
ESTADOS_M = int(np.prod(DIMS_M))
DIMS_T = (4, 3, 3, 2)
ESTADOS_T = int(np.prod(DIMS_T))
ACCIONES_T = 5
CRITICAS = {AI["estrellar_unidad"], AI["atropellar_pasajero"]}   # sin exploración aleatoria en la simulación real
EVENTOS = ["corte_de_via", "entrada_folklorica", "atraco", "aparicion_fantasma", "bloqueo_vecinal"]


def prioridad_accion(P):
    """Q inicial = recompensa inmediata esperada de cada acción según la tabla y la personalidad (la 'identidad')."""
    v = np.zeros(NA)
    for i, a in enumerate(ACT):
        if a.tipo == "neutro":
            v[i] = C.REWARD_SCALE * a.gain
        else:
            v[i] = C.REWARD_SCALE * (P["W"][a.tipo] * a.gain - a.pen * P["risk_av"]) - 0.8 * a.wanted
    v[AI["estrellar_unidad"]] -= 3.0
    v[AI["atropellar_pasajero"]] -= 11.0
    return v * 3.0


class Minibusero:
    def __init__(self, idx, perfil, cerebro, rng):
        self.idx, self.perfil, self.cerebro, self.rng = idx, perfil, cerebro, rng
        self.nombre = perfil["name"]
        self.pers = perfil["pers"]
        P = C.PERSONALITIES[self.pers]
        self.aggr, self.risk_av, self.lam, self.W_base = P["aggr"], P["risk_av"], P["lam"], P["W"]
        self.W = dict(self.W_base)
        self.vstd, self.vmax, self.familia = perfil["vstd"], perfil["vmax"], perfil["family"]
        self.restriccion = idx % 5                       # día sin circular (lun..vie)
        self.estado = "activo"
        self.billetera = 3000.0
        self.combustible = 100.0
        self.cd = 99
        self.integ = 100.0
        self.buscado = 0.0
        self.estres = 20.0
        self.comodidad = 0.0
        self.pos = rng.random() * 3
        self.precision = 100.0
        self.conocidos = set()
        self.deuda_sindicato = 0.0
        self.prision_hasta = -1
        self.malus_hasta = -1
        self.pend = None
        self.recientes = deque(maxlen=4)
        self.conteos = np.zeros(NA)
        self.eventos = 0
        self.faltas = 0
        self.arrestos = 0
        self.vueltas = 0
        self.ingreso = 0.0
        self.pasajeros = 0
        self.delitos = 0
        self.accidentes = 0
        self.no_aporte_u = 0
        self.no_aporte_h = 0
        self.ticks_trabajo = 0
        self.metas_ano = []
        self.vueltas_a = 0
        self.no_aporte_u_a = 0
        self.no_aporte_h_a = 0
        self.tt_a = 0
        self.billetera_a0 = self.billetera
        self.dia_fin = None
        self.motivo_fin = ""
        self.ingreso_dia = 0.0
        self.ev_dia = 0
        self.ultimo_tick_delito = -99
        self.bitacora = []
        self.trabajando = False
        self.finalizo = False

    def atractivo(self, extra=0.0):
        return float(np.clip(1.0 + self.comodidad + extra, 0.3, 2.0))


class Transito:
    def __init__(self, cerebro):
        self.cerebro = cerebro
        self.activo = False
        self.objetivo = None
        self.arrestos = 0
        self.dia_activacion = None
        self.ultimo_ok = 0
        self.pend = None
        self.bitacora = []
        self.suma_recompensa = 0.0


class Simulacion:
    def __init__(self, semilla=0, modo="sim", Q_minis=None, Q_transito=None, aprender_minis=True,
                 aprender_transito=True, eps_minis=0.05, eps_transito=0.05, registrar=True):
        """modo: 'pretrain' (sin eliminación; Tránsito presente), 'pretrain_transit', 'sim'."""
        self.rng = np.random.default_rng(semilla)
        self.modo = modo
        self.ciudad = City()
        self.aprender_m = aprender_minis
        self.aprender_t = aprender_transito
        self.eps_m = eps_minis
        self.eps_t = eps_transito
        self.registrar = registrar
        self.minis = []
        for i, p in enumerate(C.PROFILES):
            cerebro = TabularAgent(ESTADOS_M, NA, "sarsa", self.rng, C.ALPHA, C.GAMMA)
            if Q_minis is not None:
                cerebro.Q = Q_minis[i].copy()
            else:
                cerebro.Q[:] = prioridad_accion(C.PERSONALITIES[p["pers"]])
            self.minis.append(Minibusero(i, p, cerebro, self.rng))
        cerebro_t = TabularAgent(ESTADOS_T, ACCIONES_T, "q", self.rng, C.ALPHA, C.GAMMA)
        if Q_transito is not None:
            cerebro_t.Q = Q_transito.copy()
        self.transito = Transito(cerebro_t)
        self.dia = 0
        self.rep = C.REP_MAX
        self.faltas = 0
        self.terminado = False
        self.motivo_fin = ""
        self.cuota = C.QUOTA
        self.pen_pasiva = 1.0
        self.recaudado_sindicato = 0.0
        self.gtick = 0
        self.diario = []
        self.bitacora_anual = []
        self.total_eventos = 0
        self.bolsa = 0
        if modo in ("pretrain", "pretrain_transit"):
            self._activar_transito()

    # ------------------------------------------------------------ utilidades
    def ano_de(self, d):
        if self.modo != "sim":
            d = d % 365
        acum = 0
        for a, n in enumerate(C.YEAR_DAYS):
            acum += n
            if d < acum:
                return a, acum - d, n
        return len(C.YEAR_DAYS) - 1, 0, C.YEAR_DAYS[-1]

    def _activar_transito(self):
        if not self.transito.activo:
            self.transito.activo = True
            self.transito.dia_activacion = self.dia

    def _trafico(self, t, dsm):
        base = 2 if (t in (2, 3, 12, 13)) else (1 if t in (1, 4, 5, 11, 14) else 0)
        base += 0 if dsm < 5 else -1
        return int(np.clip(base + (self.rng.random() < 0.15), 0, 2))

    def _presion(self, m):
        """Obligaciones de los próximos 30 días (cuota + hogar + deuda) vs. billetera."""
        _, _, n = self.ano_de(self.dia)
        necesario = m.deuda_sindicato + self.cuota * 30 / n + m.familia * 30
        razon = m.billetera / max(necesario, 1.0)
        return 2 if razon < 0.3 else (1 if razon < 1.0 else 0)

    def _estado(self, m, t, trafico, objetivo):
        seg = self.ciudad.seg_at(m.pos)
        nc = 0 if m.combustible <= 10 else 1 if m.combustible <= 45 else 2
        nb = 0 if m.buscado < 2 else 1 if m.buscado <= C.WANTED_ARREST else 2
        return encode((
            nc,
            int(trafico == 2),
            nb,
            int(objetivo),
            self._presion(m),
            int(m.integ > 50),
            int(self.ciudad.segs[seg]["light"]),
            int(m.cd >= C.REFUEL_COOLDOWN),
            int(seg in m.conocidos),
        ), DIMS_M)

    def _validas(self, m, objetivo):
        if m.combustible <= 0:
            return [AI["cargar_combustible"]] if m.cd >= C.REFUEL_COOLDOWN else [AI["terminar_turno"]]
        validas = []
        for i, a in enumerate(ACT):
            if a.name == "cargar_combustible" and not (m.cd >= C.REFUEL_COOLDOWN and m.combustible <= 65):
                continue
            if a.name == "huir_transito" and not objetivo:
                continue
            validas.append(i)
        return validas

    # ------------------------------------------------------------ Tránsito
    def _estado_t(self, tb):
        b = sorted([m.buscado for m in self.minis if m.trabajando and not m.finalizo], reverse=True) or [0]
        maximo = 0 if b[0] < 2 else 1 if b[0] <= 5 else 2 if b[0] <= 8 else 3
        n = sum(x > C.WANTED_ARREST for x in b)
        return encode((maximo, min(n, 2), tb, self.transito.ultimo_ok), DIMS_T)

    def _elegir_objetivo(self, at, trabajadores):
        por_b = sorted(trabajadores, key=lambda m: -m.buscado)
        if at == 0:
            return por_b[0]
        if at == 1:
            return por_b[1] if len(por_b) > 1 else por_b[0]
        if at == 2:
            ultimo = max(trabajadores, key=lambda m: m.ultimo_tick_delito)
            return ultimo if ultimo.ultimo_tick_delito > self.gtick - 8 else trabajadores[int(self.rng.integers(len(trabajadores)))]
        if at == 4:
            con_luz = [m for m in por_b if self.ciudad.segs[self.ciudad.seg_at(m.pos)]["light"]]
            return con_luz[0] if con_luz else trabajadores[int(self.rng.integers(len(trabajadores)))]
        return trabajadores[int(self.rng.integers(len(trabajadores)))]

    # ------------------------------------------------------------ un tick
    def tick(self, t, dsm):
        ciudad = self.ciudad
        tb = t * 3 // C.TICKS
        self.gtick += 1
        trabajadores = [m for m in self.minis if m.trabajando and not m.finalizo]
        if not trabajadores:
            return
        trafico = self._trafico(t, dsm)
        rep0 = self.rep
        tr = self.transito
        objetivo = None
        et = at = None
        if tr.activo:
            et = self._estado_t(tb)
            at = tr.cerebro.act(et, range(ACCIONES_T), self.eps_t)
            objetivo = self._elegir_objetivo(at, trabajadores)
        tr.objetivo = objetivo
        infos = []

        # ---- fase A: decisión + movimiento
        for k in self.rng.permutation(len(trabajadores)):
            m = trabajadores[k]
            es_objetivo = (m is objetivo)
            s = self._estado(m, t, trafico, es_objetivo)
            validas = self._validas(m, es_objetivo)
            expl = [x for x in validas if x not in CRITICAS] if self.modo == "sim" else validas
            a = m.cerebro.act(s, validas, self.eps_m, expl)
            if m.pend is not None and self.aprender_m:
                ps, pa, pr = m.pend
                m.cerebro.update_sarsa(ps, pa, pr, s, a)
            act = ACT[a]
            m.conteos[a] += 1
            m.ticks_trabajo += 1
            m.tt_a += 1
            seg_i = ciudad.seg_at(m.pos)
            seg = ciudad.segs[seg_i]
            info = dict(
                m=m, s=s, a=a, act=act, objetivo=es_objetivo,
                pax=0, ingreso=0.0, accidente=False, muerte=False, delito=False,
                vueltas=0, huyo=False, multado=False, evento=None
            )
            m.cd = min(99, m.cd + 1)
            cruzo_rojo = False
            if act.name == "cargar_combustible":
                m.combustible = 100.0
                m.cd = 0
                m.billetera -= C.FUEL_COST
                v = 0.0
            elif act.name == "terminar_turno":
                m.finalizo = True
                v = 0.0
            else:
                ft = (1.0, 0.8, 0.6)[trafico]
                v = min(m.vmax, m.vstd * act.speed * ft)
                if seg["light"]:
                    if act.name in C.LAWFUL:
                        v *= 0.9
                    else:
                        cruzo_rojo = True
                bono = 0.0
                if act.name == "tomar_atajo" and seg_i in ciudad.shortcut:
                    if seg_i in m.conocidos:
                        bono = ciudad.shortcut[seg_i][1]
                    elif self.rng.random() < 0.12:
                        m.conocidos.add(seg_i)
                        bono = ciudad.shortcut[seg_i][1]
                        m.precision -= 3
                        info["encontrado"] = seg_i
                    else:
                        m.precision -= 0.5
                elif act.name == "tomar_atajo":
                    m.precision -= 0.5
                anterior = m.pos
                m.pos += v * C.TICK_H + bono
                nv = int(m.pos // ciudad.L) - int(anterior // ciudad.L)
                info["vueltas"] = nv
                m.vueltas += nv
                m.vueltas_a += nv
                m.combustible -= 5.0 * (v / m.vstd) ** 1.2 * (0.8 if act.name == "limite_velocidad" else 1.0) if v > 0 else 0
                m.combustible = max(0.0, m.combustible)
                if act.cost:
                    m.billetera -= act.cost
                if act.name == "aseo_unidad":
                    m.comodidad = min(0.5, m.comodidad + 0.12)
            info.update(v=v, rojo=cruzo_rojo, seg=seg)
            infos.append(info)

        # ---- fase B: pasajeros (finitos y en competencia)
        ticks_restantes = max(1, C.TICKS - t)
        disp = self.bolsa / ticks_restantes * (1.25 if trafico == 2 else 1.0)
        pesos = []
        for inf in infos:
            m = inf["m"]
            if inf["v"] <= 0:
                pesos.append(0.0)
                continue
            w = m.atractivo(inf["act"].appeal + (0.1 if self.rep >= 4 else -0.1 if self.rep < C.REP_ATROZ else 0)) \
                - (inf["v"] / m.vstd) ** 0.6 * inf["seg"]["demand"] * (1.0 if m.integ > 30 else 0.7)
            pesos.append(w)
        total_w = sum(pesos)
        for inf, w in zip(infos, pesos):
            if w <= 0 or total_w <= 0:
                continue
            m = inf["m"]
            malus = C.MALUS_FACTOR if self.dia < m.malus_hasta else 1.0
            p = int(min(30, self.rng.poisson(disp * w / total_w * malus * self.pen_pasiva)))
            p = min(p, self.bolsa)
            self.bolsa -= p
            inf["pax"] = p
            inf["ingreso"] = p * C.FARE

        # ---- fase C: accidentes, eventos, faltas, reputación
        for inf in infos:
            m, act = inf["m"], inf["act"]
            fl = 0
            if act.name == "no_aportar_sindicato":
                m.no_aporte_u += 1
                m.no_aporte_u_a += 1
            if act.name == "no_aportar_hogar":
                m.no_aporte_h += 1
                m.no_aporte_h_a += 1
            if inf["v"] > 0 or act.name in ("estrellar_unidad", "atropellar_pasajero"):
                p = 0.0008 + act.risk + (0.006 if inf["rojo"] else 0) + 0.001 * trafico
                p *= (0.6 + m.aggr) * (1.5 if m.integ < 35 else 1.0) * (1.3 if inf["v"] > m.vstd * 1.3 else 1.0)
                forzado = act.name in ("estrellar_unidad", "atropellar_pasajero")
                if forzado or self.rng.random() < max(p, 0):
                    inf["accidente"] = True
                    m.accidentes += 1
                    sev = float(self.rng.integers(5, 25))
                    m.integ -= act.integ if forzado else sev
                    m.buscado += 0.4
                    fl += 1
                    self.rep -= 0.01
                    inf["ingreso"] *= 0.5
                    m.estres += 4
                    if act.name == "atropellar_pasajero" or self.rng.random() < 0.004:
                        inf["muerte"] = True
                        m.buscado += 5.0 if act.name != "atropellar_pasajero" else 0
                        fl += 3
                        self.rep -= C.ARREST_REP_PENALTY
                        inf["ingreso"] = 0.0
            m.integ -= act.integ if act.name not in ("estrellar_unidad", "atropellar_pasajero") else 0
            if act.tipo == "criminal":
                inf["delito"] = True
                m.delitos += 1
                fl += 1
                m.ultimo_tick_delito = self.gtick
            m.buscado += act.wanted if act.tipo != "criminal" or act.name == "conduccion_temeraria" else act.wanted
            self.rep += act.rep * C.REP_SCALE
            m.estres = float(np.clip(m.estres + act.stress, 0, 100))
            if multa_transito(self, inf, objetivo):
                inf["multado"] = True
                m.billetera -= C.FINE
            if self.rng.random() < 0.03:
                ev = int(self.rng.integers(len(EVENTOS)))
                inf["evento"] = EVENTOS[ev]
                m.eventos += 1
                m.ev_dia += 1
                self.total_eventos += 1
                if ev == 2:
                    m.billetera -= float(self.rng.integers(40, 120))
                    m.estres += 8
                elif ev == 3:
                    inf["ingreso"] = 0.0
                    m.estres += 6
                else:
                    inf["ingreso"] *= 0.4
                    m.combustible = max(0.0, m.combustible - 3)
            m.ingreso += inf["ingreso"]
            m.pasajeros += inf["pax"]
            m.ingreso_dia += inf["ingreso"]
            m.billetera += inf["ingreso"]
            m.faltas += fl
            self.faltas += fl
            m.integ = max(0.0, m.integ)
            if m.integ <= 0 and self.modo == "sim":
                self._eliminar(m, "unidad destruida")
            if m.integ <= 0 and self.modo != "sim":
                m.integ = 40.0
        self.rep = float(np.clip(self.rep, 0, C.REP_MAX))
        if not tr.activo and self.faltas >= C.FALTAS_LIMIT:
            self._activar_transito()

        # ---- fase D: arresto
        arrestado = None
        r_transito = -0.05
        if tr.activo and objetivo is not None and not objetivo.finalizo and objetivo.estado == "activo":
            inf = next(i for i in infos if i["m"] is objetivo)
            inf["huyo"] = inf["act"].name == "huir_transito"
            if objetivo.buscado > C.WANTED_ARREST:
                p = 0.18 * (1.5 if inf["delito"] or inf["accidente"] else 1.0) * (1.3 if at == 4 and inf["seg"]["light"] else 1.0)
                p *= 0.4 if inf["huyo"] else 1.0
                p *= 1 + min(0.5, (objetivo.buscado - 5) * 0.1)
                if self.rng.random() < min(0.75, p):
                    arrestado = objetivo
                    r_transito += 10 + objetivo.buscado
            else:
                r_transito -= 1.0
            r_transito -= 0.3 * sum(i["delito"] for i in infos)
        if arrestado is not None:
            self._arrestar(arrestado)
            tr.ultimo_ok = 1
        else:
            tr.ultimo_ok = 0
        if tr.activo and et is not None:
            if self.aprender_t:
                tr.cerebro.update_q(et, at, r_transito, self._estado_t(tb), range(ACCIONES_T))
            tr.suma_recompensa += r_transito
            if self.registrar:
                tr.bitacora.append((self.dia, t, at, objetivo.idx if objetivo else -1, round(r_transito, 2), int(arrestado is not None)))

        # ---- fase E: recompensas y bitácora
        drep = self.rep - rep0
        for inf in infos:
            m, act = inf["m"], inf["act"]
            n_misma = sum(1 for x in m.recientes if x == inf["a"])
            sat = 0.85 ** n_misma
            m.recientes.append(inf["a"])
            Wt = m.W[act.tipo]
            r = C.REWARD_SCALE * (Wt * act.gain * sat - act.pen * m.risk_av * (1 if act.tipo != "neutro" else 0)) if act.tipo != "neutro" else C.REWARD_SCALE * act.gain * sat
            if act.name == "terminar_turno":   # abandonar el turno cuesta ingresos futuros; sólo compensa en fin de semana sin presión
                r -= 0.5 * (C.TICKS - t) / C.TICKS * (1 + self._presion(m)) - (0.3 if dsm >= 5 and self._presion(m) == 0 else 0)
            r += inf["ingreso"] / 12.0 - (3.0 if inf["accidente"] else 0) - (8.0 if inf["muerte"] else 0)
            r -= 0.02 * max(0.0, m.buscado - 2) + 0.8 * act.wanted   # costo esperado de ser 'buscado' (arresto futuro)
            r += 1.0 * inf["vueltas"] - (1.0 if inf["multado"] else 0) - 0.03 * self._presion(m)
            r += m.lam * C.COLLECTIVE_K * drep / len(trabajadores)
            if inf["evento"]:
                r -= 0.5
            if inf["s"] is not None:
                m.pend = (inf["s"], inf["a"], r)
            if arrestado is m:
                m.pend = (m.pend[0], m.pend[1], m.pend[2] - 30.0)
            if self.registrar:
                m.bitacora.append((
                    self.dia, t, act.name, act.tipo, inf["pax"], round(inf["ingreso"], 1),
                    round(m.buscado, 2), round(m.combustible, 1), round(m.integ, 1), inf["evento"] or "", round(r, 3)
                ))

    # ------------------------------------------------------------ eventos de estado
    def _arrestar(self, m):
        dias_p, dias_m = (C.PRISON_DAYS, C.MALUS_DAYS) if self.modo == "sim" else (3, 0)
        m.estado = "prision"
        m.trabajando = False
        m.prision_hasta = self.dia + dias_p
        m.malus_hasta = m.prision_hasta + dias_m
        m.buscado = 0.0
        m.arrestos += 1
        self.transito.arrestos += 1
        self.rep = max(0.0, self.rep - C.ARREST_REP_PENALTY)

    def _eliminar(self, m, motivo):
        if m.estado in ("eliminado", "abandono"):
            return
        m.estado = "abandono" if motivo.startswith("abandono") else "eliminado"
        m.trabajando = False
        m.finalizo = True
        m.dia_fin = self.dia
        m.motivo_fin = motivo
        if m.pend is not None and self.aprender_m:
            ps, pa, pr = m.pend
            m.cerebro.update_sarsa(ps, pa, pr - 60.0, 0, 0, done=True)
            m.pend = None

    def _iniciar_dia(self, dsm):
        _, _, _ = self.ano_de(self.dia)
        entre_semana = dsm < 5
        self.bolsa = int(self.rng.normal(C.POOL_WEEKDAY if entre_semana else C.POOL_WEEKEND, 40))
        for m in self.minis:
            if m.estado == "prision" and self.dia >= m.prision_hasta:
                m.estado = "activo"
            m.trabajando = m.estado == "activo" and not (entre_semana and dsm == m.restriccion)
            m.finalizo = False
            m.no_aporte_u = m.no_aporte_h = m.ticks_trabajo = 0
            m.ingreso_dia = 0.0
            m.ev_dia = 0
            m.comodidad *= 0.97
            if m.pers == "volatil":
                m.W = {k: v * float(np.exp(self.rng.normal(0, 0.5))) for k, v in m.W_base.items()}
            if m.estado in ("eliminado", "abandono"):
                m.trabajando = False

    def _cerrar_dia(self, dsm):
        a, restantes, n = self.ano_de(self.dia)
        cd = self.cuota / n
        for m in self.minis:
            if m.estado in ("eliminado", "abandono"):
                continue
            tt = max(1, m.ticks_trabajo)
            fu = m.no_aporte_u / tt if m.ticks_trabajo else 0.0
            fh = m.no_aporte_h / tt if m.ticks_trabajo else 0.0
            impuesto = C.TAX_RATE * m.ingreso_dia
            repuestos = C.PARTS_RATE * m.ingreso_dia * (1 + (100 - m.integ) / 100)
            fam_debida = m.familia * (0.5 if m.estado == "prision" else 1.0)
            fam_pagada = fam_debida * (1 - fh)
            sin_pagada = cd * (1 - fu) if m.estado == "activo" else 0.0
            reparacion = min(max(0.0, 80 - m.integ), 10.0)
            m.integ += reparacion
            m.billetera -= impuesto + repuestos + fam_pagada + sin_pagada + reparacion * C.REPAIR_COST_PER_PT
            m.deuda_sindicato += cd - sin_pagada
            self.recaudado_sindicato += sin_pagada
            m.buscado = max(0.0, m.buscado - 0.25)
            # estrés y presión
            p = self._presion(m)
            m.estres = float(np.clip(m.estres + 1.5 * p + (fh * 5) - 2 - (4 if dsm >= 5 else 0), 0, 100))
            if m.estres > 95 and self.rng.random() < 0.02 and self.modo == "sim":
                self._eliminar(m, "abandono por sobrepresión")
        if self.modo != "sim" and self.dia % 90 == 89:
            for m in self.minis:
                m.billetera = float(self.rng.uniform(300, 7000))
                m.deuda_sindicato = 0.0
        # sindicato: ¿cierre de año?
        # buen servicio: el sindicato recupera reputación lentamente mientras haya minis operando
        self.rep = min(C.REP_MAX, self.rep + C.REP_RECOVERY * sum(m.estado == "activo" for m in self.minis) / len(self.minis))
        if restantes == 1 and self.modo == "sim":
            self._cerrar_ano(a)
        if self.rep <= 0 and self.modo == "sim":
            self.terminado = True
            self.motivo_fin = "reputación del sindicato en 0"
        self.diario.append(dict(
            dia=self.dia, rep=self.rep, faltas=self.faltas, transito=int(self.transito.activo),
            ingreso=sum(m.ingreso_dia for m in self.minis), eventos=sum(m.ev_dia for m in self.minis),
            activos=sum(m.estado == "activo" for m in self.minis), arrestos=self.transito.arrestos,
            accidentes=sum(m.accidentes for m in self.minis), delitos=sum(m.delitos for m in self.minis),
            bolsa_restante=self.bolsa
        ))

    def _cerrar_ano(self, a):
        vivos = [m for m in self.minis if m.estado in ("activo", "prision")]
        pueden = [m for m in vivos if m.billetera >= m.deuda_sindicato]
        # metas individuales del año
        for m in self.minis:
            if m.estado in ("eliminado", "abandono") and m.dia_fin is not None and m.dia_fin < self.dia - 365:
                m.metas_ano.append(0.0)
                continue
            g = [
                np.clip((m.billetera - m.billetera_a0) / C.QUOTA, 0, 1),
                np.clip(m.vueltas_a / 400, 0, 1),
                np.clip(m.integ / 60, 0, 1),
                1 - m.no_aporte_u_a / max(1, m.tt_a),
                1 - m.no_aporte_h_a / max(1, m.tt_a),
                1.0 if m.buscado < 2 else 0.0,
            ]
            m.metas_ano.append(float(np.mean(g)) if m.estado != "eliminado" else 0.0)
        if vivos and not pueden:
            self.pen_pasiva = 0.9
            for m in vivos:
                if m.pend and self.aprender_m:
                    m.pend = (m.pend[0], m.pend[1], m.pend[2] - 10)
        else:
            self.pen_pasiva = 1.0
            for m in vivos:
                if m in pueden:
                    m.billetera -= m.deuda_sindicato
                    self.recaudado_sindicato += m.deuda_sindicato
                    m.deuda_sindicato = 0.0
                    if m.pend:
                        m.pend = (m.pend[0], m.pend[1], m.pend[2] + 25.0)
                else:
                    self._eliminar(m, f"no pagó la cuota del año {a + 1}")
        if self.rep < C.REP_MIN_REQ:
            self.cuota *= C.QUOTA_PENALTY
        self.bitacora_anual.append(dict(
            ano=a + 1, rep=self.rep, cuota=self.cuota,
            sobrevivientes=sum(m.estado in ("activo", "prision") for m in self.minis),
            recaudado=self.recaudado_sindicato
        ))
        for m in self.minis:
            m.vueltas_a = 0
            m.no_aporte_u_a = 0
            m.no_aporte_h_a = 0
            m.tt_a = 0
            m.billetera_a0 = m.billetera
        if not any(m.estado in ("activo", "prision") for m in self.minis):
            self.terminado = True
            self.motivo_fin = "todos fueron eliminados"

    # ------------------------------------------------------------ bucle
    def ejecutar(self, n_dias, prog_eps=None, verboso=True):
        for k in range(n_dias):
            if self.terminado:
                break
            if prog_eps:
                self.eps_m = prog_eps(k, n_dias)
            dsm = self.dia % 7
            self._iniciar_dia(dsm)
            for t in range(C.TICKS):
                self.tick(t, dsm)
            self._cerrar_dia(dsm)
            self.dia += 1
            if verboso and self.dia % 365 == 0:
                print(
                    f"  día {self.dia:>4} | rep={self.rep:.2f} | faltas={self.faltas} | "
                    f"tránsito={'ON' if self.transito.activo else 'off'} | "
                    f"activos={sum(m.estado == 'activo' for m in self.minis)} | arrestos={self.transito.arrestos}"
                )

    # ------------------------------------------------------------ resultado final
    def resultado(self):
        sobrevivientes = [m for m in self.minis if m.estado in ("activo", "prision")]

        def puntaje(m):
            anos = len(C.YEAR_DAYS)
            g = m.metas_ano + [0.0] * (anos - len(m.metas_ano))
            return float(np.mean(g))

        puntajes = {m.idx: puntaje(m) for m in self.minis}
        meta_cumplida = self.recaudado_sindicato >= C.UNION_GOAL_RATIO * len(self.minis) * C.QUOTA * len(C.YEAR_DAYS)
        ganador = None
        final = ""
        if self.terminado or not sobrevivientes:
            final = f"MALO: todos pierden ({self.motivo_fin or 'sin sobrevivientes'})"
        elif self.rep < C.REP_MIN_REQ:
            final = "AMARGO: sobreviven, pero el sindicato está desprestigiado (rep < 4.2) y nadie gana"
        else:
            mejor = max(sobrevivientes, key=lambda m: puntajes[m.idx])
            empates = [m for m in sobrevivientes if abs(puntajes[m.idx] - puntajes[mejor.idx]) < 0.03]
            if len(empates) > 1:
                final = "BUENO: varios sobreviven empatados en cumplimiento de metas"
                ganador = [m.idx for m in empates]
            else:
                final = "GANADOR ÚNICO"
                ganador = [mejor.idx]
            if not meta_cumplida:
                final += " (meta colectiva del sindicato NO alcanzada)"
        ev_esp = self.total_eventos / max(1, len(self.minis))
        suerte = {m.idx: float(np.clip(1 - m.eventos / max(1.0, ev_esp * 1.5), 0, 1)) for m in self.minis}
        return dict(
            final=final, ganador=ganador, puntajes=puntajes, suerte=suerte,
            rep=self.rep, recaudado_sindicato=self.recaudado_sindicato,
            meta_cumplida=bool(meta_cumplida), faltas=self.faltas, dia_transito=self.transito.dia_activacion
        )


def multa_transito(sim, inf, objetivo):
    """Multa a infractores egoístas cuando Tránsito está activo (huir la evita)."""
    act = inf["act"]
    if not sim.transito.activo or act.tipo != "egoista" or act.name == "huir_transito":
        return False
    return sim.rng.random() < (0.25 if inf["m"] is objetivo else 0.06)