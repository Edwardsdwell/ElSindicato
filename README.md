# ElSindicato
Proyecto De Aprendizaje por Refuerzo Descubrir el rendimiento de un colectivo cuando cada individuo tiene la libertad para escoger entre dicho beneficio el beneficio individual, a través  de un juego
#Ideas, decisiones, pensamiento, lógica, derechos y filosofía de este juego, versión y tal propias de Edwardsdwell

#Bitácora
#Borrador 0
Tipo de Aprendizaje: Por Refuerzo
Objetivo General: Descubrir el rendimiento de un colectivo cuando cada individuo tiene la libertad para escoger entre dicho beneficio el beneficio individual, a través  de un juego
Objetivos específicos:
Desarrollar un entorno virtual para el desarrollo de experimento
Sacar resultados de las decisiones que tomen los agentes individuales mientras trabajan tanto para ellos como para el colectivo
Añadir factores de cambio externo que fuerce a los agentes a elegir
Determinar una tabla de pesos, recompensas y penalizaciones.

Synthesis:
El juego denominado como “Sindicato de Transporte 11 De Septiembre” simula el funcionamiento de una línea de transporte público de tipo “minibús” en un entorno de mapa de la ciudad  de La Paz, para este proyecto se hará uso de  5 agentes entrenados bajo el mecanismo de aprendizaje por refuerzo de Sarsa, que irán aprendiendo durante un periodo de 5 años  o 1826 días considerando como el año bisiesto el {último de estos. Las recompensas irán relacionadas en  cuanto a la eficiencia de sus rutas, la recompensa final de sus ingresos considerando un pasaje estandarizado de  3Bs por cada pasajero. Se añadieron factores de tráfico y competencia para añadir parámetros de “avaricia” y estímulo a tomar decisiones. Los agentes durante el tiempo pueden  ir cambiando, pero, un sexto agente llamado “tránsito” se incorporará cuando las recompensas y pesos acumulados tanto de colectivo como individuales excedan un número límite de faltas cometidas, este agente no cambia, se entrena con q-learning y su objetivo es atrapar a los infractores. Tiene un parámetro de normas de tránsito que son inalterables. Dentro de las faltas están los accidentes, choques, ocasionar daño al tráfico a los pasajeros, matar a alguien ,destruir su motorizado.
El entorno tendrá un factor interactivo de tránsito que generará competencia entre los agentes “minibuseros”.

Cada agente contará con una ficha técnica de persona, modelo de su vehículo ,velocidad tope de su vehículo, personalidad (factores de recompensa personalizados), historial social, lo que servirá para que parte de sus ingresos diarios se recorten por “gastos familiares, impuestos, repuestos” así como tendrán un cooldown de 7 momentos para recargar “combustible” ,se maneja un solo tipo de combustible, no pueden tener tan fácil recaudar dinero. Además durante un día de la semana no podrán circular por la ¨restricción vehicular¨, cada agente un día distinto de lunes a viernes, fin de semana todos pueden o no trabajar.
Los “pasajeros” por episodio/día no son ilimitados, y se consideran eventos aleatorios de penalización como cortes de vías, entradas, prestes, atracos, apariciones fantasmas, etc que les pueden salir en sus rutas.
El sindicato cada “año” tiene una cuota mínima de dinero que cada agente debe entregar, así como una meta al acabar los 5 “años”, por su parte los agentes deben aportar a ella como ver que su dinero también les sirva para mantener sus unidades, su vivienda, pagar impuestos, mantener a sus familias, así los intereses de IA los fuercen a decidir constantemente qué hacer. Puede existir el evento de sobre presión donde un agente decida abandonar la carrera o terminar su turno ”por su propia mano”.
Tránsito no inicia con ellos pero una vez que sale se queda en el juego y busca “arrestar/detener” a los que tengan estatus “buscado mayor a 5”, aque que sea atrapado quede congelado en “prision” por 7 “meses” en el jeugo, además que desde ese turno tendrá dos años con una penalización económica extra y hará que la reputación del sindicato caiga en 0.25 pts, 5 maximo reputación de sindicato, menos de 2.5 es atroz, si se queda sin reputación el juego acaba y todos pierden. 

Perfiles de Agentes IA bosquejo:
Nombre completo
motorizado
tendencia (agresivo, pasivo,volátil)
velocidad máxima
velocidad estándar
cuota en el sindicato (todos pagan lo mismo)
Gastos familiares (varían para ver qué tanto influye en las decisiones del agente) y si no tiene familia tendrá alguna deuda o gasto de “vicios”

FIlosofía de puntajes: Los agentes deben si bien no estar estresados, deben tener presión constante para “trabajar”

Tabla modelo de pesos, recompensas e indicadores a ajustar
 
Acción
Tipo
Penalización
Ganancia
Reputación para el sindicato
Adelantar en doble vía
Egoísta
-4 seguridad / + riesgo accidente
+2 aceleración / +2 avance en tráfico
-0.5
Conducir a exceso de velocidad
Egoísta
-5 seguridad / -1 integridad unidad
+5 velocidad
-0.5
Tocar el claxon
Egoísta
-2 seguridad / -1 paciencia pasajeros
+3 apertura de paso / +2 intimidación
-0.4
Tomar atajos
Egoísta
-2 fiabilidad de ruta / -1 precisión ruta
+3 velocidad
-0.2
Huir de tránsito
Egoísta
-6 fiabilidad / + riesgo captura
+4 evasión / conserva monto de multa
-0.8
Ceder paso a peatones
Altruista
-2 velocidad / -1 tiempo recorrido
+4 seguridad / +3 reputación ciudadana
1
Mantener el límite de velocidad
Altruista
-3 velocidad / -1 vueltas por turno
+4 seguridad / +2 ahorro combustible
0.4


Cumplir su ruta completa
Altruista
-2 energía / -1 integridad unidad
+5 fiabilidad / +4 ingresos estables
1
Mantener la unidad aseada
Altruista
-2 dinero (limpieza) / -1 tiempo
+4 confort / +3 satisfacción pasajero
0.7
Obedecer las normas de tránsito
Altruista
-3 velocidad
+5 seguridad / +3 fiabilidad
0.4
No aportar al sindicato
Filosófica
-5 respaldo gremial / - reputación vínculo
+4 dinero personal / +2 independencia
-1
No aportar al hogar
Filosófica
-6 moral / -2 estabilidad familiar
+5 dinero disponible (unidad/propio)
-0.5
Respetar los semáforos
Filosófica
-2 tiempo recorrido
+3 autocontrol / +3 orden vial
1
Maldecir al volante
Filosófica
-3 temple / -2 ambiente en unidad
+2 desahogo / -2 estrés
-0.5
Conducción temeraria
Criminal
Activa/atrae a Tránsito; +2 estatus buscado
+4 en todas las stats egoístas
-1
Estrellar su unidad
Criminal
Activa/atrae a Tránsito; -4 integridad; +3 estatus buscado
+6 en todas las stats egoístas
-1
Atropellar peatón / pasajero o acabar con pasajero
Criminal
Activa/atrae a Tránsito; -0.25 reputación sindicato; +5 estatus buscado
+7 en todas las stats egoístas
-1




Mucha aceleración/velocidad puede implicar mayor porcentaje de accidente. Los eventos trágicos estarán sujetos al indice de agresividad de los agentes, un agente más agresivo es más propenso porcentualmente  a cometer una actividad criminal.

Fases de implementación:
Los agentes minibuseros tendrán un pre-entreno en google collab en SARSA donde aprenderán a manejar, los reglamentos de tránsito y sus identidades, así como aprenderán de la ciudad con A* limitándoles para evitar que salten entre calles o atraviesen algo que no sea calzada.
Colab pre entrena y esos modelos listos se guardan en una carpeta dentro el proyecto, se guardan los pesos/tablas Q y SARSA entrenados para cargarlos directamente en la simulación de 1826 días en La Paz, y luego el aprendizaje continúa activo durante los 5 años.  Para evitar desperdiciar esos 5 años en aprender, si no que sean refinamiento y bajo normas,  durante el pre entrenamiento simplemente aprenden a “conducir” y tener “identidad” y “conocimiento”
El agente de tránsito también se entrenará en collab pero con q-learning donde aprenderá todas las normas de tránsito y practicará con eventos similares a los que enfrentará para poder atrapar a los minis.
El mapa del juego se construirá en base a la ciudad de La Paz Bolivia, añadiendoles una ruta única, pero con ciertos atajos que no se les dirá, pero pueden descubrir, esto les dará bono de velocidad pero penalización en precisión de ruta. Se añadirá pasajeros finitos por turno que se repartirán entre ellos y deben competir por ellos, teniendo los marcadores y barras para sindicato y necesidades individuales. A su vez se implementan semáforos. La visualización mostrará a los agentes y el tránsito recorriendo las calles de la paz, cada icono de personaje agente saldrá de: “mini 1”,”mini2”,”mini3”,”mini 4”,”mini 5”,”tránsito” todos jpg reducidos.
Una vez el mapa esté construido la simulación de 5 años se llevará a cabo con los agentes entrenados y el tránsito pudiendo observar como realizan a cabo su trabajo.
El refuerzo de aprendizaje se dará hasta finalizar donde se tendrá los modelos finales con  las decisiones registradas en bitácoras de cada mini y tránsito, cada uno una bitácora, al final se unirán en global para ver estadísticas.
Si el mini no da su cuota al sindicato al final de cada año es eliminado, son días de 365 y solo el ultimo es de 366, Gana quien sobreviva dentro el sindicato y solo si cumplio con sus metas de objetivos individuales de mejor manera, si más de uno lo logró se considerará el resto de estadísticas qué tan llenas las logró en acumulado, no pueden cambiar de unidad y al finalizar con la elección del ganador se mostrará su perfil y decisiones más importantes, así como el indicador de suerte que se mide por que tan pocos eventos aleatorios le aparecieron.Uno de los requisitos del sindicato es tener reputación mayor igual a 4.2
si al final de un año nadie paga la cuota empiuezan el siguiente año con deuda y penalización pasiva en ganancias, si varios sobreviven empatados en cumplimiento de metas individuales tendremos el final “bueno”. 
Al finalizar el juego, se clusterizará por aprendizaje no supervisado para agrupar por decisiones desde la bitácora y personalidad los minibuseros.
Se medirá el éxito del tránsito con su propia tabla y se verá si tras su turno de salida el rendimiento mejoro o empeoro pero viendo tambien el indice de seguridad establecidas por crímenes cometidos por los minis



mejoras futuras a adjuntar en recomendaciones: 
para futuras modificaciones se añadirá un factor de corrupción a transito
implementar gasolina y gnv
añadir trameaje formal
añadir pasaje diferenciado


