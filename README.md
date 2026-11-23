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

Cátodo se prepara por la noche y se publica solo a las 6:00 (hora de Madrid):

1. **23:00 (domingo a jueves), automático:** el Mac ejecuta `make noche` (noticias, guion en cinco pasadas, voz y montaje del episodio de mañana) y avisa con una notificación. Se instala una vez con `make instalar-noche`.
2. **Tú, por la noche:** revisa `episodes/AAAA-MM-DD/revision.md`, corrige `guion.md` si hace falta y:

   ```bash
   make aprobar NOTA="datos dudosos comprobados"   # deja constancia de la revisión humana
   make programar   # rehace solo los bloques de voz que cambien, sube el audio a R2 y lo programa
   ```

3. **6:00, automático:** GitHub (`.github/workflows/publicar.yml`) publica el episodio programado y actualiza la web y el feed. El Mac puede estar apagado.

Después de las 15:00, `make` trabaja por defecto con el episodio del día siguiente. Para publicar en el momento, sin esperar a las 6:00: `make publicar`.

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

`make preparar` necesita la sesión de `claude` iniciada (`claude` y luego `/login`).

## Estructura

- `config/`: fuentes, ajustes, persona del presentador y pronunciación.
- `src/`: código de cada paso.
- `episodes/AAAA-MM-DD/`: noticias, guion, notas y audio de cada episodio.
- `docs/`: web y `feed.xml` publicados en GitHub Pages.
- `pruebas/`: herramienta de prueba a ciegas de voces.

`.env` nunca se sube al repositorio.
