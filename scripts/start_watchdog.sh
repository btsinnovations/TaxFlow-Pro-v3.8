#!/bin/bash
cd ~/Desktop/financial_etl_project
source venv/bin/activate
python -m phase3_pipeline.watchdog --input-dir "$HOME/Downloads" --output-dir "./output" --format qif