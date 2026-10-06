# IA, cachés, planes, patrocinio y escalado

Análisis del 6 de octubre de 2026, con datos medidos en el Bee (Beelink Core 3
304, iGPU Intel, 15,6 GB de RAM, 216 GB libres en `/vol2`). Lo marcado como
*estimación* depende de supuestos que se indican.

## 1. Lo implementado (commit 8ead178)

| Cambio | Detalle |
| --- | --- |
| Cola de IA por planes | Redis. Prioridad `ai_priority` del plan: 0 VIP/editor/admin, 1 general, 2 gratis, 3 pregeneración nocturna. FIFO dentro de cada prioridad. Un mismo artículo+idioma es **un solo trabajo**: si otro lector lo pide, se une, y si tiene mejor plan lo adelanta. |
| Respuesta inmediata | `GET /ai-summary?generate=true` ya no espera al modelo: devuelve `status` (`queued`/`running`/`ready`/`failed`), `position` y `eta_s`. La app consulta cada 2 s. |
| Lotes en la iGPU | El worker toma hasta 2 trabajos y los genera juntos (atención paginada + *continuous batching*). |
| Titulares | Se traducen con opus-mt (CPU, instantáneo) en vez de una segunda pasada del LLM. |
| Texto completo | El resumen usa el artículo completo, no el extracto del feed. Si el feed solo da extracto, lo descarga primero. Si luego llega el texto completo, se borran resúmenes, traducciones y audio hechos con el extracto. |
| Cuota diaria | Nuevo límite `ai_summaries_per_day`. Gratis: 3 resúmenes **nuevos** al día; los que ya existen se leen sin límite. |
| Planes | Gratis: voz del dispositivo, sin Post radio. General: voz del servidor manual y Post radio limitado a 5 posts / 20 min. VIP/editor: prioridad alta, radio 20 posts / 60 min. Todo editable en Admin. |
| Pregeneración | De 00 a 05 UTC, si la cola está vacía, se encolan (prioridad 3) resúmenes de los artículos del último día de las fuentes que siguen lectores VIP/editor/admin activos, en su idioma. Máximo 20 por pasada, cada 30 min. |
| Lector | La barra azul aparece plegada y sin el extracto. Al pulsarla muestra el resumen IA, o lo pide y enseña posición y espera. |

Pregenerar voz para VIP no se ha hecho: la voz del servidor ya empieza a sonar
en ~0,4 s (se genera mientras suena), así que adelantarla apenas mejora nada y
ocupa CPU y disco.

## 2. Cachés: qué se guarda y se sirve a los demás

| Contenido | Dónde | Compartido | Dura |
| --- | --- | --- | --- |
| Resumen IA | `article_ai` (artículo + idioma) | Sí, todos los lectores de ese idioma | Lo que el artículo: **90 días** (retención) |
| Traducción | `article_translations` | Sí | 90 días |
| Artículo completo | `articles.full_html` | Sí | 90 días |
| Audio (voz del servidor) | `/data/tts`, por artículo + idioma + voz | Sí | **Antes:** sin límite de tiempo, LRU de 1 GB (~550 grabaciones). **Ahora:** 90 días desde la última reproducción, se borra con su artículo; tope de seguridad 10 GB |
| Audio sin conexión | En el iPhone (guardados) | — | Mientras siga guardado |

Los guardados y favoritos no se purgan nunca, ni sus resúmenes. Tampoco los
50 artículos más recientes de cada fuente.

**Post radio**: verificado con test (`test_radio_mixes_recorded_and_new_posts`).
Pide cada post por separado. Primero usa la copia del iPhone, luego la caché
del servidor, y solo genera lo que falta. En una secuencia de 3 posts con uno ya
grabado genera 2. Repetida, sirve los 3 de caché sin generar nada.

### Espacio estimado para 90 días

Tamaños medidos: resumen ~0,6 KB, traducción ~4,5 KB, artículo completo
~9,5 KB, audio ~1,9 MB (unos 6 min de voz a 40 kbps mono), artículo en BD
~11,5 KB con su vector.

| Escenario (*estimación*) | Artículos/día | BD 90 días | Audio 90 días |
| --- | --- | --- | --- |
| Hoy (5 usuarios, 77 fuentes, ~5 audios/día) | ~700 | ~0,7 GB | ~0,9 GB |
| 500 usuarios (~1.000 fuentes, 100 audios/día) | ~9.000 | ~9 GB | ~17 GB → limitado a 10 GB |
| 10.000 usuarios (~10.000 fuentes, 1.000 audios/día) | ~90.000 | ~90 GB | ~170 GB |

Conclusión: el texto (resúmenes, traducciones) ocupa poco. El audio es lo que
crece. Hasta unos cientos de usuarios caben 90 días con el tope de 10 GB. A
partir de ahí, o se sube el tope (hay 216 GB libres) o se baja la calidad a
32 kbps (−20 %), o el audio se aloja fuera (ver §6).

## 3. Rendimiento del resumen IA (medido en el Bee)

Artículos reales de ~1.900 tokens, Qwen3-4B int4, iGPU:

| Modo | Total | Por resumen |
| --- | --- | --- |
| Antes: uno a uno (SDPA) | ~17 s c/u | 17 s (5 s leer + 12 s escribir a ~11 tok/s) |
| Lote de 2 (atención paginada) | 20,7 s | **10,3 s** (×1,6) |
| Lote de 4 | 38,7 s | 9,7 s (×1,75) |
| Decodificación especulativa (borrador Qwen3-0.6B en iGPU) | 21–26 s c/u | Peor: compiten por la misma memoria |
| Borrador en el NPU | No compiló en 8 min | Descartado |
| **Producción tras el cambio** | 29 s el primer lote de 2 (con calentamiento) | ~14,5 s |

- **El cuello de botella:** el ancho de banda de memoria de la iGPU al escribir. Por eso juntar 2 casi duplica la capacidad, pero más de 2 apenas mejora.
- **El NPU no sirve para este LLM:** formas estáticas y una compilación lentísima. Podría alojar los *embeddings* para liberar la iGPU, pero su carga es mínima y no compensa.
- **Margen restante (opcional):**
  - Pedir 3 frases en vez de 3–4 (−20–25 % de tiempo, resúmenes algo más cortos).
  - Recortar la entrada a ~4.000 caracteres (lectura más rápida, algo de pérdida en artículos largos).
  - Una segunda máquina con iGPU que consuma la misma cola (escala lineal; la cola ya está preparada).

Capacidad actual *estimada*: ~10 s por resumen en lotes → ~8.500 resúmenes/día
con la iGPU al 100 %, o ~350/hora en hora punta.

## 4. GitHub Sponsors para cubrir gastos (sin beneficio)

**Cómo funciona** (documentación de GitHub):
- **Comisiones:** 0 % para patrocinios desde cuentas personales.
- **Cobro:** vía Stripe, con el formulario W-8BEN.
- **Impuestos:** GitHub no retiene ni emite certificados para residentes fuera de EE. UU. En España los ingresos se declaran en el IRPF aunque solo cubran gastos. Conviene confirmar con un gestor cómo encajarlo (o crear una asociación sin ánimo de lucro si crece).

**Gastos operativos completos** (*estimación*, rellena tus cifras reales):

| Concepto | Supuesto | €/año |
| --- | --- | --- |
| Servidor Beelink | 450 € en 4 años | 112 |
| Ampliaciones (RAM/SSD) | 120 € en 4 años | 30 |
| Discos de copia (parte del QNAP) | 220 € en 5 años × 25 % | 11 |
| Electricidad Beelink | 18 W medios × 0,18 €/kWh | 28 |
| Electricidad QNAP (parte) | 25 % de ~30 W | 10 |
| Dominio uverse.es | | 12 |
| Apple Developer | 99 $/año | 92 |
| Google Play | 25 $ una vez, en 5 años | 5 |
| Parte de la fibra | 10 % de 30 €/mes | 36 |
| Imprevistos | 10 % | 34 |
| **Total** | | **~370 €/año ≈ 31 €/mes** |

**Propuesta:**
- **Página de costes pública:** en `/info` o una nueva `/costes`, con esta tabla actualizada cada año y lo recaudado frente a lo gastado.
- **Niveles de Sponsors:** 2, 5 y 10 €/mes, con la meta de Sponsors fijada en ~31 €/mes.
- **Si sobra:** va a un fondo de hardware anunciado, por ejemplo la segunda máquina con iGPU de §3, y nunca a ingresos personales.
- **Apple:**
  - **Enlaces de donación:** la app de iOS no puede llevar a donaciones con pago externo salvo que seas una organización sin ánimo de lucro aprobada. Deja los enlaces solo en la web.
  - **Ventajas para patrocinadores:** si a los patrocinadores se les da VIP, Apple lo considera desbloquear contenido digital. La app de iOS tendría que ofrecer ese mismo VIP como compra dentro de la app.
  - Lo más simple es el patrocinio como donación sin ventajas. Verifica las guías vigentes al preparar la ficha.
- **Alternativas:**
  - **Open Collective:** gastos públicos por diseño, pero con comisión del anfitrión fiscal.
  - **Liberapay:** sin comisión de plataforma, pero menos conocido.

## 5. Escalado a 10.000 usuarios

**La clave:** el coste de IA crece con los **artículos distintos** que alguien
pide, no con los usuarios. Mil lectores de la misma noticia cuestan un solo
resumen y una sola grabación. Por eso la caché compartida y la cola deduplicada
son la base. La pregeneración por popularidad completa el cuadro.

| Recurso | 10.000 usuarios (*estimación*) | ¿Aguanta el Bee? |
| --- | --- | --- |
| Resúmenes | 10 % pide 3/día → 3.000/día; punta 4 h → ~750/h | No en punta (capacidad ~350/h). Hace falta otra iGPU o un respaldo externo |
| Voz | 1.000 grabaciones nuevas/día × 15 s de CPU | Sí, pero compite con la API; mejor una segunda máquina para IA |
| Audio servido | 20 % escucha 3/día × 1,9 MB → ~11 GB/día (~1 Mbps de media, picos mayores) | Sí con fibra simétrica |
| BD | ~90 GB a 90 días | Sí (216 GB libres); vigilar índices y `shared_buffers` |
| Ingesta | ~10.000 feeds cada 15–30 min → 5–10 peticiones/s | Sí, con más workers de ingesta |

### Sobre las sugerencias recibidas

1. **APIs gratuitas externas (Gemini, Groq, Cloudflare Workers AI): no como base.**
   - **Gemini:** su plan gratuito bajó en 2026 a ~5 peticiones/min y ~100/día, y Google usa los textos para mejorar sus productos.
   - **Privacidad:** choca con nuestra política y la ficha de la App Store ("tu lectura no se envía a servicios de IA externos").
   - **El resto:** sus límites gratuitos cambian a menudo.
   - **Si hiciera falta respaldo:** de pago, con procesamiento en la UE (Gemini vía Vertex AI en región europea), opcional y avisado al usuario. O mejor, la segunda máquina local.
2. **Voz del dispositivo para planes bajos: ya es así.** El plan gratis usa la voz del iPhone, sin coste para el servidor.
3. **Cloudflare delante con caché de 90 días: con matices.**
   - **Audio:** las condiciones del plan gratuito prohíben servir una proporción grande de audio por la CDN. Además, nuestras URL de audio van firmadas por usuario y no se cachearían entre usuarios.
   - **Alternativa válida:** alojar el audio en Cloudflare R2, con nombres públicos imposibles de adivinar.
   - **Resúmenes:** van en la API autenticada; no deben cachearse públicamente.
   - **Fichas estáticas de la web:** sí se pueden cachear.
4. **Cola asíncrona con 202 y consulta periódica: hecho.** Concurrencia de 2 por iGPU.
5. **Pregeneración de fuentes "calientes": hecho para las fuentes de VIP de noche.** Se puede ampliar a "fuente leída por ≥3 usuarios".
6. **SQLite con WAL: no aplica.** Usamos PostgreSQL, que ya escribe con WAL. Los 72 MB actuales caben enteros en RAM.

### Plan por fases

- **Hasta ~500 usuarios:** lo actual basta (cola, lotes de 2, pregeneración nocturna, cuota gratis de 3 al día).
- **500–3.000:**
  - **Audio:** subir el tope o bajar a 32 kbps; valorar R2.
  - **Pregeneración:** ampliarla por popularidad.
  - **Panel:** vigilar en Admin → Recursos la espera media de la cola.
- **3.000–10.000:**
  - **IA:** una segunda máquina con iGPU (~450 €, objetivo del fondo de patrocinio) que consuma la misma cola.
  - **Bee:** el actual queda para la API, la BD y la ingesta.
  - **Respaldo:** externo de pago en la UE solo si las colas se disparan.

## Fuentes

- [GitHub Sponsors: about](https://docs.github.com/en/sponsors/getting-started-with-github-sponsors/about-github-sponsors)
- [Impuestos de patrocinios open source (2026)](https://beancount.io/blog/2026/07/08/open-source-maintainer-sponsorship-income-taxes-guide)
- [Cambios en el plan gratuito de Gemini API (abril 2026)](https://agentdeals.dev/gemini-api-pricing-changes)
- [Gemini API: plan gratuito y uso de datos](https://www.costbench.com/software/llm-api-providers/google-gemini-api/free-plan/)
- [Gemini en regiones de la UE (Vertex AI)](https://docs.cloud.google.com/gemini/enterprise/docs/locations?authuser=0)
- [Cloudflare y el contenido no HTML (cláusula 2.8)](https://community.cloudflare.com/t/multimedia-hosting-on-cloudflare/408289)
