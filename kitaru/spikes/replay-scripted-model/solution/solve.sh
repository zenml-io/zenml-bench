#!/usr/bin/env bash
cd /app && python run_spike.py --n 20 --rounds 5 --out /app/spike3.json > /app/run_spike.log 2>&1
