# Cátodo: comandos del día a día. Ejecuta `make` para ver la ayuda.

PYTHON := .venv/bin/python
# Fecha del episodio: a partir de las 15:00 se trabaja en el de mañana (flujo nocturno).
FECHA  ?= $(shell if [ $$(date +%H) -ge 15 ]; then date -v+1d +%Y-%m-%d; else date +%Y-%m-%d; fi)
PLIST  := $(HOME)/Library/LaunchAgents/es.catodo.noche.plist

.DEFAULT_GOAL := ayuda
.PHONY: ayuda instalar noticias guion preparar memoria aprobar marcar-publicado corregir reservas voz audio portada noche programar instalar-noche desinstalar-noche publicar simulacro feed probar-voces

ayuda: ## Muestra esta ayuda
	@echo "Cátodo: comandos disponibles"
	@echo
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /|/' | awk -F'|' '{printf "  make %-14s %s\n", $$1, $$2}'
	@echo
	@echo "Fecha del episodio: $(FECHA) (cámbiala con FECHA=AAAA-MM-DD)"

instalar: ## Crea el entorno de Python e instala las dependencias
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip -q
	$(PYTHON) -m pip install -r requirements.txt -q
	@echo "Entorno listo en .venv"

noticias: ## Descarga los feeds y elige las noticias candidatas (Fase 1)
	$(PYTHON) src/fetch.py --fecha $(FECHA)
	$(PYTHON) src/rank.py --fecha $(FECHA)

guion: ## Guion en cinco pasadas con Claude a partir de news.json (Fase 2)
	$(PYTHON) src/script.py --fecha $(FECHA)

preparar: noticias guion ## Noticias + guion listo para revisar (Fases 1 y 2)

memoria: ## Muestra lo que Cátodo recuerda de episodios anteriores
	@$(PYTHON) src/memoria.py --fecha $(FECHA)

aprobar: ## Deja constancia de tu revisión humana del guion (NOTA="qué has revisado")
	$(PYTHON) src/memoria.py --aprobar $(FECHA) --nota "$(NOTA)"

marcar-publicado: ## Marca el episodio de FECHA como emitido (entra en la memoria; exige aprobar)
	$(PYTHON) src/memoria.py --publicado $(FECHA)

corregir: ## Registra una corrección del episodio de FECHA (TEXTO="...")
	$(PYTHON) src/memoria.py --correccion $(FECHA) --texto "$(TEXTO)"

reservas: ## Comprueba qué medios no permiten que una IA lea sus artículos
	$(PYTHON) src/reservas.py

voz: ## Sintetiza el guion por bloques con Gemini (solo repite los que cambian)
	$(PYTHON) src/tts.py --fecha $(FECHA)

audio: voz ## Voz + montaje: MP3 final con sintonía y volumen normalizado (Fase 3)
	$(PYTHON) src/mix.py --fecha $(FECHA)

portada: ## Portada del episodio: el guion en emojis (emojis.txt) en duotono
	$(PYTHON) src/portada_episodio.py --fecha $(FECHA)

noche: ## Lo que se lanza solo a las 22:00: guion y audio del episodio de mañana
	scripts/noche.sh

programar: ## Tras aprobar: audio al día, subida a R2 y publicación automática a las 6:00
	$(MAKE) audio FECHA=$(FECHA)
	-$(MAKE) portada FECHA=$(FECHA)
	$(PYTHON) src/publish.py --fecha $(FECHA) --programar

instalar-noche: ## Instala la preparación automática de las 22:00 (domingo a jueves)
	@mkdir -p logs $(dir $(PLIST))
	@sed "s|RUTA_CATODO|$(CURDIR)|g" scripts/es.catodo.noche.plist > "$(PLIST)"
	@launchctl bootout gui/$$(id -u) "$(PLIST)" 2>/dev/null || true
	launchctl bootstrap gui/$$(id -u) "$(PLIST)"
	@echo "Instalado: Cátodo se preparará solo a las 22:00 de domingo a jueves."

desinstalar-noche: ## Quita la preparación automática de las 22:00
	@launchctl bootout gui/$$(id -u) "$(PLIST)" 2>/dev/null || true
	@$(PYTHON) -c "import pathlib; pathlib.Path('$(PLIST)').unlink(missing_ok=True)"
	@echo "Desinstalado."

publicar: ## Publica ya el episodio aprobado: R2, feed, web y push (sin esperar a las 6:00)
	$(PYTHON) src/publish.py --fecha $(FECHA)

simulacro: ## Prueba la publicación sin subir nada (feed y web en una carpeta temporal)
	$(PYTHON) src/publish.py --fecha $(FECHA) --simulacro

feed: ## Regenera docs/feed.xml y la web a partir de los episodios publicados
	$(PYTHON) src/feed.py


probar-voces: ## Prueba a ciegas de voces (pruebas/voces.toml)
	python3 pruebas/prueba_voces.py
