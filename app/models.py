from datetime import datetime
from typing import List, Tuple
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean
from sqlalchemy.sql import func
from src.database import Base, BaseRepository, get_database



class SampleTableModel(Base):
    """Sample table model."""
    
    __tablename__ = 'sample_table'
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Email tracking
    email_id = Column(String(255), unique=True, index=True, nullable=False)
    email_subject = Column(String(500))
    email_sender = Column(String(255))
    email_received_at = Column(DateTime(timezone=True))
    email_snippet = Column(Text)


