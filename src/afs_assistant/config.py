"""Paths and runtime settings. Everything configurable comes from the environment (.env)."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

MATERIALS_DIR = Path(os.getenv("AFS_MATERIALS_DIR", REPO_ROOT / "materials"))
KB_DIR = REPO_ROOT / "kb"
KB_CACHE_DIR = KB_DIR / "cache"
CHUNKS_PATH = KB_CACHE_DIR / "chunks.jsonl"
FACTS_PATH = KB_DIR / "facts.yaml"
FIGURE_NOTES_PATH = KB_DIR / "figure_notes.yaml"
OUTPUTS_DIR = REPO_ROOT / "outputs"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # anthropic | bedrock
MODEL = os.getenv("AFS_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("AFS_EFFORT", "high")

# Source files as named in the challenge materials. The ID is what the assistant cites.
SOURCE_FILES = {
    "S01": "S01_Multispectral_Laboratory.pdf",
    "S02": "S02_AFS_Process_Control_Slides.pdf",
    "S03": "S03_LED_Kidney_Study_2017.pdf",
    "S04": "S04_Combi_MIR_Fluorescence_2021.pdf",
    "S05": "S05_AFS_Flyer.pdf",
    "S06": "S06_Laboratory_Link.txt",
    "TABLE": "AFS_method_comparison_table.xlsx",
    "DOCX": "AFS_Examples_and_Reference.docx",
    "SCENARIOS": "customer_scenarios_for_final_evaluation.txt",
}
