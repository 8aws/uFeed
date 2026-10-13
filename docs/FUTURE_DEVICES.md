# uFeed en iPhone Duo y HomeView — estudio para versiones futuras

Estado: estudio, nada implementado. Fecha: 2026-10-13.

Objetivo: llegar pronto a los dos dispositivos nuevos de Apple como reclamo
para los primeros usuarios. Quien compra un plegable de 2.000 $ busca apps que
aprovechen la pantalla abierta, y en la App Store aún hay pocas.

## 1. Lo que se sabe

### iPhone Duo (plegable)

Apple lo presentó en septiembre de 2026; sale a la venta el 23 de octubre con
iOS 27.1. Datos de MacRumors:

| | Cerrado (exterior) | Abierto (interior) |
| --- | --- | --- |
| Diagonal | 5,4" | 7,6" |
| Píxeles | 1398 × 2034 | 1878 × 2670 |
| Densidad | 460 ppi | 430 ppi |

- Las dos pantallas tienen la misma proporción (≈ 0,70). Al abrirlo, el
  contenido se agranda sin cambiar de forma.
- Split View con dos apps o dos ventanas de la misma app. Dock vertical al
  lado. Las apps se reajustan al plegar, al girar y al darle la vuelta.
- Apple ya acepta apps adaptadas al Duo en la App Store (desde el 5 de octubre).
- **No sabemos todavía:**
  - la escala de puntos (@2x o @3x);
  - si hay una "bisagra" que la app pueda detectar (Apple la anuncia sin pliegue
    visible);
  - cómo se muestran las apps de iPhone no adaptadas.

  Confirmarlo con el SDK de Xcode 27.1 en el simulador del Duo.

Cálculo aproximado en puntos, a confirmar:

- @3x: unos 466 × 678 pt cerrado y 626 × 890 pt abierto.
- @2x: unos 700 × 1017 pt cerrado y 939 × 1335 pt abierto.

Con @3x, el exterior ya es más ancho que el de un 16 Pro (402 pt) y el interior
se parece a un iPad mini en vertical (744 pt).

**Nota:** la adopción de `UIScene` que hicimos para que la app arrancase en
iOS 27 (etapa 5) es justo lo que hace falta para ventanas de tamaño variable y
Split View. Ese trabajo ya está hecho.

### HomeView (pantalla del hogar)

Se presenta hoy, 13 de octubre (evento "Welcome home"). Se espera que llegue a
las tiendas a mediados de noviembre. Todo lo de abajo es rumor hasta ver lo
anunciado:

- Pantalla cuadrada de unas 6", en dos versiones: sobremesa con altavoz y de pared.
- homeOS, basado en tvOS. Solo apps de Apple y **sin App Store**.
- Las apps de terceros aparecerían como **widgets desde un iPhone cercano**.
- Mucho Siri, cámara para reconocer quién mira y elementos que crecen o
  encogen según la distancia. Pensada para verse desde el otro lado de la
  habitación.

Revisar esta sección cuando Apple publique la información para desarrolladores.

## 2. Propuesta para iPhone Duo

En vez de diseñar para un aparato concreto, la idea es que la app cambie de
disposición según el **ancho disponible**: el de la pantalla, el de media
pantalla en Split View o el del iPad más adelante. Así una sola lógica sirve
para los tres casos.

| Ancho | Cuándo pasa | Disposición |
| --- | --- | --- |
| < 600 pt | iPhone normal, Duo en Split View estrecho | La actual: lista ↔ lector, menú lateral desplegable |
| 600–900 pt | Duo abierto en vertical, Duo cerrado en horizontal | **Dos paneles:** lista a la izquierda (≈ 40 %) y lector a la derecha; el menú pasa a una barra de iconos |
| > 900 pt | Duo abierto en horizontal, iPad | **Tres paneles:** menú de fuentes fijo, lista y lector |

Bocetos (Duo abierto, vertical, unos 626 pt):

```
┌──────────┬─────────────────────────┐
│ ☰ Sin leer│  El País · hace 2 h     │
│──────────│  Titular del artículo   │
│ ▣ Titular │  ─────────────────────  │
│ ▣ Titular │  Texto del artículo…    │
│ ▣ Titular◀│                         │
│ ▣ Titular │                         │
│          │ ▶ ⏸  −15  +15  1,2×     │
└──────────┴─────────────────────────┘
```

Detalles que marcan la diferencia:

- **Mosaico de 3–4 columnas** en el panel de lista cuando se usa el modo
  mosaico. El perfil denso que acabamos de hacer (imagen de 84 px, título de
  13 px) escala bien: solo cambia el número de columnas.
- **Post radio en dos paneles:** la cola a la izquierda y el lector siguiendo
  al post a la derecha. Es el caso de uso que mejor vende el plegable.
- **Abrir y cerrar sin perder el sitio:**
  - el artículo abierto y la posición del scroll se mantienen;
  - al cerrar el Duo con un artículo abierto, se queda el lector;
  - al abrirlo, aparece la lista al lado.

  Cuidado con no reconstruir los providers de Riverpod al cambiar de tamaño.
- **Dos ventanas de uFeed en Split View**, por ejemplo una fuente en cada una.
  Llega casi gratis con `UIScene`, pero hay que comprobar que el
  estado compartido (outbox y caché local) aguanta dos instancias a la vez.
- **Pliegue:** si el SDK informa de una bisagra (`MediaQuery.displayFeatures`
  en Flutter), se pone la división entre paneles justo en ella. Si no, la
  división va al 40/60.
- **Arrastrar y soltar** un artículo de uFeed a Notas o Mail en Split View
  (como enlace).

Coste estimado: 4–6 días.

- Disposición adaptable con `LayoutBuilder` y paneles: 2–3 días.
- Conservar el estado al plegar: 1 día.
- Pruebas en el simulador del Duo y en Split View: 1–2 días.

Reutiliza `HomeScreen`, `ReaderScreen` y `ArticleTile` tal cual. Sirve
además como base del iPad, lo que cambia la decisión 2 del plan nativo ("solo
iPhone en la 1.0") en una versión posterior.

## 3. Propuesta para HomeView

Sin App Store, uFeed entraría por tres vías que no dependen de homeOS:

1. **Widget de titulares (WidgetKit):**
   - los 3–5 últimos titulares sin leer, en letra grande, con fuente e
     imagen y pensados para leerse de lejos;
   - sirve también en la pantalla de inicio y de bloqueo del iPhone, así que
     no se pierde nada si HomeView no lo muestra;
   - necesita una extensión nativa en Swift; los datos se comparten con
     Flutter por un App Group (paquete `home_widget`).
2. **Siri y App Intents:**
   - «Oye Siri, ¿qué hay nuevo en uFeed?» lee los titulares;
   - «Pon la radio de uFeed» arranca Post radio.

   Encaja con lo que ya existe: `/digest` para el resumen y la voz del
   servidor para el audio.
3. **Audio por AirPlay:** Post radio ya publica la información de "Ahora
   suena" (`audio_service`). Si HomeView hace de altavoz AirPlay, las noticias
   sonarían en casa sin hacer nada más.

Coste estimado: 4–5 días.

- Widget: 2–3 días.
- App Intents: 1–2 días.
- Pruebas de AirPlay: medio día.

Gran parte del trabajo coincide con la etapa 6 del plan nativo (widgets y
Siri). Conviene hacerlo a la vez.

## 4. Orden propuesto

1. **1.0 (sin cambios):** iPhone, como está. La app ya funciona en el Duo como
   app de iPhone; confirmar en el simulador cómo se ve cuando salga el SDK.
2. **1.1 "Duo":** disposición adaptable de dos y tres paneles. Es lo que más se
   nota y lo que se puede anunciar ("uFeed, preparada para iPhone Duo").
3. **1.2 "Casa":** widget de titulares y App Intents. Sirve en iPhone desde el
   primer día y en HomeView si Apple abre los widgets.
4. iPad, sobre la misma disposición de la 1.1.

## 5. Ideas para atraer a los primeros usuarios

- Insignia o plan "Early adopter" para quien se dé de alta antes de una fecha
  (los roles y planes ya existen en el backend).
- Nota en la ficha de la App Store y en la web: "Optimizada para iPhone Duo".
- Convocar una TestFlight pública para usuarios de Duo antes de la 1.1.

## Fuentes

- MacRumors, [iPhone Duo: Everything We Know](https://www.macrumors.com/roundup/iphone-duo/)
- MacRumors, [Apple's All-New Home Hub Will Be Revealed October 13](https://www.macrumors.com/2026/10/10/apple-to-unveil-all-new-type-of-device/)
- Tech Times, [Apple 'HomeView' Smart Home Hub Will Ship Out Next Month](https://www.techtimes.com/articles/328898/20261012/apple-homeview-smart-home-hub-will-ship-out-next-month-what-expect.htm)
- Mac Observer, [Apple HomeView (HomePad): Everything To Know](https://www.macobserver.com/tips/round-ups/apple-homeview-homepad-everything-to-know-about-the-smart-display-before-launch/)
