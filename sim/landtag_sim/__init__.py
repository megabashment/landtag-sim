"""Reine Simulationslogik ohne DB-Abhaengigkeit.

Warum als eigenes Package getrennt vom Backend: sim/tools/balance_runner.py
muss hunderte Szenarien schnell und ohne Postgres durchrechnen koennen, um
das Traegheitsmodell (verzoegerte Policy-Effekte) zu balancieren. Das
FastAPI-Backend (backend/app) importiert dieselbe Engine und uebersetzt nur
zwischen DB-Modellen und den hier definierten reinen Datenklassen.
"""
