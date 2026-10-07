# uFeed nativa (Flutter) — plan de trabajo

Documento vivo: se retoma la semana del 5 de octubre de 2026. Marcar las
casillas según se avance y anotar decisiones al final.

## 0. Punto de partida

- **7 oct 2026: proyecto Flutter creado en `App/`** (iOS, Android, macOS,
  Windows, Linux y web). Hasta entonces toda la interfaz era la PWA SvelteKit
  de `Frontend/` (~10.500 líneas).
- **El servidor ya está completo** y no hace falta tocarlo para la app: cuentas,
  fuentes, carpetas, filtros, artículos, artículo completo, voz del servidor en
  directo, traducción, resúmenes IA, Tendencias, sincronización sin conexión.
  El contrato está en `API/openapi.json`.
- `mobile/` contiene el envoltorio Capacitor: sirve solo para pruebas internas.
  **No se envía a la App Store** (guía 4.2: una web envuelta se rechaza).
- La ficha de la tienda está redactada en `docs/APPSTORE.md`. La crearemos en
  App Store Connect cuando haya ejecutable (decisión del 1 de octubre de 2026).

## 1. Objetivo

Un lector RSS nativo al estilo Newsify/Reeder, para iPhone primero (y luego
Android con el mismo código). Usa la API existente y añade lo que la web no
puede dar bien:

- audio en segundo plano fiable, con controles en la pantalla de bloqueo;
- notificaciones locales de novedades;
- copia de seguridad en iCloud;
- rendimiento y gestos nativos.

**Fuera de la app:** Admin y Curación siguen siendo solo web. La app enlaza a
ellas si el rol lo permite.

## 2. Pila técnica (en línea con AuraBox / TPV Midnight)

| Necesidad | Paquete |
| --- | --- |
| Estado | `flutter_riverpod` 3 |
| Navegación | `go_router` |
| HTTP + reintentos y refresco del JWT | `dio` (interceptor de refresh) |
| Cliente API | escrito a mano (`lib/api/`): clases simples con `fromJson`, sin generación de código, solo las rutas que usa la app |
| Base de datos local (sin conexión, cola de cambios) | `drift` (SQLite) |
| Tokens | `flutter_secure_storage` (Keychain) |
| Ajustes | `shared_preferences` |
| HTML del artículo | `flutter_widget_from_html_core` + widgets propios (imágenes, YouTube/Vimeo, audio de podcast) |
| Imágenes | `cached_network_image` |
| Voz del servidor y Post radio | `just_audio` + `audio_service` (pantalla de bloqueo, Centro de control, AirPods) |
| Voz del dispositivo | `flutter_tts` (AVSpeechSynthesizer; da progreso por palabra para el resaltado) |
| Notificaciones locales | `flutter_local_notifications` + `workmanager` / `background_fetch` (BGAppRefreshTask) |
| iCloud | canal de plataforma propio en Swift (NSUbiquitousKeyValueStore para ajustes; documento OPML en iCloud Drive) |
| Compartir / abrir enlaces | `share_plus`, `url_launcher` |
| Idiomas | `flutter_localizations` + `intl` (ES/EN, ARB) |

Identificador: `es.uverse.ufeed` (el mismo de la ficha). Android:
`es.uverse.ufeed`.

## 3. Etapas

Las estimaciones son jornadas de trabajo conjunto, orientativas.

### Etapa 0 — Preparación (½–1 día)

- [x] Regenerar `API/openapi.json` desde el Bee (1 oct: ya incluye `/full`,
      `/me/delete` y `/me/diag`).
- [x] Decidir: cliente generado o modelos a mano (ver §6): a mano.
- [x] `flutter create` en `App/` (todas las plataformas), con lints, ARB ES/EN,
      iconos (`scripts/make_icons.py` + `flutter_launcher_icons`) y colores de la web.
- [x] Job de CI: formato + `flutter analyze` + `flutter test` (job `app`).
- [ ] **Prueba técnica de audio en directo.** Comprobar que `just_audio` (AVPlayer)
      reproduce el MP3 que crece en `/api/audio/...` mientras se genera, y que
      sigue con la pantalla bloqueada. Si no, plan B: esperar al fichero
      completo, que con voz cacheada es instantáneo y si no tarda ~5–15 s.

### Etapa 1 — Esqueleto, cuenta y lista (3–4 días)

- [x] Login, registro (si el sitio lo permite: `GET /site`), recuperar contraseña y refresco del token.
- [x] Barra lateral / cajón: Todo, Sin leer, Guardados, Favoritos, carpetas y fuentes con contadores.
- [ ] Lista de artículos: paginación y tirar para actualizar hechos; faltan las vistas tarjetas/mosaico.
- [x] Gestos: deslizar para leído/guardado y pulsación larga para marcar leído.
- [x] Marcar todo como leído (hasta lo listado, como la web).
- [ ] Tendencias y "Para ti".
- [ ] Modo claro/oscuro y tamaño de texto (Dynamic Type).

### Etapa 2 — Lector (3–4 días)

- [ ] Render del HTML con imágenes, listas, citas, YouTube/Vimeo como tarjeta y podcast como reproductor.
- [ ] Artículo completo automático para extractos (`/full`) y conmutador completo/extracto.
- [ ] Resumen IA plegable con botón "✨ Resumir" y contador de segundos.
- [ ] Traducir (EN↔ES) y "Leer en mi idioma".
- [ ] Siguiente/anterior deslizando y marcar leído al abrir.
- [ ] Eventos de lectura (`read-event`, `engage`).
- [ ] Compartir, abrir en web, guardar y favorito.
- [ ] Tipografía Atkinson Hyperlegible y tamaño de texto.

### Etapa 3 — Sin conexión y sincronización (2–3 días)

- [ ] Cola de cambios en drift (leído, guardado, favorito, marcar todo, eventos con
      su hora), enviada al recuperar red o abrir la app. Mismo contrato que la web (`/sync`).
- [ ] Guardados disponibles sin red: texto completo, imágenes y audio.
- [ ] Caché de la última lista para arranque instantáneo.

### Etapa 4 — Escucha (4–5 días)

- [ ] Barra de escucha fija: reproducir/pausa, ±15 s, velocidad.
- [ ] Voz del servidor (según plan `tts_server`) o del dispositivo; sexo y ritmo.
- [ ] Pantalla de bloqueo y Centro de control con título, fuente e imagen.
- [ ] Interrupciones (llamadas, Siri), auriculares desconectados y AirPods.
- [ ] Resaltado de la frase leída (con `flutter_tts` hay progreso por palabra; con
      la voz del servidor, posición proporcional como en la web).
- [ ] Lectura automática al abrir.
- [ ] **Post radio:**
  - [ ] cola de posts y jingle entre ellos;
  - [ ] 70 % escuchado = leído;
  - [ ] límites del plan (`radio_max_posts`, `radio_max_minutes`);
  - [ ] "siguiente" desde la pantalla de bloqueo;
  - [ ] precarga del siguiente audio.

### Etapa 5 — Gestión y ajustes (2–3 días)

- [ ] Añadir fuente (URL o búsqueda con `/discover`) y catálogo de temas para empezar (onboarding).
- [ ] Carpetas, silenciar fuentes y filtros por palabra.
- [ ] Importar/exportar OPML (selector de archivos y compartir).
- [ ] Ajustes:
  - [ ] cuenta y cambiar contraseña;
  - [ ] **eliminar mi cuenta** (obligatorio en la App Store);
  - [ ] voz, accesibilidad, apariencia e idioma.
- [ ] Enlaces a Privacidad, Soporte y, según el rol, Admin/Curación en web.

### Etapa 6 — Extras nativos de iOS (3–4 días)

- [ ] **IA del propio iPhone primero, servidor como respaldo** (canal de plataforma en Swift):
  - [ ] Resumen con Foundation Models (iOS 26+, iPhone 15 Pro o posterior con
        Apple Intelligence). Gratis, sin red y privado. Límite de 4K tokens en el
        dispositivo: trocear los artículos largos (resumir partes y luego unirlas).
        Verificar la calidad en español frente a Qwen3-4B antes de activarlo.
  - [ ] Traducción con el framework Translation de Apple (es↔en sin red) en
        lugar de opus-mt del servidor.
  - [ ] Si el iPhone no puede, se usa la cola del servidor como ahora. Lo generado
        en el iPhone no se sube a la caché compartida: es local y no está verificado.
  - Android: Gemini Nano (ML Kit GenAI) solo resume en inglés, japonés y coreano y
    en pocos modelos; ML Kit Translation sí sirve para es↔en.
- [ ] **Notificaciones locales:** comprobación periódica en segundo plano (iOS decide
      cuándo, típicamente cada pocas horas).
  - [ ] Avisa de N artículos nuevos en las fuentes o carpetas elegidas, o da un
        resumen diario a la hora que elija el usuario.
  - [ ] Sin servidor de push ni datos a terceros.
  - [ ] Valorar un endpoint ligero de recuento ("nuevos desde T") si `/articles` resulta pesado.
- [ ] **iCloud:**
  - [ ] ajustes sincronizados entre dispositivos (clave-valor);
  - [ ] copia automática del OPML en iCloud Drive para restaurar fuentes si se pierde la cuenta o el servidor.
- [ ] Opcionales, por valor/esfuerzo:
  - [ ] extensión de Compartir ("Añadir a uFeed" desde Safari);
  - [ ] widget de la pantalla de inicio (últimos titulares);
  - [ ] atajos de Siri ("Pon mi Post radio");
  - [ ] CarPlay (audio).
- [ ] **Iniciar sesión con Apple: opcional.** Solo es obligatorio si se añaden
      inicios de sesión de terceros. Requiere:
  - [ ] Services ID y clave en el portal de Apple;
  - [ ] endpoint `/auth/apple` en el backend que verifique el `id_token`.

### Etapa 7 — Pulido y accesibilidad (2–3 días)

- [ ] VoiceOver: etiquetas en todos los botones-icono.
- [ ] Dynamic Type y contraste.
- [ ] iPad: diseño en dos columnas.
- [ ] Estados vacíos y de error, sin red y servidor caído.
- [ ] Rendimiento con listas largas.
- [ ] Pruebas de widgets y de la cola sin conexión.

### Etapa 8 — Publicación (1–2 días + espera de Apple)

- [ ] Firma automática en Xcode (descarga certificados y perfiles) y archivo de Release.
- [ ] **TestFlight interno** para probar en tus dispositivos.
- [ ] Crear la ficha en App Store Connect con `docs/APPSTORE.md`. Actualizar los
      textos con lo que de verdad tenga la app (notificaciones, iCloud…).
- [ ] Capturas 6,9" en ES y EN (lista, lector, escucha, Post radio, traducción, ajustes).
- [ ] Cuestionario de privacidad: añadir lo que cambie (p. ej. iCloud no cuenta
      como recogida nuestra).
- [ ] Contraseña de la cuenta demo en "Información para la revisión" (la escribe el usuario).
- [ ] Enviar a revisión: solo con OK explícito.
- [ ] Después: Google Play con el mismo código (ajustes de Android y ficha).

**Total orientativo:** 4–6 semanas a ritmo normal. El orden permite tener una
app usable (etapas 1–3) en unas dos semanas y probarla en TestFlight antes de
los extras.

## 4. Paridad con la web (comprobación final)

- [ ] Todo / Sin leer / Guardados / Favoritos / carpetas / fuentes
- [ ] Vistas lista, tarjetas y mosaico; gestos
- [ ] Artículo completo; contenido multimedia incrustado
- [ ] Resumen IA; traducción; leer en mi idioma
- [ ] Voz servidor/dispositivo; Post radio; audio sin conexión
- [ ] Accesibilidad: autolectura, resaltado, tamaño, Atkinson
- [ ] Sin conexión con cola de cambios
- [ ] Tendencias, Para ti, similares
- [ ] Fuentes, carpetas, filtros, OPML, catálogo y onboarding
- [ ] Eliminar cuenta; privacidad; soporte

## 5. Riesgos

| Riesgo | Mitigación |
| --- | --- |
| Que AVPlayer no reproduzca bien el MP3 "en directo" | Prueba en la etapa 0. Plan B: esperar al fichero completo. |
| HTML de feeds muy variado | Render propio para lo común y "Abrir en web" como salida. |
| Revisión 4.2 / 4.8 de Apple | Ser cliente nativo de verdad. Sin login de terceros, Apple no es obligatorio. |
| Segundo plano de iOS poco predecible para notificaciones | Prometer "avisos periódicos", no tiempo real. Si hiciera falta push real, APNs en el backend (fase posterior). |
| Carga en el Bee si crecen los usuarios | Ya existe el monitor de recursos (Admin → Recursos). |

## 6. Decisiones pendientes (revisar al retomar)

1. ~~¿Cliente API generado o a mano?~~ Decidido: a mano.
2. ~~¿iPad en la 1.0?~~ Decidido: solo iPhone.
3. ~~¿Android a la vez?~~ Decidido: proyecto multiplataforma desde el principio;
   se prueba y pule primero en iOS.
4. Notificaciones: ¿resumen diario a una hora, por fuente/carpeta, o ambos?
5. ¿Qué opcionales de la etapa 6 entran en la 1.0?
6. ¿Iniciar sesión con Apple en la 1.0?
7. Copyright de la ficha: "© 2026 Manuel Rodríguez" (confirmar).
8. ¿Retirar `mobile/` (Capacitor) cuando la nativa esté en TestFlight?

## 7. Registro de decisiones

- 2026-10-01: no se crea la ficha en App Store Connect hasta tener ejecutable
  nativo. No se sube nada sin OK explícito.
- 2026-10-07: cliente de la API escrito a mano en Dart (como `api.ts` en la
  web), sin `freezed` ni generación de código. Proyecto Flutter para todas las
  plataformas; la 1.0 se centra en iPhone (iPad en modo iPhone). Los extras
  nativos (IA del dispositivo, iCloud, segundo plano) se hacen primero en iOS.
  Destino mínimo iOS 16.
