# uFeed en iPhone Duo y HomeView — estudio para versiones futuras

Estado: estudio, nada implementado. Fecha: 2026-10-13 (actualizado tras el evento "Welcome home").

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
- **Guía de diseño de Apple ("Designing for iPhone Duo", HIG):**
  - **Mismo estado en las dos pantallas.** La pantalla grande muestra un nivel
    más de jerarquía. El ejemplo de Apple es Mail: cerrado, lista *o* correo;
    abierto, lista *y* correo lado a lado. Es nuestra disposición de dos paneles.
  - **Controles en el lateral.** La pantalla exterior es más ancha y baja, así
    que el sistema pasa los controles a los lados para no gastar altura. En
    horizontal también se quedan en un lado.
  - **Pliegue y asimetría.** Recomienda contenedores adaptables, como vistas
    partidas que ajustan el ancho de cada panel, y la API `ReservedRegion` para
    que nada importante quede en la franja central del pliegue.
- **No sabemos todavía:**
  - la escala de puntos (@2x o @3x);
  - cómo llega `ReservedRegion` a Flutter. Lo más probable es que haga falta
    un pequeño canal nativo que pase la franja a Dart; mirar primero si Flutter
    la expone en `MediaQuery.displayFeatures`;
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

Presentada hoy, 13 de octubre (evento "Welcome home"). Se espera en tiendas a
mediados de noviembre.

- Pantalla táctil Liquid Retina de 7". Cuadrícula de apps y widgets como en
  iPhone y iPad. Siri AI.
- **Hasta seis personas reconocidas por la cámara**, cada una con su propia
  pantalla de inicio, sus apps y sus widgets, en privado.
- **Más o menos detalle según la distancia:** desde lejos, información general
  y simplificada; al acercarse, detalles más ricos.
- Se configura desde el iPhone.
- **Sin App Store propia.** Las apps de terceros llegan como en CarPlay:
  - HomeView muestra las **apps de audio y vídeo compatibles del iPhone (o
    iPad) cercano**;
  - las apps de audio hechas para CarPlay, como Spotify o Audible,
    funcionan tal cual y pueden aparecer solas tras la configuración;
  - Apple aún no ha detallado si hacen falta pasos extra, cómo funciona la
    proximidad del iPhone ni si habrá widgets de terceros.

Revisar cuando Apple publique la documentación para desarrolladores.

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

- **Barra de escucha en el lateral, según la guía de Apple:**
  - cerrado: en vertical, pegada a un lado en lugar de abajo;
  - abierto: en el panel del lector;
  - en horizontal: siempre en un lado.

  Así la lista conserva altura en la pantalla exterior.
- **Nada en el pliegue:** la división entre paneles se coloca en la franja de
  `ReservedRegion`, y el lector deja un margen en ella. Si la franja no llega
  a Flutter, la división va al 40/60 como respaldo.

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

La entrada natural es **uFeed como app de audio de CarPlay**: Post radio ya
es una "radio de noticias". Con una sola pieza, uFeed sale en tres sitios:

- en el coche (CarPlay);
- en HomeView;
- en la pantalla de bloqueo del iPhone, que ya funciona.

1. **App de audio CarPlay (prioridad):**
   - **Plantillas:**
     - `CPListTemplate` con "Post radio", "Sin leer" y las carpetas;
     - `CPNowPlayingTemplate` con título, fuente e imagen, que ya publica
       `audio_service`;
     - siguiente y anterior post.
   - **Requisito:** el permiso `com.apple.developer.carplay-audio`, que se
     pide a Apple y tarda. Pedirlo pronto.
   - **Implementación:**
     - parte en Swift (escena de CarPlay; ya tenemos `UIScene`) que habla con
       el `ListenController` de Flutter por un canal;
     - existe el paquete `flutter_carplay`, a evaluar.
   - **Perfiles por persona:** en HomeView cada persona tiene su pantalla y su
     iPhone, así que cada uno oye sus propias fuentes. Encaja con uFeed, donde
     todo va por cuenta.
   - **Distancia:** en el lado de la app no hay nada que hacer. Las plantillas
     de CarPlay son del sistema, y HomeView las adapta (letra grande de lejos,
     más detalle de cerca).
2. **Siri y App Intents:**
   - «Oye Siri, pon la radio de uFeed» arranca Post radio;
   - «¿Qué hay nuevo en uFeed?» lee los titulares (vía `/digest`).

   Sirve en iPhone, CarPlay y HomeView.
3. **Widget de titulares (WidgetKit):**
   - útil en el iPhone pase lo que pase;
   - en HomeView solo si Apple abre los widgets de terceros, que hoy no está
     confirmado;
   - con dos tamaños (lejos: número de sin leer y el titular principal;
     cerca: 3–5 titulares), por si llega a usarse con la distancia;
   - datos compartidos con Flutter por un App Group (paquete `home_widget`).
4. **AirPlay:** la salida de seguridad. Post radio ya suena en cualquier
   altavoz AirPlay.

Coste estimado: 4–6 días, más la espera del permiso de CarPlay.

- CarPlay audio: 2–3 días.
- App Intents: 1–2 días.
- Widget: 1–2 días.

Se solapa con la etapa 6 del plan nativo (Siri y widgets).

## 4. Orden propuesto

1. **1.0 (sin cambios):** iPhone, como está. La app ya funciona en el Duo como
   app de iPhone; confirmar en el simulador cómo se ve cuando salga el SDK.
2. **1.1 "Duo":** disposición adaptable de dos y tres paneles. Es lo que más se
   nota y lo que se puede anunciar ("uFeed, preparada para iPhone Duo").
3. **1.2 "Casa y coche":** uFeed como app de audio de CarPlay, más Siri.
   Sale a la vez en el coche y en HomeView. **Pedir ya el permiso de CarPlay
   audio**, aunque se implemente después, porque Apple tarda. El widget va
   en el mismo paquete o justo después.
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
- MacRumors, [HomeView Runs Third-Party Apps From Your iPhone or iPad](https://www.macrumors.com/2026/10/13/homeview-third-party-apps/)
- 9to5Mac, [Will HomeView support third-party apps?](https://9to5mac.com/2026/10/13/will-homeview-support-third-party-apps-heres-what-apple-says/)
- Apple HIG, "Designing for iPhone Duo" y presentación de HomeView (resumen aportado por el usuario)
- Mac Observer, [Apple HomeView (HomePad): Everything To Know](https://www.macobserver.com/tips/round-ups/apple-homeview-homepad-everything-to-know-about-the-smart-display-before-launch/)
