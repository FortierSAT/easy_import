#!/usr/bin/env python3
import sys
import os
import logging

# 1) Add your src/ directory to the path
HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# 2) Now import your scraper
from main import escreen_scraper, DOWNLOAD_PATHS

# 3) Turn on debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# 4) Run it
if __name__ == "__main__":
    try:
        xlsx = escreen_scraper()
        print("✅ escreen_scraper returned:", xlsx)
    except Exception:
        logger.exception("💥 escreen_scraper exploded")
