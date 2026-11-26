# Cátodo

Podcast diario de noticias de tecnología en español, de lunes a viernes. El guion y la voz se generan con IA, pasan comprobaciones automáticas antes de publicarse y luego los revisan personas al escucharlos.

- Web y feed: https://catodo.es (GitHub Pages, carpeta `docs/`)
- Audio: https://audio.catodo.es (Cloudflare R2)

El plan completo, las decisiones tomadas y las fases están en [catodo-proyecto.md](catodo-proyecto.md).

## Puesta en marcha

```bash
make instalar          # entorno de Python en .venv
cp .env.example .env   # y rellena las claves
make                   # lista los comandos
```

## Uso diario

Cátodo se prepara y se publica solo cada mañana en [ops](https://ops.wmail.es), el centro de mando, sin revisión previa: lo revisan personas después, al escucharlo (decidido el 25 de noviembre de 2026; `centenardebolitas/ops#122`). El Mac no hace falta:

1. **5:00 (lunes a viernes), automático:** ops ejecuta el trabajo `catodo.preparar` (`scripts/ops/preparar.sh`): noticias, guion en cinco pasadas con sus revisores automáticos, voz, montaje y portada del episodio del día (el guion escrito en emojis, `src/portada_episodio.py`; si falla, sale sin ella). Lo deja como publicación automática en su memoria, sube el MP3 a R2, regenera el feed y la web, y ops empuja el commit a `main` (`commandGitPush`). Hacia las 5:30 está en catodo.es, y Apple y Spotify lo recogen en su siguiente pasada.
2. **En el móvil:** un aviso con el enlace, los puntos a comprobar al escucharlo y el orden del episodio. Con redes activas, sus opciones son «Difundir en redes», que lo publica en ellas (`src/redes.py`), y «No difundir»; sin redes, solo «Visto». Es el único trabajo de Cátodo en ops: si el episodio falla, no hay nada más que falle detrás.
3. **Si algo no cuadra al escucharlo:** `make corregir FECHA=… TEXTO="…"` lo añade a las notas del episodio y el siguiente lo menciona.

El flujo anterior (preparar a las 22:00, «Aprobar y programar» desde el móvil y publicar desde la rama `programado`) sigue en el código (`src/ops.py preparar` y `responder`), pero ops ya no lo lanza, y `publicar.yml` ya no corre solo a las 6:00: la rama `programado` se pasa a `main` a mano (Actions › Publicar episodio programado › Run workflow).

Si hay que corregir el guion antes de aprobar, se hace en el Mac, como antes:

```bash
make preparar FECHA=2026-11-25   # el guion, en el Mac
make aprobar NOTA="datos dudosos comprobados"   # deja constancia de la revisión humana
make programar   # rehace solo los bloques de voz que cambien, sube el audio a R2 y lo programa
```

Después de las 15:00, `make` trabaja por defecto con el episodio del día siguiente. Para publicar en el momento, sin esperar a las 6:00: `make publicar`. `make noche` prepara a mano en el Mac lo mismo que ops; `make instalar-noche` lo programaría con `launchd`, pero desde ops#118 no se usa (`make desinstalar-noche` lo quita).

En ops, la configuración del trabajo (calendario, secretos, rama de push) está en `jobs/manifest.json` del repo ops, y cómo funciona, en su `docs/TRABAJOS.md` ("Un comando con IA" y "Un comando que responde"). Las pruebas de esta parte: `.venv/bin/python -m unittest discover -s tests`.

Otros comandos útiles:

```bash
make noticias                # solo descarga y agrupa (news.json)
make guion                   # solo el guion, a partir de news.json
make memoria                 # lo que Cátodo recuerda de días anteriores
make marcar-publicado        # mete el episodio de hoy en la memoria (hasta que exista la Fase 4)
make corregir FECHA=2026-11-23 TEXTO="..."   # registra una corrección de un episodio
make reservas                # qué medios no permiten que una IA lea sus artículos
make portada                 # portada del episodio: el guion en emojis (emojis.txt) en duotono
python src/capitulos.py --fecha AAAA-MM-DD   # capítulos del episodio (los hace mix.py; --incrustar los mete en el MP3)
python src/enlaces.py        # enlace de cada episodio en Apple Podcasts (lo hace publish.py)
make preparar FECHA=2026-11-24
```

`make preparar` en el Mac necesita la sesión de `claude` iniciada (`claude` y luego `/login`). En ops, el token de la suscripción lo pone el centro.

## Estructura

- `config/`: fuentes, ajustes, persona del presentador y pronunciación.
- `src/`: código de cada paso.
- `episodes/AAAA-MM-DD/`: noticias, guion, notas y audio de cada episodio.
- `docs/`: web y `feed.xml` publicados en GitHub Pages.
- `pruebas/`: herramienta de prueba a ciegas de voces.

`.env` nunca se sube al repositorio.
