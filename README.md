Simulación local de aprendizaje por refuerzo para cinco minibuses y un agente de Tránsito en una La Paz ficticia. 
El proyecto está organizado en cuatro áreas principales:

pre entrenamiento/       Políticas iniciales
juego/                   Motor de simulación, servidor e interfaz web
modelosML/               Modelos iniciales y entrenamiento adicional
Apartado multimedia/     Imágenes, música, fuentes y sprites de vehículos


`jugar.py` está en la raíz para iniciar el juego directamente. 
También se conservan allí dependencias, documentación, cachés y salidas compartidas.

## Inicio

Requiere Python 3.10 o posterior. Desde la raíz del proyecto:

```powershell
py jugar.py
```

El lanzador prepara el entorno virtual e inicia el juego local. La primera construcción del mapa necesita conexión a Internet.

## Entrenamiento

Genera las políticas iniciales SARSA y Q-learning con:

```powershell
.\.venv\Scripts\python.exe "pre entrenamiento" --dias-minis 6000 --dias-transito 2000 --semilla 0
```

Continúa el aprendizaje desde las políticas preentrenadas con:

```powershell
.\.venv\Scripts\python.exe modelosML\entrenamiento\ejecutar.py --dias 1826 --semilla 7
```

Los modelos iniciales y su resumen de evaluación se guardan en `modelosML/preentrenados/`; las corridas interactivas se guardan en `outputs/sindicato/`.

## Recursos y documentación

- Imágenes, música y sprites: `Apartado multimedia/`.
- Arquitectura: `docs/arquitectura/estructura.md`.
- Borrador de diseño original conservado del repositorio: `docs/concepto-original.md`.

