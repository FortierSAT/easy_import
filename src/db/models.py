# src/db/models.py

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Integer, String, Text

from db.session import Base


class WorklistStaging(Base):
    __tablename__ = "worklist_staging"

    ccfid = Column(Text, primary_key=True)
    first_name = Column(Text)
    last_name = Column(Text)
    primary_id = Column(Text)
    company_code = Column(Text)
    company_name = Column(Text)
    collection_site = Column(Text)
    collection_site_id = Column(Text)
    laboratory = Column(Text)
    location = Column(Text)
    test_reason = Column(Text)
    test_result = Column(Text)
    test_type = Column(Text)
    regulation = Column(Text)
    collection_date = Column(Date)
    mro_received = Column(Date)
    reviewed = Column(Boolean, default=False)
    uploaded_timestamp = Column(DateTime)


class CollectionSite(Base):
    __tablename__ = "collection_sites"

    Record_id = Column(Text, primary_key=True)
    Collection_Site = Column(Text)
    Collection_Site_ID = Column(Text)


class Company(Base):
    __tablename__ = "account_info"

    account_id = Column(Text, primary_key=True)
    account_code = Column(Text, unique=True, index=True)
    account_name = Column(Text)


class Laboratory(Base):
    __tablename__ = "laboratories"

    Record_id = Column(Text, primary_key=True)
    Laboratory = Column(Text, unique=True, index=True)
