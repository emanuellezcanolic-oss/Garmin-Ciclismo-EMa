# Notas de metodología — Entrenamiento Óptimo

Fuente: https://entrenamiento-optimo.com/articulos/ (85 páginas leídas vía sitemap el 2026-08-16).
Sitio serio, basado en evidencia (>1000 referencias), enfoque endurance/ciclismo.
Este archivo es memoria de referencia para decisiones futuras del proyecto.

## Filosofía del sitio (alineada con este proyecto)
- **Individualización y ajuste continuo**: "si tu programa te llega en un PDF, deberías preocuparte". Nada de planes fijos; se ajusta con datos día a día. (Es exactamente lo que hace este sistema.)
- **Especificidad**: entrenar para las demandas del evento objetivo.
- **Consistencia > sesiones heroicas**: "realiza tu trabajo cada día, aun si es poco".
- **Trabajar las fortalezas**, no solo tapar debilidades.
- **Monitoreo multivariable** (objetivo + subjetivo), no un solo número.

## Backlog priorizado de mejoras a agregar

### Factibles YA (con FC / datos actuales)
1. **sRPE (RPE de sesión)**: registrar esfuerzo percibido 0-10 × duración = carga subjetiva; cross-check del TSS por FC. [escala-de-percepcion-del-esfuerzo-o-rpe] · Evidencia: Foster.
2. **Feedback subjetivo diario** (fatiga, sueño, dolor muscular, ánimo, estrés) que alimente la decisión del plan. [importancia-del-feedback-post-sesion; feedback-post-entreno] · Evidencia: Saw 2016 (subjetivo ≥ objetivo para monitoreo).
3. **Checklist de sobreentrenamiento / overreaching no funcional (NFOR)**: señales específicas. [indicadores-sobreentrenamiento] · complementa HRV/RHR/monotonía ya implementados.
4. **Doble umbral (LT1 aeróbico + LT2 anaeróbico)**: estimar LT1 para afinar el techo real de Z2. [determinacion-del-primer-y-segundo-umbral-del-lactato].
5. **Nutrición intra-entreno cuantificada**: 30-60 g CHO/h (hasta ~90 g/h con glucosa+fructosa en fondos >2.5 h), sodio 300-600 mg/h; carga de CHO 8-12 g/kg 24-48 h pre-evento. [que-debo-comer-y-beber; rol-del-sodio; carga-de-carbohidratos].
6. **Protocolos de recuperación**: inmersión en agua fría (útil post-resistencia, EVITAR post-fuerza/hipertrofia porque atenúa adaptaciones), siesta 20-30 min, rutina post-competición. [inmersion-en-agua; siesta; recuperacion-post-competicion].
7. **Prevención de infecciones** en cargas altas (hábitos inmunidad). [reducir-el-riesgo-de-infecciones] · complementa señales de salud.
8. **Periodo de transición / offseason** estructurado. [periodo-transicion].
9. **Técnica de pedaleo** ("pedalear redondo") — drills de eficiencia. [pedalear-redondo].
10. **Control de intensidad en HIIT** (dosificación de intervalos) — informa el generador de workouts. [control-intensidad-hiit].

### Requieren hardware o decisión personal
- Potenciómetro → umbrales de potencia, curva potencia-duración, FTP/CP, EF.
- Banda de pecho (intervalos RR) → DFA a1.
- Suplementos (beta-alanina, cafeína, bebidas energéticas): decisión personal/médica. [beta-alanina; bcaa; bebidas-energeticas].

### Médico
- Miocardiopatía post-COVID / retorno a la actividad: criterio médico. [miocardiopatia-post-covid].

## Reglas para decisiones futuras del generador de planes
- Priorizar especificidad MTB con desnivel: fuerza-resistencia en subida + durabilidad (fondos largos).
- Cruzar carga objetiva (TSS por FC) con carga subjetiva (sRPE) y con feedback diario.
- No decidir por un solo número: integrar HRV + RHR + sueño + estrés + RPE + monotonía.
- Mantener consistencia y polarización ~80/20 (ya medido; Emanuel venía 62/12/26 → subir Z2).

---

## Papers científicos aportados por Emanuel (2026-08-16) — específicos de MTB

1. **Hebisz 2021 — Polarizado vs Bloques (20 ciclistas MTB entrenados, 8 sem)**: ambos mejoran capacidad aeróbica, pero el **entrenamiento POLARIZADO fue MÁS efectivo para el VO2max** que el de bloques (Pmax, PVT1 y PVT2 mejoraron similar). → Refuerza fuerte la regla 80/20 del generador. Usa umbrales ventilatorios **VT1 (aeróbico) y VT2 (anaeróbico)** como anclas del modelo de 3 zonas.
2. **Hebisz 2022 — SIT + polarizado y tiempo de reacción (MTB)**: el **Sprint Interval Training (SIT)** mejora de forma aguda el tiempo de reacción y reduce errores; crónicamente sube la potencia media y mejora la toma de decisiones bajo fatiga. Clave para MTB (intensidad variable + decisiones rápidas en descenso). → Agregar SIT al catálogo de tests/entrenos.
3. **de Moura — Composición corporal y rendimiento (83 ciclistas MTB, maratón 75 km)**: el tiempo de carrera **correlaciona positivo con % de grasa (r=0.415)** y **negativo con masa muscular (r=−0.427)** y agua corporal. Más grasa = más lento; más músculo + hidratación = más rápido. → Respalda directamente los objetivos de bajar grasa + preservar músculo + hidratación que ya tiene el sistema. Motivador concreto para Emanuel (109 kg, 33% grasa).
4. **Mater 2021 — Cadencia y función neuromuscular (revisión)**: los ciclistas eligen un rango estrecho de cadencia; cadencia alta + intensidad alta fatiga más el sistema neuromuscular. Entrenar a cadencias NO preferidas da estímulos variados (recomendado). → Monitorear cadencia y agregar trabajo de cadencia variada (alta = soltura; baja/torque = fuerza en subida para MTB).

### Reglas y adiciones que salen de estos papers
- **Polarización 80/20 confirmada como superior** para VO2max en MTB → el planner debe empujar Z2 cuando el % duro semanal supera ~20 (Emanuel venía 62/12/26).
- **Añadir test/entreno SIT** (6-8 × 30 s all-out / 4 min suave): potencia + decisión bajo fatiga.
- **Añadir umbrales VT1/VT2 (doble umbral)** vía test incremental → afinar el techo de Z2 y la zona de umbral.
- **Monitorear cadencia** por salida + drills de cadencia (alta y baja/torque).
- **Composición → rendimiento**: reforzar seguimiento de grasa/músculo/hidratación como predictor directo del tiempo de carrera.

## Segunda tanda de papers (2026-08-16)

5. **Inoue et al. — SIT vs HIT en rendimiento de MTB XC (RCT, 6 sem)**: tanto HIT (intervalos aeróbicos de alta intensidad, ~VO2max) como SIT (sprints) mejoran el rendimiento en MTB, pero **HIT es probablemente MÁS beneficioso (83.5%) que SIT** para el rendimiento en MTB. → El trabajo de calidad (el ~20% duro) debe apoyarse principalmente en **HIT tipo 4×4 min a VO2max** (que ya es el "día de intensidad" del plan); el SIT queda como estímulo secundario/específico.
6. **Revisión sSIT (sprints ≤10 s)**: protocolos con esfuerzos ≤10 s mejoran VO2max y rendimiento aeróbico y anaeróbico; muy eficientes en tiempo, en pocas semanas. → Opción adicional: sprints cortos (10 s) time-efficient.
7. **Hansen & Rønnestad — Entrenamiento a cadencia baja impuesta (revisión)**: **NO hay evidencia fuerte** de beneficio de la cadencia baja; algunos estudios muestran que la cadencia libremente elegida es igual o mejor. Recomendación tentativa: incluir algún bloque de cadencia baja a intensidad moderada-máxima, pero sin sobrevalorarlo. → CORRIGE la nota anterior: no prescribir torque bajo como pilar; cadencia libre está bien, el trabajo de cadencia baja es variedad opcional.
8. **Poon 2024 (Sports Medicine, umbrella review + metaanálisis) — Entrenamiento interválico y composición corporal**: el entrenamiento interválico es eficaz para reducir grasa/adiposidad en adultos sanos, eficiente en tiempo (comparable a continuo). → Respalda incluir algo de intensidad para la pérdida de grasa, equilibrado con el volumen Z2.
9. **Galán-Rioja & Seiler — Periodización, distribución de intensidad y volumen en ciclistas entrenados (revisión sistemática)**: caracteriza modelos de periodización (tradicional, polarizado, piramidal) y TID. → Base para la macro-periodización del plan (base → construcción → pico → transición).

### Reglas actualizadas
- **Calidad = HIT (4×4 VO2max) como prioridad para MTB** (Inoue); SIT y sprints ≤10 s como estímulos secundarios.
- **Cadencia**: la libremente elegida está bien; el trabajo de cadencia baja/torque es variedad opcional, NO un pilar (Hansen). Ajustar el mensaje del dashboard.
- **Intervalos ayudan a la composición corporal** (Poon) → mantener 1-2 días de calidad también sirve para bajar grasa, sin romper el 80/20.
- **Macro-periodización**: estructurar bloques base/construcción/pico/transición (Galán-Rioja/Seiler).

## Tercera tanda de papers (2026-08-16)

10. **Oosthuyse, Muros & Zabala — Nutrición para MTB y ciclocross (revisión)**. Números concretos por disciplina:
   - Pre 24 h: 7–12 g/kg CHO (10–12 en maratón/etapas). 1–4 h pre: 1–4 g/kg CHO. <1 h pre: ~30–60 g CHO rápido si hace falta.
   - **Durante: eventos <2.5 h → 30–60 g/h CHO; >2.5 h → 60–90 g/h**, como **CHO múltiples transportables (maltodextrina:fructosa 2:1 o 3:2)**, solución 5–8% + electrolitos (sodio 10–35 mmol/L, potasio 3–5 mmol/L).
   - Maratón/etapas (XCM/XCS): sumar **proteína (caseína/whey hidrolizada) 10–15 g/h** (solución 1–2%).
   - Post: 1–1.2 g/kg CHO + 20–30 g proteína láctea en la 1ª-2ª h; CHO extendido 4–6 h (mezcla glucosa-fructosa).
   - Cafeína 3–6 mg/kg pre; total ≤6 mg/kg, lejos de 9. Micronutrientes clave: calcio 1000–1500 mg/día (MTB es osteogénico), hierro 8 mg/día, B12.
   - **Gut training**: practicar la nutrición de carrera en los entrenos para tolerar los CHO.
11. **de Moura — Hidratación y rendimiento MTB en calor**: la hidratación es determinante del rendimiento, sobre todo en ambiente caluroso. → Reforzar avisos de hidratación en días de calor.
12. **Inoue 2012 — Tests anaeróbicos y rendimiento XCO**: la capacidad anaeróbica se relaciona con el rendimiento en MTB XC. → Justifica tests/entrenos anaeróbicos (SIT, sprints) para MTB.
13. **Schoenmakers 2026 — Tiempo cerca del VO2max en HIIT (metaanálisis)**: el driver clave del HIIT es maximizar el TIEMPO cerca del VO2max. → Diseñar los intervalos para maximizar T@VO2max (bloques de 3–5 min; el 4×4 va bien).
14. **Viana 2018 — Estrategia de ritmo (pacing) en MTB XCO**: los XCO arrancan agresivo y luego bajan; los de mayor rendimiento tienen **mayor potencia en OBLA (umbral)** y terminan más rápido. → Entrenar la potencia en umbral (OBLA≈VT2/LT2) mejora el rendimiento; enseñar estrategia de pacing.

### Reglas actualizadas (nutrición y calidad)
- **Nutrición intra-entreno MTB cuantificada** (Oosthuyse): usar 30–60 g/h (<2.5 h) y 60–90 g/h (>2.5 h) con maltodextrina:fructosa 2:1; proteína en fondos largos; cafeína 3–6 mg/kg. Integrado en las tarjetas de nutrición.
- **HIIT**: priorizar tiempo cerca de VO2max (4×4). **Umbral/OBLA**: incluir trabajo de umbral para MTB (Viana).
- **Hidratación reforzada en calor**.

## Composición corporal y pérdida de grasa (búsqueda web + Consensus, ago 2026)

Enfoque elegido por Emanuel: **balanceado** (déficit chico solo en días suaves/descanso;
comer completo en calidad/fondos) y **sin cambiar la estructura del entrenamiento** (la
grasa se maneja por nutrición + seguimiento). Hallazgo: intervals.icu ya recibe `bodyFat`
y `fatTotal` de la balanza Femmto, pero la app no los usaba → ahora se leen, se tendencian
y se muestran.

Evidencia clave:
- **Arriel 2020 (MTB amateur)**: la potencia relativa (W/kg) correlaciona negativo con % de
  grasa pero NO con masa magra → es la grasa la que frena, sacar grasa sube potencia/kg.
- **de Moura 2025** (ya en base): tiempo de carrera +0.415 con % grasa, −0.427 con músculo.
- **Alejo 2022**: los ciclistas pro son más magros y con más músculo que juniors.
- **Proteína en el déficit (Mettler 2010; Longland 2016; Witard 2019; ISSN)**: 1.6–2.0 g/kg/día
  preservan masa magra (con poca proteína se pierde músculo; con alta + entreno se preserva/gana).
- **Baja disponibilidad energética / REDs (IOC-REDs Mathisen 2023; Woods 2018)**: por debajo
  de ~30 kcal/kg masa magra/día caen RMR, hormonas y rendimiento. Déficit solo en días fáciles,
  pérdida gradual ~0.5%/sem. Medir % grasa como tendencia de semanas, no a diario.

Reglas incorporadas:
- Nuevos objetivos: % de grasa (−3 pts/12 sem) y masa magra (mantener/subir).
- Nutrición días fáciles: objetivo de proteína 1.6–2.0 g/kg + marco de déficit.
- Guardarraíl REDs en health_signals: peso bajando >1%/sem + FC reposo↑/HRV↓ → aviso de comer más.
- Principios nuevos en evidencia.py: composicion_corporal (reforzado con Arriel),
  proteina_deficit, energia_disponible.

## Control de la carga (Cragnulini 2013, PubliCE) — leído ago 2026

Revisión de cuantificación de carga en ciclismo. **Confirma la metodología de la app** (no
es un cambio de rumbo):
- Carga = volumen × frecuencia × intensidad; en resistencia el TIEMPO importa más que la
  distancia (ciclismo es tiempo- e intensidad-dependiente).
- **Ningún parámetro solo alcanza**: FC = estrés central; potencia/RPE = intensidad periférica.
  Lo correcto es cruzar varios. Sin potenciómetro → FC + RPE (lo que ya hace la app).
- **FC**: lineal con la intensidad submáxima, pero se distorsiona con calor, deshidratación
  (+7.5%), variación día a día (2–4 lpm), posición y pendiente. **Deriva cardíaca** en salidas
  largas: la FC sube y baja la potencia para sostener la zona (justo lo que mide el desacople).
  La FC responde con retardo → no sirve para intervalos 30/30; ahí manda el RPE.
- **RPE (Borg/OMNI-RPE, validado en ciclismo)**: barato, práctico y MÁS sensible para prevenir
  el sobreentrenamiento; mejora con el autoconocimiento del ciclista.
- Regla incorporada: principio `carga_multiparametrica` en evidencia.py (FC + RPE + sensaciones).

## Historia de salud — Ergometría (04/09/2026)

Estudio: Ergometría 12 derivaciones, cicloergómetro, protocolo WHO-modificado.
Centro Médico y Diagnóstico del Sur — Dr. Moriniго Ricardo (MN 83210 / MP 2832).
Emanuel: 35 años, 109 kg, 184 cm, IMC 32.2.

Datos clave:
- **FC máx alcanzada 173 lpm** (93% de la teórica 185); FC reposo 64. Histórico Garmin: 176.
- PA reposo 130/80 → PA máx 180/80 (respuesta presora normal). Doble producto máx 31.140.
- **9.1 METs máx** (~245 W; VO2 por carga ~32 ml/kg/min). "Elevada clase funcional".
- **HRR 1 min = −21 lpm** (173→152). R3 121.
- ST-T normal, sin evidencia de isquemia. Asintomático. Ergometría máxima normal.

Lectura de cardiología deportiva (para el entrenamiento):
- Test válido y máximo; corazón sano en el esfuerzo → **habilitado para intensidad** (HIIT/4×4/SIT).
- Respuesta cronotrópica y presora normales; HRR adecuado (KPI a seguir, debería subir con la forma).
- **FCmáx real ~173-176** → cargar en Garmin/intervals; confirmar con test de 30 min (LTHR).
- El limitante es composición corporal + base aeróbica, no el corazón → refuerza el rumbo.
- Una ergometría sin gases/lactato NO da VT1/VT2; para zonas finas, el test de campo.
- Guardado en la app en Salud/Estudios (data/salud.json) con análisis y disclaimer (lo firma el cardiólogo).

## Sección Medidas (para compras online)
- data/medidas.json + sección "Medidas" con dibujos de cómo medir (SVG) por prenda: ropa
  (pecho/cintura/cadera/entrepierna/brazo/bíceps), calzado (pie), guantes (mano largo/contorno),
  casco (cabeza), + peso y altura.
- **Edición in-app con localStorage** (`peloton-medidas`): Emanuel escribe cada valor en un input
  y se guarda solo en el navegador (feedback "✓ guardado"), sin pasar por GitHub. El peso es de
  solo lectura (viene de la balanza / Composición). El seed de data/medidas.json es el valor por
  defecto; lo guardado a mano tiene prioridad. (add_medida.py queda como vía alternativa, no principal.)

## Banda HRM 600 → DFA α1 + respiración (desde 09/2026)
- Emanuel sumó una **Garmin HRM 600** (banda de pecho). Ahora las salidas graban el intervalo
  **latido a latido (RR)**: el stream `hrv` de intervals.icu trae los RR (confirmado: `RR presente=True`).
  El sensor de muñeca NO da RR fiable → para DFA hay que usar la banda.
- **DFA α1 (Detrended Fluctuation Analysis, orden 1)** — scripts/dfa.py. Método Rogers et al. 2021:
  se calcula α1 en ventanas cortas (120 s) sobre escalas de 4–16 latidos; a medida que sube la
  intensidad α1 baja. **α1 ≈ 0.75 = umbral aeróbico (AeT/VT1) = techo real de la Z2**; **α1 ≈ 0.5 = VT2**.
  Filtro de artefactos: RR fuera de 300–2000 ms o con salto >5% vs. el previo se descartan.
  Normaliza a ms si el stream viene en segundos.
- **En el build** (compute_dfa): calcula sobre las últimas ~6 salidas con RR; la más reciente que
  cruce el umbral fija el AeT actual, el resto arma la tendencia (sparkline). El α1 del tramo fácil
  de la última salida es marcador de **durabilidad/fatiga** (≥0.9 muy fresco · ~0.75 en umbral ·
  <0.5 intenso). Expuesto en `data["dfa"]`; α1 por salida anotado en cada ride (detalle de salida).
- **Test DFA α1 · rampa** (load_test.py `dfa_ramp`): rampa suave y pareja Z1→Z5 en escalones de 3 min,
  con la banda, en rodillo/llano sin cortes → curva α1–FC limpia. Es el valor **más confiable** de AeT.
- **Frecuencia respiratoria**: `average_respiration` por salida (la banda la mide) → marcador de
  esfuerzo; se muestra en el detalle de cada salida.
- Aviso al usuario: DFA es sensible; el número orientativo sale de cualquier salida con banda, pero
  el confiable sale del test de rampa. numpy agregado al workflow (dashboard.yml).
