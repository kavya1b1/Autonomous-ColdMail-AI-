"""SQLAlchemy database models"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, JSON, Float, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()


class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    linkedin = Column(String(500), nullable=True)
    github = Column(String(500), nullable=True)
    portfolio = Column(String(500), nullable=True)
    leetcode = Column(String(500), nullable=True)
    college = Column(String(255), nullable=True)
    degree = Column(String(255), nullable=True)
    graduation_year = Column(Integer, nullable=True)
    skills = Column(JSON, default=list)
    objective = Column(Text, nullable=True)
    tone = Column(String(50), default="professional")
    resume_path = Column(String(500), nullable=True)
    resume_filename = Column(String(255), nullable=True)
    profile_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaigns = relationship("CampaignDB", back_populates="user")
    campaign_records = relationship("CampaignRecordDB", back_populates="user")


class CompanyDB(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    tech_stack = Column(JSON, default=list)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)
    careers_page = Column(String(500), nullable=True)
    culture_notes = Column(Text, nullable=True)
    recent_news = Column(Text, nullable=True)
    embedding_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emails = relationship("GeneratedEmailDB", back_populates="company")


class CampaignDB(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    goal = Column(String(50), nullable=False)
    status = Column(String(50), default="draft")
    recipients = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    stats = Column(JSON, default=dict)

    user = relationship("UserDB", back_populates="campaigns")
    emails = relationship("GeneratedEmailDB", back_populates="campaign")


class GeneratedEmailDB(Base):
    __tablename__ = "generated_emails"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    recipient_email = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    personalization_score = Column(Integer, default=5)
    key_points_used = Column(JSON, default=list)
    approved = Column(Boolean, default=False)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("CampaignDB", back_populates="emails")
    company = relationship("CompanyDB", back_populates="emails")


class AnalyticsDB(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    emails_sent = Column(Integer, default=0)
    emails_failed = Column(Integer, default=0)
    response_count = Column(Integer, default=0)
    response_rate = Column(Float, default=0.0)
    avg_personalization_score = Column(Float, default=0.0)
    top_performing_subject = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MemoryDB(Base):
    __tablename__ = "memory"

    id = Column(Integer, primary_key=True, index=True)
    memory_type = Column(String(50), nullable=False)  # company, email, interaction
    content = Column(Text, nullable=False)
    embedding_id = Column(String(100), nullable=True)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class CampaignRecordDB(Base):
    """Lightweight, self-contained persistence for campaign/dashboard history.

    The normalized Company/Campaign/GeneratedEmail tables above model a fuller
    schema but were never wired into the running workflow (see api/dependencies/store.py).
    Rather than force campaign runs through that heavier relational shape (which
    would require, e.g., a full Company row per recipient domain), this table
    stores each campaign run as a per-user JSON snapshot: enough to survive a
    server restart and power the dashboard/analytics/applications views, while
    the live LangGraph checkpointer remains the source of truth for in-flight
    (not-yet-sent) campaigns during a single server session.
    """
    __tablename__ = "campaign_records"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    goal = Column(String(50), nullable=False)
    status = Column(String(50), default="awaiting_approval")
    total_emails = Column(Integer, default=0)
    sent = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    avg_personalization = Column(Float, default=0.0)
    companies = Column(JSON, default=list)
    emails = Column(JSON, default=list)  # snapshot of generated/sent emails (dicts)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    user = relationship("UserDB", back_populates="campaign_records")


def init_database(database_url: str):
    """Initialize database tables"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Get database session"""
    Session = sessionmaker(bind=engine)
    return Session()
