# Cátodo

Podcast diario de noticias de tecnología en español, de lunes a viernes. El guion y la voz se generan con IA y una persona los revisa antes de publicar.

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

Cátodo se prepara por la noche en [ops](https://ops.wmail.es), el centro de mando, y se publica solo a las 6:00 (hora de Madrid). El Mac no hace falta (`centenardebolitas/ops#118`):

1. **23:00 (domingo a jueves), automático:** ops ejecuta el trabajo `catodo.preparar` (`scripts/ops/preparar.sh`): noticias, guion en cinco pasadas, voz y montaje del episodio de mañana. Sube el audio a una ruta de R2 no enlazada y te avisa en el móvil con una decisión: resumen, puntos a comprobar, orden del episodio y enlaces para escucharlo y leer el guion.
2. **Tú, desde el móvil:** revisas y eliges:
   - **Aprobar y programar**: deja constancia de tu revisión en la memoria del episodio, sube el MP3 definitivo a R2 y regenera el feed y la web (`scripts/ops/responder.sh`). ops empuja el commit a la rama `programado`.
   - **No publicar** (la opción por defecto): no cambia nada.
   - **Un comentario** en texto libre («en la noticia 1 añade "presuntamente" y quita el chiste de Bessent»): Claude lo aplica al guion respetando `config/persona.md`, vuelve a verificar si cambian datos, rehace solo los bloques de voz que cambian y te pasa la versión nueva con las mismas opciones (`src/comentarios.py`). Puede haber varias rondas, y cada comentario queda apuntado en `revision.md`. Un comentario nunca publica: solo «Aprobar y programar».
3. **6:00, automático:** GitHub (`.github/workflows/publicar.yml`) pasa `programado` a `main` y actualiza la web y el feed. ops lo vigila (`catodo.publicar`) y avisa si a esa hora no se publica.

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
