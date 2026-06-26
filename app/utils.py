# utils.py

import os
from config import DEFAULT_CONFIGS

def getenv_bool(name: str, default: bool = False) -> bool:
    # The default parameter for getenv_bool is used if the config default itself needs a fallback,
    # or if the call site specifically wants to override the global default.
    return os.getenv(name, str(default)).lower() in ("yes", "y", "true", "1", "t")

# DETAILED_ERROR_LOGGING is used in tts_handler.py
DETAILED_ERROR_LOGGING = getenv_bool('DETAILED_ERROR_LOGGING', DEFAULT_CONFIGS["DETAILED_ERROR_LOGGING"])
