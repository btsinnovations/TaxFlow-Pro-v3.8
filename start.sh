#!/bin/bash
set -e
cd ~/Desktop/TaxFlow-Pro
source venv/bin/activate
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
