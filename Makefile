# Cátodo: comandos del día a día. Ejecuta `make` para ver la ayuda.

PYTHON := .venv/bin/python
FECHA  ?= $(shell date +%Y-%m-%d)

.DEFAULT_GOAL := ayuda
.PHONY: ayuda instalar noticias guion preparar memoria aprobar marcar-publicado corregir reservas publicar probar-voces

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

publicar: ## Voz, montaje, subida a R2, feed y push (Fases 3 y 4)
	@echo "Pendiente: Fases 3 y 4 (tts.py, mix.py, publish.py, feed.py)"

probar-voces: ## Prueba a ciegas de voces (pruebas/voces.toml)
	python3 pruebas/prueba_voces.py
