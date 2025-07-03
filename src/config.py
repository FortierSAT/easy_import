import logging
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# auto-locate the first .env in parent directories
env_file = find_dotenv()
print(f"→ loading env vars from {env_file}")
load_dotenv(env_file)

# Logging config
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

# 3) Database credentials (must come *after* load_dotenv)
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_NAME     = os.getenv("DB_NAME")

# 4) Debug print so we can see in logs if any are missing
print(f"→ config.py loaded → DB_USER={DB_USER!r}, DB_HOST={DB_HOST!r}, DB_PORT={DB_PORT!r}, DB_NAME={DB_NAME!r}")

# 5) Now build the SQLAlchemy URL
DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# 6) Zoho CRM and other creds
ZOHO_CLIENT_ID     = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")
ZOHO_API_BASE      = os.getenv("ZOHO_API_BASE")
ZOHO_MODULE        = os.getenv("ZOHO_MODULE")

CRL_USER = os.getenv("CRL_USER")
CRL_PASS = os.getenv("CRL_PASS")
I3_USER  = os.getenv("I3_USER")
I3_PASS  = os.getenv("I3_PASS")
