"""Agentes tabulares: SARSA (minibuseros) y Q-learning (Tránsito)."""
import numpy as np

def codificar(valores, dimensiones):
    """Convierte una tupla de variables discretas en un índice de estado (base mixta)."""
    indice = 0
    for v, d in zip(valores, dimensiones): indice = indice * d + int(v)
    return indice
class AgenteTabular:
    def __init__(self, n_estados, n_acciones, algoritmo, rng, alfa=0.1, gamma=0.97):
        self.Q = np.zeros((n_estados, n_acciones)); self.algoritmo = algoritmo; self.rng = rng
        self.alfa, self.gamma = alfa, gamma
    def elegir(self, estado, validas, eps, explorables=None):
        """ε-greedy con máscara de acciones válidas. 'explorables' limita las acciones al explorar."""
        validas = list(validas); explorables = validas if not explorables else list(explorables)
        if self.rng.random() < eps: return int(self.rng.choice(explorables))
        q = self.Q[estado, validas] + self.rng.random(len(validas)) * 1e-6   # desempate aleatorio
        return validas[int(np.argmax(q))]
    def actualizar_sarsa(self, s, a, r, s2, a2, terminal=False):
        objetivo = r if terminal else r + self.gamma * self.Q[s2, a2]
        self.Q[s, a] += self.alfa * (objetivo - self.Q[s, a])
    def actualizar_q(self, s, a, r, s2, validas2):
        objetivo = r + self.gamma * self.Q[s2, list(validas2)].max()
        self.Q[s, a] += self.alfa * (objetivo - self.Q[s, a])
    def guardar(self, ruta): np.save(ruta, self.Q)
    def cargar(self, ruta): self.Q = np.load(ruta)
