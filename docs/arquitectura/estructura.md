# Estructura del proyecto

```text
Dies Irae/
├── jugar.py                                # Inicio directo
├── pre entrenamiento/                      # Políticas iniciales y sprites
├── juego/                                  # Motor, servidor y aplicación web
├── modelosML/                              # Políticas y entrenamiento adicional
├── Apartado multimedia/                    # Imágenes, música y sprites
├── outputs/                                # Corridas y reportes generados
├── docs/                                   # Documentación
├── bitacora_corridas/                      # Registro de ejecuciones
├── requirements*.txt                       # Dependencias
└── README.md
```

`jugar.py` crea el entorno virtual `.venv` en la raíz, instala las dependencias base y lanza `juego/sindicato/server.py`. Usa por defecto las políticas de `modelosML/preentrenados/`.

## Flujo de trabajo

1. Ejecuta `python "pre entrenamiento"` para generar políticas iniciales en `modelosML/preentrenados/`. El flujo autocontenido está en `pre entrenamiento/preentrenamiento.py`.
2. Ejecuta `modelosML/entrenamiento/ejecutar.py` para continuar el aprendizaje y guardar resultados en `outputs/entrenamiento/`.
3. Inicia `jugar.py` para abrir la simulación. Las corridas interactivas se guardan en `outputs/sindicato/`.
4. El script `pre entrenamiento/preprocesamiento/procesar_iconos.py` regenera sprites desde las imágenes de `Apartado multimedia/assets/vehiculos/originales/` hacia `Apartado multimedia/sprites/vehicles/`.

Las cachés locales se guardan en `.cache/`. Los resultados bajo `outputs/` y la caché no se versionan.
