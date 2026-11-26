# Cátodo: podcast diario de tecnología en español generado con IA

Documento de arranque del proyecto. Contiene el concepto, las decisiones ya tomadas, la arquitectura y el plan por fases. Léelo entero antes de empezar.

## Instrucciones para Claude Code

- Trabaja fase a fase, en el orden indicado. Al terminar cada fase, resume lo hecho, indica cómo probarlo y espera mi confirmación antes de pasar a la siguiente.
- No crees cuentas ni contrates servicios: las cuentas las creo yo y te paso las credenciales por `.env`. Los pasos en paneles web (Cloudflare, registrador, GitHub) los hago yo siguiendo tus instrucciones.
- Nunca subas `.env` ni claves al repositorio. Crea `.env.example` con las variables vacías.
- Código en Python 3, sencillo y legible, sin frameworks innecesarios. Comentarios y textos de interfaz en español.
- Todo configurable desde ficheros (`config/`), nada de valores fijos en el código: fuentes, voz, modelo, duración objetivo.
- Si una decisión no está en este documento, pregúntame antes de tomarla.

## Identidad (decidido)

- **Nombre del podcast:** Cátodo. En títulos, guiones y textos siempre con tilde; sin tilde solo en slugs, URLs y handles.
- **Subtítulo propuesto (pendiente de confirmar):** "Cátodo: tecnología cada mañana".
- **Nombre interno del proyecto y repositorio:** `catodo`.
- **Dominio:** `catodo.es` (ya comprado, pendiente de configurar en Cloudflare).
- **Handles en redes:** `catodo.es` en todas (Instagram, Threads, YouTube; en Bluesky, el propio dominio), decidido el 25 de noviembre de 2026: `catodo` está ocupado en Instagram y en Bluesky.

## Concepto

- Podcast diario de noticias de tecnología en español, de lunes a viernes.
- Inspirado en Mixxio (sin episodios desde octubre de 2025), pero con un presentador propio, no una imitación.
- Público, pero es sobre todo un experimento técnico. Sin monetización.
- Duración: 10 a 15 minutos por episodio (unas 1.500 a 2.000 palabras de guion).
- Se prepara por la noche: el script recoge las noticias del día, genera el guion, yo lo reviso y apruebo, y se publica para que esté disponible a primera hora.
- Hueco detectado: en español el único diario generalista de 10 a 15 min activo es Loop Infinito (Xataka). No hay ninguno hecho con IA ni con presentador ficticio.

## El presentador: Cátodo

- Voz masculina, simpática, cálida y cercana. Español de España.
- Actitud positiva ante la tecnología, con un punto de escepticismo: se ilusiona con los anuncios, pero siempre se pregunta quién paga, quién lo controla y si de verdad funciona.
- Algo de opinión y humor, sin pasarse. Humor con un punto geek (referencias a informática, ciencia y cultura friki), nunca forzado. Nada de tono de locutor de telediario.
- Humilde: reconoce que puede equivocarse. De vez en cuando, cuando algo no está del todo claro, lo dice ("si me equivoco, corregidme") y agradece las correcciones.
- Tiene memoria: recuerda lo que contó en episodios anteriores y lo usa cuando ayuda, como lo haría una persona: a veces dentro de la frase ("lo de Nvidia que te contaba ayer ha dado otro paso") y a veces con una pregunta cercana ("¿Te acuerdas de lo de Jensen Huang?"). Que varíe, para que no suene a coletilla.
- El nombre viene del electrodo por el que salen los electrones: es el que emite.

## Estructura del episodio

1. Sintonía corta.
2. Saludo de Cátodo y un gancho de unos 10 segundos sobre la noticia más fuerte del día. Firma fija (decidida el 25 de noviembre de 2026 tras escuchar seis candidatas con la voz real; «escéptica» no sonaba bien): "Buenos días, soy Cátodo, una inteligencia artificial que sigue la tecnología muy de cerca." (el aviso de IA al principio es obligatorio, ver "Aspectos legales"). Después, un enlace breve al gancho que cambia cada día ("Hoy te traigo…", "Empezamos por…"); la voz se genera cada día, también la firma, para que suene natural. Reglas en `config/persona.md`. Sin decir la fecha del día: el episodio puede salir tarde, saltarse un día o escucharse más adelante.
3. Cinco o seis noticias. La más importante primero, con unos 2 minutos; el resto, más breves. El reparto es flexible según el día (ver "Continuidad entre episodios"): seguimientos de días anteriores, noticias que no cupieron ayer, y en días flojos, más profundidad o contexto de alguna noticia.
4. Transiciones habladas por el presentador. Sin cortinilla musical entre noticias.
5. Cierre (decidido el 24 de noviembre de 2026, con el mismo panel que la apertura): una recomendación o un dato curioso; un paso breve que cambia cada día ("Y con esto termino.", "Hasta aquí lo de hoy."); la parte fija, palabra por palabra: "El guion y la voz los hace una inteligencia artificial, y los revisan personas. Si me equivoco, envíame tus comentarios y lo corrijo en el próximo episodio: tienes el contacto en las notas." (sin nombrar a quienes revisan; el correo no se dice en voz alta, va en las notas), y la despedida según el día: "Hasta mañana." de lunes a jueves y "Buen fin de semana." el viernes (`comun.persona()` se lo dice al guion). La memoria lleva los enlaces y pasos de los últimos episodios para que no se repitan.
6. Sintonía de salida.

## Reglas de contenido

- Las noticias se cuentan con palabras propias. Nunca se leen ni se copian artículos.
- Estructura propia: no se sigue el orden ni la estructura de ningún artículo concreto. No se citan literalmente frases de periodistas; solo declaraciones públicas breves y atribuidas. De las fuentes en inglés se extraen los hechos, no se traducen frase a frase.
- Personas reales: situación judicial exacta, "presuntamente" cuando toque, ningún hecho negativo sobre una persona que no esté en al menos dos fuentes y nada de humor sobre particulares.
- Las fuentes se citan siempre: atribuir y enlazar es la mejor defensa legal y la buena práctica periodística. Ocultarlas no reduce el riesgo, lo aumenta.
- Las fuentes se enlazan en las notas del episodio.
- Nunca se trata una noticia que solo publique una fuente o un solo grupo editorial. Tiene que estar cubierta por al menos dos grupos independientes, para que nadie pueda decir que usamos su exclusiva como si fuera nuestra. Cada fuente tiene su grupo identificado en `sources.yaml`. Los agregadores (Techmeme, Hacker News) sirven para descubrir noticias, pero no cuentan como cobertura: cuentan los medios originales a los que enlazan.
- No inventar datos, cifras ni declaraciones. Si algo no está claro en las fuentes, se dice o se omite.
- Fechas y cifras con moderación: lo que interesa es qué ha pasado y por qué importa, no el día exacto en que entró en vigor una norma. Solo se dan fechas o cifras exactas cuando son el centro de la noticia (por ejemplo, algo que cambia un día concreto). El resto se redondea ("hace un par de años", "casi el doble") o se omite.
- Se pueden usar fuentes en inglés: se traducen y se contextualizan para un oyente hispanohablante.
- Transparencia sobre IA: la descripción del podcast y las notas de cada episodio indican que guion y voz se generan con IA con revisión humana. En el audio no se nombra a quienes revisan: se dice "personas". La revisión nocturna tiene que ser real.

## Continuidad entre episodios (decidido)

Es la clave del proyecto: Cátodo no empieza de cero cada día.

- **Memoria:** al publicar cada episodio se guarda qué noticias se contaron, con un resumen breve y los asuntos abiertos ("Huang declarará ante el Senado la semana que viene"). Al preparar el siguiente, el editor recibe la memoria de los últimos días.
- **Pendientes:** las buenas noticias que no caben en un episodio quedan pendientes y se pueden contar al día siguiente si siguen siendo relevantes.
- **Anuncios (decidido el 25 de noviembre de 2026):** de vez en cuando, si una pendiente es de verdad importante, el cierre la deja para el próximo episodio ("mañana lo vemos con calma"). Como mucho una por episodio y la mayoría de días ninguna; la memoria la marca como anunciada y el editor del día siguiente está obligado a contarla (o a explicar por qué no).
- **Índice de temas (decidido el 25 de noviembre de 2026):** cada noticia contada guarda de tres a seis temas concretos (empresas, personas, productos, casos). Al preparar un episodio, las noticias de hace más de una semana que comparten tema con las de hoy llegan al editor, a la redacción y a la crítica como antecedentes, para enlazarlas solo cuando la de hoy depende de ellas o las completa. Debe ser sutil: lo normal es no usarlas.
- **Seguimiento:** si una historia de días anteriores avanza, se cuenta como continuación y se enlaza con lo ya dicho.
- **Días flojos:** si hay pocas noticias, se profundiza en alguna, se cuenta el contexto o la historia detrás de una noticia, o se hace seguimiento de anteriores. No se rellena con noticias menores.

## Fuentes iniciales

Verificar que cada URL de feed funciona antes de darla por buena.

La lista completa está en `config/sources.yaml`: 38 fuentes (23 de noviembre de 2026), todas con el feed comprobado y su grupo editorial.

- **En inglés:** Ars Technica, The Verge, TechCrunch, Engadget, The Register, BBC, Tom's Hardware, 9to5Mac, Gizmodo, CNBC, Bloomberg, NYT, Washington Post, MIT Technology Review, 404 Media, ZDNet, The Next Web, MacRumors, Android Authority y Android Police.
- **En español:** Xataka, Genbeta, Hipertextual, El Confidencial, MuyComputer, Computer Hoy, El Español Omicrono, El País, Business Insider España, Andro4all, Microsiervos, Wwwhat's new y FayerWayer.
- **Agregadores** (descubren noticias, no cuentan como cobertura): Techmeme, Hacker News, Slashdot y Google News Tecnología (España y EE. UU.).

Varias fuentes del mismo grupo cuentan como una sola cobertura (por ejemplo, Xataka y Genbeta son de Webedia). Los grupos marcados «por confirmar» hay que verificarlos.

## Aspectos legales (decidido el 23 de noviembre de 2026)

Basado en un análisis informativo hecho con IA (`investigacion/analisis-legal.md`, fuera del repositorio). No es asesoramiento jurídico.

- **Repositorio público:** nunca se suben los artículos ni los titulares de los medios (`articulos.json`, `news.json`, `pasadas/`, `escaleta.json`, `revision.md`). Solo se publican guion, notas y memoria.
- **Lectura por IA:** se respetan las reservas de los medios. Las fuentes con `leer_con_ia: false` en `sources.yaml`, y los dominios cuyo robots.txt o TDMRep lo reservan (`src/reservas.py`), cuentan para la regla de dos grupos y se enlazan, pero Claude no abre sus artículos.
- **Aviso de IA (Reglamento de IA, art. 50, y normas de Apple Podcasts):** al principio y al final del audio, en las notas de cada episodio, en la `<description>` de cada episodio del feed y en la descripción del programa.
- **Notas:** el texto de cada enlace es el nombre del medio, nunca su titular copiado. Nunca se enlazan copias que saltan muros de pago.
- **Revisión humana documentada:** hasta el 25 de noviembre de 2026, `make aprobar` dejaba constancia en el episodio y no se publicaba sin aprobación. Desde el 26, por decisión del editor (de momento no hay más oyentes que él), cada episodio se publica solo a las 5:00 tras las comprobaciones automáticas y lo revisan personas después, al escucharlo; la memoria lo deja como «publicación automática» y la descripción, las notas, Sobre y el aviso legal lo cuentan así.
- **Correcciones:** `make corregir` las añade a las notas del episodio afectado y el siguiente episodio las menciona.
- **Web:** página `docs/legal.html` con responsable editorial ("el editor de Cátodo"), contacto, privacidad y uso de IA. Sin cookies ni analítica.

## Arquitectura

```
[Feeds RSS] -> fetch -> rank -> news.json
news.json + persona -> claude -p -> guion.md
            (revisión y aprobación manual)
guion.md -> Gemini TTS (por bloques) -> ffmpeg (unión, sintonía, normalizado) -> episodio.mp3
episodio.mp3 -> Cloudflare R2 (audio.catodo.es)
feed.xml + web -> GitHub Pages (catodo.es)
feed.xml -> Apple Podcasts / Spotify
```

### Dominios

| Uso | Dirección | Servicio |
|---|---|---|
| Web y feed RSS | `https://catodo.es` (feed en `https://catodo.es/feed.xml`) | GitHub Pages |
| Audio de episodios | `https://audio.catodo.es` | Bucket público de Cloudflare R2 |

El DNS de `catodo.es` se gestiona en Cloudflare (ver Fase 0).

### Piezas y servicios

| Pieza | Herramienta |
|---|---|
| Lenguaje | Python 3 (`feedparser`, `requests`, `boto3`, `pyyaml`) |
| Guion | Claude Code en modo no interactivo (`claude -p`) con mi plan Max |
| Voz | Gemini TTS por la Agent Platform de Google Cloud (región eu, credenciales de gcloud), pago por uso; la API de AI Studio queda como alternativa. Modelo `gemini-3.8-flash-tts`, voz `es-es-csagent-3` (Call Center Agent 3, castellano, 32 años) e instrucción de estilo en `config/` |
| Pronunciación | Gemini no tiene diccionario de pronunciación: se usa un diccionario propio de sustituciones que se aplica al texto antes de sintetizar (siglas, marcas, nombres en inglés) |
| Montaje de audio | `ffmpeg` |
| Alojamiento de audio | Cloudflare R2 con dominio `audio.catodo.es` |
| Feed RSS y web | GitHub Pages (carpeta `docs/`) con dominio `catodo.es` |
| DNS | Cloudflare |
| Ejecución | Mi ordenador, lanzado a mano por la noche |

### Estructura de repositorio propuesta

```
catodo/
  config/
    sources.yaml        # feeds, idioma, peso de cada fuente
    settings.yaml       # duración objetivo, nº de noticias, modelo y voz TTS, estilo, bitrate
    persona.md          # prompt del personaje y de la estructura del episodio
    pronunciacion.yaml  # sustituciones de texto antes de sintetizar
  src/
    fetch.py            # descarga feeds, filtra últimas 24 h
    rank.py             # agrupa duplicados y ordena por relevancia
    script.py           # genera el guion llamando a claude -p
    tts.py              # envía bloques a Gemini TTS
    mix.py              # une audio, añade sintonía, normaliza
    publish.py          # sube a R2, regenera feed, commit a Pages
    feed.py             # construcción del RSS de podcast
  assets/
    sintonia_intro.mp3
    sintonia_outro.mp3
    portada.jpg         # 3000x3000 px
  episodes/
    AAAA-MM-DD/
      news.json
      guion.md
      notas.md          # notas del episodio con enlaces a fuentes
      bloques/          # audios parciales
      catodo-AAAA-MM-DD.mp3
  docs/                 # GitHub Pages: CNAME, feed.xml, index.html, portada
  .env.example
  Makefile
  README.md
```

### Flujo de uso diario

```
make preparar    # fetch + rank + guion -> episodes/AAAA-MM-DD/guion.md
                 # (reviso y edito guion.md)
make publicar    # tts + mix + subida a R2 + feed + commit y push
```

### Variables de entorno (`.env`)

```
GEMINI_API_KEY=
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=catodo-audio
R2_PUBLIC_BASE_URL=https://audio.catodo.es
SITE_URL=https://catodo.es
```

## Plan por fases

### Fase 0. Dominio, infraestructura y esqueleto

Guíame paso a paso en lo que tenga que hacer yo en los paneles web, y haz tú la parte de código.

**0.1 Dominio en Cloudflare (lo hago yo con tu guía)**
- Añadir `catodo.es` como sitio en Cloudflare (plan Free).
- Cambiar los servidores DNS en el registrador donde compré `catodo.es` por los dos que indique Cloudflare.
- Esperar a que Cloudflare marque el dominio como activo y comprobarlo (por ejemplo con `dig NS catodo.es`).

**0.2 Bucket de audio en R2 (lo hago yo con tu guía)**
- Activar R2 en la cuenta de Cloudflare.
- Crear el bucket `catodo-audio`.
- Conectarle el dominio personalizado `audio.catodo.es` (no usar la URL `r2.dev`, que es solo para pruebas).
- Crear un token de API de R2 con permiso de lectura y escritura solo sobre ese bucket y pasar las claves al `.env`.

**0.3 Repositorio y GitHub Pages**
- Crear la estructura del repositorio `catodo`, `README.md`, `.env.example`, `.gitignore`, `Makefile` y ficheros de configuración de ejemplo.
- Configurar GitHub Pages desde la carpeta `docs/` con un fichero `CNAME` que contenga `catodo.es`.
- Darme los registros DNS que debo crear en Cloudflare para GitHub Pages (registros A/AAAA del dominio raíz y CNAME de `www`), en modo "solo DNS" (nube gris) para que GitHub pueda emitir el certificado HTTPS.
- Activar "Enforce HTTPS" en GitHub Pages cuando el certificado esté listo.

**Hecho cuando:** `https://catodo.es` muestra una página de prueba con HTTPS, un fichero de prueba subido a R2 se descarga desde `https://audio.catodo.es`, y `make` muestra los comandos disponibles.

**Estado (23 de noviembre de 2026):**
- 0.1 hecho: DNS de `catodo.es` en Cloudflare (servidores `sara` y `zod`), con los registros de correo de OVH y los de GitHub Pages en modo «solo DNS». Propagándose.
- 0.2 hecho: R2 activado, bucket `catodo-audio` en Europa Occidental, dominio `audio.catodo.es` (TLS mínimo 1.2) y token de cuenta `catodo-publicar`, con lectura y escritura de objetos solo en ese bucket, guardado en `.env`. Probado: subida por la API y descarga pública por `https://audio.catodo.es`.
- 0.3 hecho: repositorio `centenardebolitas/catodo` con GitHub Pages desde `docs/` y HTTPS obligatorio (comprobado el 25 de noviembre de 2026).

### Fase 1. Recogida y selección de noticias
- `fetch.py`: lee los feeds de `sources.yaml` y se queda con lo publicado en las últimas 24 h.
- `rank.py`: agrupa la misma noticia publicada en varias fuentes; cuantos más grupos editoriales independientes la cubren, más sube. Descarta las noticias cubiertas por un solo grupo (los agregadores no cuentan). Devuelve las mejores candidatas en `news.json` (titular, resumen, enlaces, fuentes, fecha).
- Agrupación con Claude (decidido): la agrupación estadística por palabras se queda corta con cientos de artículos, así que la hace Claude (`claude -p`, modelo configurable). Claude junta los artículos que cuentan la misma historia, aunque estén en distintos idiomas, y marca lo que no es noticia (ofertas, reseñas, guías). La regla de dos grupos y la puntuación las aplica el código, no Claude.
- Hecho cuando: `make noticias` genera un `news.json` razonable con las noticias del día.

### Fase 2. Guion
- `persona.md`: prompt con el personaje, la estructura, las reglas de contenido y la longitud objetivo.
- El guion es lo más importante del proyecto. Se hace con un buen modelo (Claude Opus con la suscripción del editor por ahora) y en varias pasadas, cada una con `claude -p`:
  1. **Editor:** con `news.json` y la memoria de días anteriores, decide la escaleta: qué noticias, en qué orden, con qué ángulo y duración, qué es seguimiento, qué queda pendiente y, en días flojos, en qué se profundiza.
  2. **Redacción:** lee los artículos originales (al menos dos grupos por noticia) y escribe el guion con la voz de Cátodo, con palabras propias.
  3. **Verificación:** otra pasada contrasta cada dato, cifra y declaración con las fuentes y señala lo dudoso.
  4. **Abogado del diablo:** otra pasada rebate el guion: equilibrio, quién paga y quién controla, contexto que falta, exceso de fechas o cifras, humor, ritmo y duración.
  5. **Versión final:** aplica las correcciones y deja `guion.md`, `notas.md` y un informe de revisión con lo cambiado y las dudas para el editor.
- `script.py` orquesta esas pasadas. Deja en la carpeta del episodio `escaleta.json`, `guion.md`, `notas.md`, `revision.md`, `memoria.json` y la respuesta de cada pasada en `pasadas/`. Con `--desde N` se repite a partir de una pasada.
- Memoria: `memoria.json` de cada episodio guarda lo contado, los asuntos abiertos y las pendientes. Solo entra en la memoria de días siguientes cuando el episodio está marcado como publicado (`make marcar-publicado` hasta que la Fase 4 lo haga sola).
- Formato del guion: Markdown dividido en bloques (`## Apertura`, `## Noticia 1`, ..., `## Cierre`) para poder sintetizar por bloques. Genera también `notas.md` con los enlaces y el aviso de IA. Formato de `notas.md`: una línea `# ` con el título del episodio; por noticia, una línea `## ` con su título, una frase de resumen y, en una línea aparte, las fuentes todas seguidas y separadas por ` · ` (`[Bloomberg](url) · [Xataka](url)`), con solo el nombre del medio como texto del enlace y nunca en lista; al final, `---` y el aviso de IA. Lo pide el prompt de la pasada final y, por si el modelo no hace caso, `comun.enlaces_en_linea` junta en una línea las listas de enlaces al escribir las notas (`script.py`), al aplicar un comentario de ops y al publicar (`publish.py`).
- Comprobar la longitud (palabras y caracteres) y avisar si se sale del rango.
- Hecho cuando: `make preparar` deja un guion listo para revisar.

### Fase 3. Audio
- `tts.py`: aplica el diccionario de sustituciones y sintetiza cada bloque con la voz, el modelo y la instrucción de estilo configurados, con reintentos ante errores. Cada petición genera como máximo unos 10 minutos de audio, así que los bloques deben ser más cortos.
- `mix.py`: une bloques con `ffmpeg`, añade sintonía de entrada y salida, normaliza a -16 LUFS y exporta MP3 mono a 96 kbps.
- Mostrar al final la duración del episodio y su coste aproximado (tokens de audio: 25 por segundo).
- Hecho cuando: obtengo un MP3 escuchable del guion aprobado.
- Estado (23 de noviembre de 2026): `tts.py` y `mix.py` escritos (`make voz`, `make audio`). La voz se genera por la Agent Platform de Google Cloud (antes Vertex AI), región `eu`, con las credenciales de `gcloud` (`gcloud auth application-default login`, una vez): la API de AI Studio aplicaba la cuota gratuita de 10 peticiones al día aunque el proyecto estuviera en el nivel de pago. La vía de AI Studio sigue disponible (`tts.via: gemini_api`). Primer episodio completo generado: 10 minutos para 1.935 palabras (la voz lee a unas 190 palabras por minuto). Desde el 24 de noviembre, con sintonía de entrada y salida, el «bzz» entre noticias y capítulos.

### Fase 4. Publicación
- `publish.py`: sube el MP3 a R2 y obtiene la URL pública en `audio.catodo.es`.
- `feed.py`: regenera `docs/feed.xml` como RSS de podcast válido (etiquetas `itunes:*`, `enclosure` con tamaño en bytes, `guid`, `pubDate`, notas del episodio con enlaces) y una `index.html` sencilla con la lista de episodios.
- Commit y push automáticos del feed.
- La `<description>` de cada episodio incluye el aviso de IA (lo exige Apple Podcasts).
- Solo publica episodios aprobados (`make aprobar`) y los marca como publicados para la memoria.
- Hecho cuando: el feed pasa un validador de podcasts y el episodio se reproduce desde `https://audio.catodo.es`.
- Estado (23 de noviembre de 2026): `publish.py` y `feed.py` escritos (`make publicar`, `make simulacro`, `make feed`); los datos del programa están en `config/podcast.yaml`. Desde el 24 de noviembre publica de verdad; desde el 26, solo y desde ops (ver «Revisión humana documentada»).

### Fase 5. Distribución (la hago yo, con tu guía)
- Alta del feed `https://catodo.es/feed.xml` en Apple Podcasts Connect y en Spotify (feed externo).
- Requisitos: portada 3000x3000 px, título, descripción (con el aviso de IA), categoría Tecnología, idioma español.
- Estado (24 de noviembre de 2026):
  - **Apple Podcasts:** dado de alta con un Apple ID propio de Cátodo (hola@catodo.es). Estado «Disponible», ID 6838674796: https://podcasts.apple.com/us/podcast/cátodo/id6838674796. Declarado «sin contenido de terceros», frecuencia diaria, todos los países.
  - **Spotify:** dado de alta en Spotify for Creators (feed externo, verificado con código a hola@catodo.es). País España, idioma español, categoría Business & Technology › Technology (no se puede cambiar). Enlace: https://open.spotify.com/show/0yoPeeD7SrWdvm9FAcuWf4 (tarda unas horas en aparecer).
  - Enlaces en la web (portada y pie), configurables en `config/podcast.yaml` (`escuchar`).
  - **iVoox (aparcado):** cuenta creada con hola@catodo.es, pero al importar el feed su filtro automático lo rechaza (HTTP 451, «Spam detected when creating or editing program or audio») sin decir por qué. Decidido dejarlo de momento; se puede reintentar con más episodios o escribiendo a su soporte.

### Fase 6. Piloto
- Dos semanas publicando sin difundir. Ajustar prompt, voz, modelo y duración.
- En marcha desde el episodio 1 (24 de noviembre de 2026); termina hacia el 8 de diciembre. Hasta ahora: apertura y cierre nuevos, publicación automática a las 5:00 desde ops, ritmo de voz más pausado, anuncios del próximo episodio e índice de temas.

## Presupuesto estimado (sin contar la IA de desarrollo)

| Concepto | Coste |
|---|---|
| Gemini TTS (pago por uso) | Unos 3,5 $/mes hasta el 31 de diciembre de 2026; unos 7 $/mes desde enero de 2027 (Google dobla el precio) |
| Dominio `catodo.es` | Ya comprado |
| Cloudflare (DNS y R2) | 0 € (capa gratuita de R2 de 10 GB; un año de episodios ocupa unos 2,3 GB) |
| GitHub y GitHub Pages | 0 € |
| Guion con Claude | 0 € extra (plan Max) |
| Apple Podcasts y Spotify | 0 € |
| **Total** | **unos 4 a 7 $/mes** |

Nota sobre el coste: Gemini cobra por audio generado (25 tokens por segundo). 22 episodios de 12 min son unos 400.000 tokens de audio al mes: 9 $ por millón hasta fin de 2026 y 18 $ por millón después, más el texto de entrada, que es despreciable. El modo por lotes cuesta la mitad.

Facturación real (25 de noviembre de 2026): la voz va por Google Cloud, que es pospago (se carga en la tarjeta a principios del mes siguiente). Mientras dure el crédito de bienvenida de Google Cloud (269,43 €, quedan 268,02 €, caduca el 22 de febrero de 2027) el gasto lo cubre el crédito. Presupuesto «Cátodo voz 5 €/mes» en la cuenta de facturación: solo alertas por correo al 50, 90 y 100 % (2,5, 4,5 y 5 €), sobre el gasto bruto, sin descontar créditos, para que avise aunque el crédito lo esté pagando. El prepago de 5 € de AI Studio solo lo usa la vía de respaldo `gemini_api`.

## Voz (decidido el 23 de noviembre de 2026)

- Proveedor: Gemini TTS, por precio. Modelo `gemini-3.8-flash-tts`, voz `es-es-csagent-3` (Call Center Agent 3: castellano, 32 años, "engaging and empathic").
- Se eligió en dos pruebas a ciegas (`pruebas/`). En la primera, la voz favorita fue ElevenLabs "David Martin - Confident and Friendly" (Eleven v4), pero Gemini sale unas tres veces más barato. En la segunda se probaron las voces nativas de España del catálogo ampliado de Gemini (`es-es-*`).
- Producción en la capa de pago: la gratuita solo permite 10 peticiones al día y Google usa esos datos para mejorar sus productos.
- Configurado: proyecto `catodo` en Google AI Studio (Nivel 1, con facturación), clave `catodo-produccion-3` en `.env` (solo para la vía de respaldo `gemini_api`; rotada el 25 de noviembre de 2026, igual que el token de R2, ahora `catodo-publicar-2`) y límite de gasto de la API de Gemini de 10 €/mes (función experimental de AI Studio; puede pasarse unos minutos antes de cortar). El crédito de bienvenida de Google Cloud no sirve para pagar la API de Gemini.

## Ritmo (25 de noviembre de 2026)

- Los dos primeros episodios se hacen algo acelerados para la cantidad de contenido (unos 10,5 minutos para casi 2000 palabras). Se quiere el mismo contenido en unos 12 minutos.
- Se probaron cuatro muestras: la actual, ralentizada un 10 %, con estilo de voz pausado y las dos cosas a la vez. Las ralentizadas no gustaron. Desde el 26 de noviembre, el estilo de voz en `settings.yaml` pide un ritmo pausado, con pausas breves entre frases (la muestra 3: un 7 % más largo, sutil).
- `audio.tempo_voz` (ralentizar la voz al mezclar, con los capítulos ajustados) queda en 1.0, sin uso.

## Redes (decidido el 25 de noviembre de 2026)

Solo redes en las que se pueda publicar de forma automática. Sin X: su API ya no tiene plan gratuito (unos 0,20 $ por publicación con enlace). TikTok y LinkedIn, aparcados: TikTok solo deja publicar en cuentas privadas hasta pasar una auditoría, y LinkedIn no da a proyectos pequeños el permiso para publicar en una página.

- **Qué se publica cada día** (`src/redes.py`, con los vídeos de `src/difusion.py`):
  - Bluesky: el titular del episodio, los titulares que quepan y una tarjeta con el enlace a la página del episodio.
  - Instagram (Reel), Facebook (vídeo de la página) y Threads: un clip vertical de 45-60 s con la primera noticia, con la portada del episodio, el título de la noticia, la forma de onda y subtítulos. Los subtítulos son el texto del guion: cada frase se coloca en proporción a su longitud y se lleva al silencio más cercano del audio.
  - YouTube: el episodio entero en vídeo, con la portada y el título de cada capítulo (y los capítulos en la descripción), y el clip como Short. Se declara como contenido sintético.
  - En todos los textos, «Guion y voz generados con IA y revisados por personas».
- **Cuándo:** al elegir «Difundir en redes» en el aviso del episodio publicado (la respuesta de `catodo.preparar`, `src/ops.py responder`). «No difundir», la opción por defecto, no publica nada. Antes de publicar espera hasta 15 minutos a que la página del episodio y el audio estén en la web. Desde el 26 de noviembre de 2026; antes era un trabajo aparte, `catodo.difundir`, a las 8:30, que fallaba en cadena si el episodio salía tarde. Ese día también se quitó `catodo.publicar` (la comprobación de las 6:00 en GitHub): Cátodo queda con un solo trabajo en ops.
- **Seguridad ante fallos:** lo publicado se apunta en R2 (`difusion/FECHA.json`) red a red, así que repetir el trabajo no publica dos veces. Si una red falla, las demás salen igual y la respuesta termina con error: ops avisa y la reintenta (4 veces en 2 horas), y solo se repiten las redes que falten.
- **Activación:** `redes.activas` en `config/settings.yaml` (vacío hasta tener las cuentas). `make redes` hace los vídeos y enseña los textos sin publicar nada.
- **Estado:** código y pruebas hechos el 25 de noviembre de 2026. **Bluesky en marcha desde ese mismo día** (`@catodo.es`, con la etiqueta de automatización; contraseña de aplicación `catodo-ops` en `catodo-bluesky-app-password`): primera publicación, la del episodio 2, lanzada a mano. Faltan Meta y YouTube: al tenerlas, sus secretos se añaden a `catodo.preparar` en el manifiesto de ops y la red a `redes.activas`.

Alta de cuentas (las crea Ulises, con hola@catodo.es; los secretos se guardan en ops con `pbpaste | ssh ops 'sudo ops-jobs secret set NOMBRE'`):

1. **Bluesky:** cuenta nueva y, en Ajustes › Cuenta › Identificador, el dominio `catodo.es` (registro TXT `_atproto` en Cloudflare). Una contraseña de aplicación: `catodo-bluesky-app-password`.
2. **Meta:** hechas el 26 de noviembre de 2026:
   - Instagram `catodo.es`, cuenta profesional (empresa).
   - Página de Facebook «Cátodo» (ID de Graph 1473516159180136, `redes.facebook_pagina`), con web, foto y la portada `assets/redes/portada-facebook.jpg`.
   - Threads `@catodo.es`, público.
   - Porfolio empresarial «Cátodo» (ID 4596718177284366, sin verificar), con la página como activo.
   - App de Meta «Cátodo» (ID 1495881029366859) del porfolio, con los casos de uso de Instagram, página y Threads.

   Meta ya no deja a las apps nuevas usar el inicio de sesión de Instagram: Facebook e Instagram van con un **usuario del sistema** del porfolio («Publicador», rol empleado, con la app y la página asignadas; Meta no admite guiones ni el nombre del porfolio en el nombre) y su token, que no caduca: `catodo-meta-token` (META_TOKEN), con `pages_show_list`, `pages_manage_posts`, `pages_read_engagement`, `pages_manage_engagement` y `pages_read_user_content` (estos dos, para el comentario con el enlace al episodio: en los Reels el enlace del texto no se puede pulsar; el usuario necesita además «Actividad de la comunidad» en la página), `instagram_basic` e `instagram_content_publish`. La app está en modo publicado (si no, lo que publica solo lo ven quienes tienen rol en ella), con `catodo.es/legal.html` como política de privacidad.

   Instagram no se deja enlazar con nada de Facebook (la página, el porfolio ni la cuenta personal): Meta da error en la web y en el móvil, típico de cuentas recién creadas. Hay que reintentar añadirla al porfolio en unos días; después se asigna al usuario del sistema y su ID va a `redes.instagram_id`.

   Threads: @catodo.es es evaluador de Threads de la app; su token largo sale del «Generador de identificadores de usuario» (caso de uso Threads › Configuración) y va a `catodo-threads-token` (THREADS_TOKEN; dura 60 días y se renueva solo cada semana).
3. **YouTube:** canal `@catodo.es` con la cuenta de Google de Cátodo. En el proyecto de Google Cloud `catodo`: activar la YouTube Data API v3, pantalla de consentimiento en producción (si se queda en «prueba», el permiso caduca a los 7 días) y un cliente OAuth de escritorio. `python src/redes.py autorizar-youtube` da el refresh token (`catodo-youtube-refresh-token`). Si los vídeos se quedan en privado, hay que pedir la auditoría de la API.

## Decisiones pendientes

- Subtítulo del podcast (propuesta: "tecnología cada mañana").
- Confirmar el grupo editorial de las fuentes marcadas «por confirmar» en `sources.yaml`.
- Comprobar la marca "Cátodo" en la OEPM y en TMview (clases 9, 38 y 41).
- Valorar una consulta con un abogado (anonimato frente a la identificación del responsable en la política de privacidad, límite de cita, lectura por IA). Las preguntas están en `investigacion/analisis-legal.md`.
- Valorar usar una clave de API de Anthropic para el proceso nocturno en lugar del plan Max.
- Licencia de la sintonía: confirmar que las condiciones de Google Cloud cubren su uso en un podcast.
- Enlaces de Spotify por episodio: hoy no se automatizan (Apple sí).
- Sección fija o muletilla del presentador, si la hay.
- Crear las cuentas de redes y activarlas (sección «Redes»).
