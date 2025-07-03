# src/db/session.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL

# 1) Create the engine
engine = create_engine(DATABASE_URL)

# 2) Configure session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3) Define Base for model classes
Base = declarative_base()
