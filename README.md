# EU Energy Analytics Bot

A market monitoring project for European power data. It tracks prices, load, generation, and cross-border flows, then turns them into a compact set of files, charts, and summaries for review.

## Overview

The project uses ENTSO-E data to pull recent market information for a selected country and related cross-border flows. It saves the raw outputs, generates a small set of charts, and runs a basic analysis step for a quick market snapshot.

## What It Produces

The pipeline generates:

- day-ahead price data
- generation data
- load data
- cross-border flow data
- charts for key series
- a summary report

## Main Files

- `main.py` fetches data and writes output files
- `EnergyAnalysis.py` runs the analysis step
- `send_energy_report.py` formats and sends a report through Telegram
- `docs/` contains reference notes for the project
- `examples/outputs/` contains sample charts and data files

## Setup

1. Install dependencies:
   ```bash
   pip install entsoe-py pandas matplotlib requests python-dotenv
   ```

2. Add the required environment variables in a local `.env` file.

3. Run:
   ```bash
   python3 main.py
   ```

## Notes

This repository is intended as a personal market monitoring workflow. It is useful for collecting and reviewing recent power market data, not as a full trading system.
