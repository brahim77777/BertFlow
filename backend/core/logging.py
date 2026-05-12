from __future__ import annotations

import logging
import sys

logger = logging.getLogger("bertflow")
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
)
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
