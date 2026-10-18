PY := .venv/bin/python

.PHONY: setup kb test eval eval-score

setup:            ## create venv and install the package (editable) with dev tools
	python3.11 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e ".[dev]"

kb:               ## build the knowledge-base cache from materials/ into kb/cache/
	$(PY) -m afs_assistant.kb.build

test:
	$(PY) -m pytest -q

eval:             ## run D01-D08, print rubric table + diff vs worked answers (D01/D02)
	$(PY) eval/run_eval.py --set D

eval-score:       ## re-score existing D outputs without API calls
	$(PY) eval/run_eval.py --set D --no-run
