"""Deprecated local config module.

Use environment variables instead of hardcoded secrets.
This file is kept only for backward compatibility with older imports.
"""

import os

# ENTSOE API key should come from environment or .env
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")

# ENTSOE API Base URL (non-secret)
ENTSOE_BASE_URL = "https://web-api.tp.entsoe.eu/api"
