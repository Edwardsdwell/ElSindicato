"""Configuración central: tabla de pesos, economía, personalidades, perfiles."""
from dataclasses import dataclass

SEMILLA = 42

# ---------------- Tiempo ----------------
TICKS = 16                      # intervalos de 30 min por jornada de 8 h
HORAS_POR_TICK = 0.5            # horas por tick
DIAS_POR_ANO = [365, 365, 365, 365, 366]   # 1826 días, el último año es bisiesto
TOTAL_DIAS = sum(DIAS_POR_ANO)

# ---------------- Economía ----------------
TARIFA = 3.0                    # Bs por pasajero
CUOTA = 9000.0                  # cuota anual al sindicato (igual para todos)
PENALIZACION_CUOTA = 1.10       # si reputación < REP_MIN_REQ el sindicato sube la cuota 10%
COSTO_COMBUSTIBLE = 556.8        # Bs por recarga (un solo tipo de combustibley se considera fulleado)
ENFRIAMIENTO_RECARGA = 7        # ticks
TASA_IMPUESTO = 0.05
TASA_REPUESTOS = 0.04           # repuestos
COSTO_REPARACION_POR_PT = 4.0
CUPO_ENTRE_SEMANA, CUPO_FIN_SEMANA = 580, 460   # pasajeros finitos por día (compartidos)
META_SINDICATO_RATIO = 0.80     # meta del sindicato = 80% de todas las cuotas posibles

# ---------------- Reputación / Tránsito ----------------
REP_MAX, REP_MIN_REQ, REP_ATROZ = 5.0, 4.2, 2.5
ESCALA_REP = 0.0010             # escala de la columna "reputación" de la tabla
RECUPERACION_REP = 0.004        # recuperación diaria por buen servicio
LIMITE_FALTAS = 120             # faltas acumuladas que activan a Tránsito
BUSCADO_ARRESTO = 5.0           # "buscado mayor a 5"
DIAS_PRISION = 210              # 7 meses
DIAS_MALUS = 730                # 2 años de penalización extra
FACTOR_MALUS = 0.75
PENALIZACION_REP_ARRESTO = 0.25
MULTA = 30.0

# ---------------- RL ----------------
ALFA, GAMMA = 0.10, 0.97
PESO_COLECTIVO = 60.0           # peso del término colectivo (Δ reputación del sindicato)
ESCALA_RECOMPENSA = 0.06

# ---------------- Acciones (tabla del documento, numerizada) ----------------
@dataclass(frozen=True)
class Accion:
    nombre: str
    tipo: str
    velocidad: float    # multiplicador de velocidad
    riesgo: float       # prob. adicional de accidente por tick
    integridad: float   # daño a la unidad
    buscado: float      # +estatus buscado
    rep: float          # columna "reputación para el sindicato"
    atractivo: float    # atractivo para pasajeros (efecto inmediato)
    ganancia: float     # puntaje de "ganancia" de la tabla
    penalizacion: float # puntaje de "penalización" de la tabla
    costo: float = 0.0  # Bs
    estres: float = 0.0

ACCIONES = [
    Accion("conducir_normal",      "neutro",     1.00,  0.000,  0, 0.0,  0.0,  0.00, 2,  0),
    Accion("cargar_combustible",   "neutro",     0.00,  0.000,  0, 0.0,  0.0,  0.00, 0,  0, COSTO_COMBUSTIBLE),
    Accion("terminar_turno",       "neutro",     0.00,  0.000,  0, 0.0,  0.0,  0.00, 0,  0, 0.0, -3.0),
    Accion("adelantar_doble_via",  "egoista",    1.30,  0.030,  0, 0.0, -0.5,  0.00, 4,  4),
    Accion("exceso_velocidad",     "egoista",    1.50,  0.050,  2, 0.2, -0.5,  0.00, 5,  6),
    Accion("tocar_claxon",         "egoista",    1.08,  0.005,  0, 0.0, -0.4, -0.08, 5,  3, 0.0, -0.5),
    Accion("tomar_atajo",          "egoista",    1.00,  0.010,  0, 0.0, -0.2,  0.00, 3,  3),
    Accion("huir_transito",        "egoista",    1.40,  0.060,  0, 0.5, -0.8,  0.00, 4,  6, 0.0,  1.0),
    Accion("ceder_paso",           "altruista",  0.80, -0.005,  0, 0.0,  1.0,  0.10, 7,  3, 0.0, -0.5),
    Accion("limite_velocidad",     "altruista",  0.90, -0.008,  0, 0.0,  0.4,  0.00, 6,  4),
    Accion("cumplir_ruta",         "altruista",  1.00,  0.000,  0, 0.0,  1.0,  0.15, 9,  3),
    Accion("aseo_unidad",          "altruista",  0.95,  0.000,  0, 0.0,  0.7,  0.20, 7,  3, 6.0, -0.3),
    Accion("obedecer_normas",      "altruista",  0.85, -0.010,  0, 0.0,  0.4,  0.05, 8,  3, 0.0, -0.3),
    Accion("no_aportar_sindicato", "filosofica", 1.00,  0.000,  0, 0.0, -1.0,  0.00, 6,  5, 0.0,  0.5),
    Accion("no_aportar_hogar",     "filosofica", 1.00,  0.000,  0, 0.0, -0.5,  0.00, 5,  8, 0.0,  1.0),
    Accion("respetar_semaforos",   "filosofica", 0.90, -0.005,  0, 0.0,  1.0,  0.05, 6,  2, 0.0, -0.5),
    Accion("maldecir_volante",     "filosofica", 1.00,  0.004,  0, 0.0, -0.5, -0.05, 4,  5, 0.0, -2.0),
    Accion("conduccion_temeraria", "criminal",   1.60,  0.080,  6, 2.0, -1.0,  0.00, 8,  6, 0.0,  1.0),
    Accion("estrellar_unidad",     "criminal",   1.30,  0.000, 25, 3.0, -1.0,  0.00, 6, 10, 0.0,  2.0),
    Accion("atropellar_pasajero",  "criminal",   1.20,  0.000, 15, 5.0, -1.0, -0.20, 7, 15, 0.0,  3.0),
]
INDICE_ACCION = {a.nombre: i for i, a in enumerate(ACCIONES)}
LEGALES = {"respetar_semaforos", "obedecer_normas", "ceder_paso", "limite_velocidad"}

# ---------------- Personalidades (factores de recompensa personalizados) ----------------
PERSONALIDADES = {
    "agresivo": dict(
        agresividad=0.80,
        aversion_riesgo=0.6,
        lam=0.15,
        pesos=dict(neutro=0, egoista=1.4, altruista=0.5, filosofica=0.8, criminal=0.9),
    ),
    "pasivo": dict(
        agresividad=0.20,
        aversion_riesgo=1.4,
        lam=0.70,
        pesos=dict(neutro=0, egoista=0.4, altruista=1.3, filosofica=1.0, criminal=0.1),
    ),
    "volatil": dict(
        agresividad=0.50,
        aversion_riesgo=1.0,
        lam=0.40,
        pesos=dict(neutro=0, egoista=1.0, altruista=1.0, filosofica=1.0, criminal=0.5),
    ),
}

# ---------------- Perfiles de los 5 minibuseros ----------------
PERFILES = [
    dict(nombre="Hilarión Mamani Colque",  modelo="Toyota Hiace 2008",    v_estandar=28, v_maxima=70, personalidad="agresivo", familia=142,  tipo_familia="familia (4 hijos)"),
    dict(nombre="Jheanine Añez Condori",     modelo="JinCheng Jinbei ",    v_estandar=26, v_maxima=60, personalidad="pasivo",   familia=180, tipo_familia="familia (madre enferma)"),
    dict(nombre="Eleuterio Apaza Conde",    modelo="Foton View CS2",  v_estandar=27, v_maxima=65, personalidad="volatil",  familia=105,  tipo_familia="deuda por vicios"),
    dict(nombre="Yotoko Kakita Tokame Flores", modelo="Kingo Minivan", v_estandar=30, v_maxima=80, personalidad="agresivo", familia=195, tipo_familia="familia (hipoteca)"),
    dict(nombre="Ricardo Kanye Milos West",    modelo="Kingo 17 DK4 MT6",       v_estandar=25, v_maxima=58, personalidad="volatil",  familia=127, tipo_familia="familia (2 hijos)"),
]
