# uFeed — App Store listing (ES / EN)

Everything App Store Connect asks for, ready to paste. Limits noted in
brackets; texts are within them.

## App information

| Field | Value |
| --- | --- |
| Name [30] | `uFeed: RSS y noticias` (record created 2026-10-13; it stayed this one for every language, the English name `uFeed: RSS & News` was not used) |
| Name on the Home Screen | uFeed (`CFBundleDisplayName`, can differ from the store name) |
| Bundle ID | `es.uverse.ufeed` (iOS and Android; App Store build checked 2026-10-13) |
| SKU | `ufeed-ios-1` (final; can't be changed after the app record is created) |
| Primary category | News |
| Secondary category | Productivity |
| Support URL | https://ufeed.uverse.es/support |
| Marketing URL | https://ufeed.uverse.es/info |
| Privacy policy URL | https://ufeed.uverse.es/privacy |
| Copyright | © 2026 Manuel Rodríguez |
| Price | Free (no in-app purchases) |

Name check (2026-10-13, iTunes Search API, Spain and US stores): an app
called **"ufeed"** already exists (Portuguese-language social network by
josue araujo moreira, `com.negoplay.ufeed.social`, updated 2026-08). App Store
names are unique, so plain "uFeed" will be refused when creating the record.
"uFeed RSS", "uFeed Reader" and "uFeed: RSS y noticias" return no match.

## Localized text

### Español (España)

**Subtítulo** [30]
Lee y escucha tus blogs y webs

**Texto promocional** [170]
Artículos completos aunque el feed solo dé un extracto, voz natural con la pantalla bloqueada, Post radio y traducción al instante. Sin anuncios ni rastreo.

**Descripción** [4000]
uFeed es un lector de noticias RSS rápido y limpio para leer… y escuchar.

ARTÍCULO COMPLETO
Muchas webs solo publican un extracto en su feed. uFeed trae el artículo entero de la web —texto, imágenes y listas— para que no tengas que salir de la app.

ESCUCHA TUS NOTICIAS
• Voz neuronal natural, femenina o masculina, que sigue sonando con la pantalla bloqueada y se controla desde la pantalla de bloqueo.
• O la voz de tu iPhone, también sin conexión.
• Ajusta la velocidad, de 0,75× a 2×.

POST RADIO
Tus noticias una tras otra, como un podcast, con un breve sonido entre posts. Solo se marca como leído lo que escuchas de verdad.

EN TU IDIOMA
Traduce al instante entre español e inglés y escucha cada artículo en tu idioma.

RESÚMENES CON IA
Resúmenes en tu idioma generados en nuestro propio servidor: tu lectura no se envía a servicios de IA externos.

SIN CONEXIÓN
Tus artículos guardados, con sus imágenes y su audio, disponibles sin red. Lo que marques se sincroniza al volver.

ACCESIBLE
Lectura automática al abrir, compatible con VoiceOver y con el texto grande del sistema, y tipografía Atkinson Hyperlegible, pensada para baja visión.

Y ADEMÁS
Carpetas, filtros por palabras, fuentes silenciadas, vistas de lista, tarjetas y mosaico, gestos para marcar y guardar, Tendencias, Para ti, importación y exportación OPML y sugerencias por temas para empezar.

PRIVADO
Sin anuncios, sin rastreadores y sin analítica de terceros. Puedes borrar tu cuenta desde Ajustes cuando quieras.

**Palabras clave** [100]
lector,feed,atom,blogs,prensa,titulares,podcast,radio,voz,escuchar,traducir,resumen,offline

**Novedades de esta versión**
Primera versión de uFeed para iPhone.

### English (U.S.)

**Subtitle** [30]
Read and listen to your feeds

**Promotional text** [170]
Full articles even when the feed only has an excerpt, a natural voice with the screen locked, Post radio and instant translation. No ads, no tracking.

**Description** [4000]
uFeed is a fast, clean RSS news reader to read… and to listen.

FULL ARTICLE
Many sites only publish an excerpt in their feed. uFeed brings the whole article from the website —text, images and lists— so you don't have to leave the app.

LISTEN TO YOUR NEWS
• A natural neural voice, female or male, that keeps playing with the screen locked and is controlled from the lock screen.
• Or your iPhone's own voice, offline too.
• Set the speed, from 0.75× to 2×.

POST RADIO
Your news one after another, like a podcast, with a short chime between posts. Only what you actually hear is marked as read.

IN YOUR LANGUAGE
Instant Spanish ↔ English translation, and every article read aloud in your language.

AI SUMMARIES
Summaries in your language made on our own server: your reading is never sent to outside AI services.

OFFLINE
Your saved articles, with their images and audio, available without a connection. What you mark syncs when you're back.

ACCESSIBLE
Read aloud on open, VoiceOver and system large text support, and the Atkinson Hyperlegible font, designed for low vision.

AND ALSO
Folders, keyword filters, muted sources, list, card and masonry views, gestures to mark and save, Trending, For you, OPML import and export, and topic suggestions to get started.

PRIVATE
No ads, no trackers, no third-party analytics. Delete your account from Settings whenever you want.

**Keywords** [100]
reader,feed,atom,blogs,press,headlines,podcast,radio,voice,listen,translate,summary,offline

**What's new**
First release of uFeed for iPhone.

## App Review information

**Sign-in required:** no (since 1.1, guideline 5.1.1(v)): the sign-in screen
has "Continue without an account", which opens the app with a few starter
feeds. An account is only needed for what costs server resources.
**Demo account (for the features that need an account):** `demo@demo.com` / `demo`
(Protected on the server: its password can't be changed and it can't be
deleted, so it keeps working for review.)

**Notes for the reviewer (English):**
uFeed is an RSS/Atom news reader backed by our own server (ufeed.uverse.es).
No account is needed to use it: on the first screen tap "Continue without an
account". That creates an anonymous guest profile (no email, no password, no
personal data) with a few starter feeds; guests can read, add up to 20 feeds,
organise folders, save articles, listen with the device voice and use the
text-size options. Creating an account (Settings > "Create an account with my
data") keeps their feeds and saved articles and unlocks AI summaries,
translation, the server voice, Post radio and syncing across devices.
"Leave and delete my data" removes the guest profile; accounts have "Delete
account" in Settings.
The demo account (VIP plan) already follows several Spanish and English feeds
and shows every feature. Features by plan, none hidden: AI summary,
translation and server voice and Post radio are shown only when the plan
includes them.
Technical notes: playing the live server voice uses a small hidden web view
inside the app (it only plays the audio stream, shows nothing and loads only
our own server's audio URL); the app contains no obfuscated or dormant code.
To try the main features:
1. Open any article. If the feed only has an excerpt, the full article is
   loaded from the publisher's website automatically.
2. At the bottom of the article, tap "Listen" (headphones): the article is
   read aloud by our server voice. Audio keeps playing with the screen locked
   and is controlled from the Lock Screen — this is why the app declares the
   "audio" background mode. The sliders button next to it opens "Voice and
   reading" (device or server voice, female or male, offline audio for saved
   articles).
3. The radio button next to "Listen" starts Post radio: posts are read one
   after another, with "next" on the Lock Screen.
4. In an English article, the "..." menu > "Translate" shows it in Spanish
   (and "Show original" goes back). "AI summary" at the top of an article
   opens a short summary.
5. Swipe an article in the list to mark it read or save it. Saved articles
   (with images and audio) work offline.
6. Settings (side menu, bottom) > "Delete account" deletes the account and
   all its data. It is disabled only for this shared demo account, so that it
   keeps working for review.
Summaries, translation and voice run on our own server; the app contains no
third-party AI, analytics, advertising or tracking SDKs.

## App Privacy (nutrition label)

Tracking: **No** (no data is used to track users across apps or websites; no
ATT prompt needed).

| Data type | Collected | Linked to user | Purpose |
| --- | --- | --- | --- |
| Contact Info → Email address | Yes (only if the person creates an account; not for guests) | Yes | App Functionality (account) |
| Identifiers → User ID | Yes | Yes | App Functionality |
| User Content → Other user content (feeds followed, folders, filters, saved/read state) | Yes | Yes | App Functionality |
| Usage Data → Product interaction (time and share read, open/share/skip) | Yes | Yes | App Functionality, Product Personalization (Trending, recommendations; aggregated) |

Not collected: location, contacts, health, financial info, browsing history
outside the app, diagnostics, advertising data.

## Reply to App Review (5.1.1(v), 2026-10-17)

> Hello, thank you for the review. We have changed the app so that nobody has
> to register to use it. The first screen now offers "Continue without an
> account", which opens the app straight away with a few starter feeds and
> without asking for any personal information. Guests can read, add feeds,
> organise folders, save articles and listen with the device voice. Registering
> is optional and only needed for the account-based features (syncing across
> devices, AI summaries, translation, the server voice and Post radio); a
> guest who registers keeps their feeds and saved articles. Account deletion
> remains available in Settings. The changes are in version 1.1.

## What's new in 1.1

Español: Ahora puedes usar uFeed sin crear una cuenta ("Continuar sin cuenta").
Diseño nuevo para iPad, Mac e iPhone plegable: en horizontal, la lista a la
izquierda y el artículo a la derecha. Botón de recargar en la barra superior,
reintentos automáticos si el servidor no responde, tamaños de letra más
pequeños y varias mejoras de memoria y estabilidad.

English: You can now use uFeed without creating an account ("Continue without
an account"). New layout for iPad, Mac and foldable iPhone: in landscape, the
list on the left and the article on the right. Refresh button in the top bar,
automatic retries when the server doesn't answer, smaller text sizes, and
memory and stability improvements.

## Age rating

The app shows content from feeds the user adds (any website), and links open
the publisher's page. Answer the questionnaire with "Unrestricted Web
Access: Yes" — the resulting rating is the conservative, safe choice for a
news/RSS reader.

## Export compliance

Uses only standard HTTPS provided by iOS → exempt.
`ITSAppUsesNonExemptEncryption = NO` is already set in Info.plist.

## Screenshots needed

**1.1 adds iPad:** App Store Connect will ask for iPad 13" screenshots
(2064 × 2752); the list + article two-pane in landscape is the one to show.

iPhone 6.3" (1206 × 2622), which is what App Store Connect asks for now, in
`App/store/capturas_iphone_6.3/` (es and en), made by `App/store/generar_capturas.py`
from raw simulator captures (demo account) in `App/store/crudo/<lang>/`.
Order: 1 list · 2 full article · 3 listening · 4 Post radio · 5 translation +
AI summary · 6 dark mode. 1320 × 2868 copies are in `capturas_iphone_6.9/`.
Also: header image 21:9 (`App/store/cabecera_3840x1646_<lang>.png`) and
search result image 3:2 (`App/store/busqueda_3840x2560_<lang>.png`), by
`App/store/generar_imagenes.py`. No alpha channel (Apple requirement).

## Steps to publish

1. **Build and upload** (with an explicit OK each time). Raise the build number
   on every upload:
   `flutter build ipa --release --build-name=1.0.0 --build-number=N`, then
   `xcodebuild -exportArchive -archivePath build/ios/archive/Runner.xcarchive
   -exportOptionsPlist <ExportOptions with destination=upload> -allowProvisioningUpdates`
   (uses the Apple account signed in to Xcode). Build 1 uploaded 2026-10-13;
   build 2 (the one for review) uploaded 2026-10-14.
   After building for the store, run `flutter clean` before using the
   simulator again (the device build of `objective_c.framework` leaks into
   the simulator build otherwise).
2. **TestFlight → Internal testing:** add your Apple ID; install from the
   TestFlight app on the iPhone. The "Missing Compliance" question is already
   answered by `ITSAppUsesNonExemptEncryption = NO`.
3. **Version 1.0 page:** texts above (es + en), screenshots 6.3", header and
   search images, URLs, categories, age rating, privacy answers, review
   information (demo password typed by you), then pick the build.
4. **Submit for review:** only with an explicit OK.
