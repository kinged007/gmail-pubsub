"""
SQLAlchemy database wrapper for Gmail Push Processing application.

This module provides a simple interface for database operations with support for:
- SQLite (development/local)
- PostgreSQL (production)
- Connection management
- Session handling
- Model base class
"""

import os
from typing import Optional, Type, TypeVar, Generic, List, Any
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from pathlib import Path
from src.utils.logger import setup_logger
from src.config import config

logger = setup_logger(__name__)

# Type variables for generic types
T = TypeVar('T')

# SQLAlchemy base class for all models
Base = declarative_base()

class DatabaseManager:
    """
    Database connection and session management.
    
    Supports both SQLite and PostgreSQL based on connection string.
    Provides simple connect/disconnect methods and session management.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: Database connection string or SQLite file path.
                         If None, checks DATABASE_URL environment variable.
                         If empty/None, database functionality is disabled.
        """
        self.database_url = database_url or config.get('database.url', '').strip()
        self.engine = None
        self.SessionLocal = None
        self.is_connected = False

        # If no database URL provided, disable database functionality
        if not self.database_url:
            logger.info("No database URL provided, database functionality disabled")
            return
            
        self._process_database_url()
    
    def _process_database_url(self):
        """Process and validate the database URL."""
        if not self.database_url:
            return
            
        # Handle SQLite file paths (relative or absolute)
        if not self.database_url.startswith(('sqlite:///', 'postgresql://', 'postgres://')):
            # Assume it's a SQLite file path
            sqlite_path = Path(self.database_url)
            
            # Create directory if it doesn't exist
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to SQLite URL
            if sqlite_path.is_absolute():
                self.database_url = f"sqlite:///{sqlite_path}"
            else:
                self.database_url = f"sqlite:///{sqlite_path.resolve()}"
            
        logger.info(f"Database URL configured: {self._mask_url(self.database_url)}")
    
    def _mask_url(self, url: str) -> str:
        """Mask sensitive information in database URL for logging."""
        if not url:
            return "None"
        
        # Mask password in PostgreSQL URLs
        if 'postgresql://' in url or 'postgres://' in url:
            parts = url.split('@')
            if len(parts) > 1:
                user_pass = parts[0].split('//')[-1]
                if ':' in user_pass:
                    user, _ = user_pass.split(':', 1)
                    masked = f"{url.split('//')[0]}//{user}:***@{parts[1]}"
                    return masked
        return url
    
    def connect(self) -> bool:
        """
        Establish database connection and create tables.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not self.database_url:
            logger.warning("No database URL configured, cannot connect")
            return False
            
        if self.is_connected:
            logger.info("Database already connected")
            return True
            
        try:
            # Create engine with appropriate settings
            if self.database_url.startswith('sqlite:'):
                # SQLite specific settings
                self.engine = create_engine(
                    self.database_url,
                    connect_args={"check_same_thread": False},  # Allow multiple threads
                    echo=False  # Set to True for SQL debugging
                )
            else:
                # PostgreSQL settings
                self.engine = create_engine(
                    self.database_url,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,  # Verify connections before use
                    echo=False  # Set to True for SQL debugging
                )
            
            # Test connection
            with self.engine.connect() as conn:
                if self.database_url.startswith('sqlite:'):
                    conn.execute(text("SELECT 1"))
                else:
                    conn.execute(text("SELECT version()"))
            
            # Create session factory
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # Create all tables
            self.create_tables()
            
            self.is_connected = True
            logger.info(f"✅ Database connected successfully: {self._mask_url(self.database_url)}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"❌ Database connection failed: {e}")
            self.engine = None
            self.SessionLocal = None
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to database: {e}")
            self.engine = None
            self.SessionLocal = None
            return False
    
    def disconnect(self):
        """Close database connection and cleanup resources."""
        if self.engine:
            try:
                self.engine.dispose()
                logger.info("✅ Database disconnected successfully")
            except Exception as e:
                logger.error(f"❌ Error disconnecting database: {e}")
            finally:
                self.engine = None
                self.SessionLocal = None
                self.is_connected = False
    
    def create_tables(self):
        """Create all database tables defined in models."""
        if not self.engine:
            logger.warning("No database engine, cannot create tables")
            return
            
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ Database tables created/verified")
        except SQLAlchemyError as e:
            logger.error(f"❌ Error creating database tables: {e}")
            raise
    
    def drop_tables(self):
        """Drop all database tables. Use with caution!"""
        if not self.engine:
            logger.warning("No database engine, cannot drop tables")
            return
            
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("⚠️ All database tables dropped")
        except SQLAlchemyError as e:
            logger.error(f"❌ Error dropping database tables: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """
        Get a database session with automatic cleanup.
        
        Usage:
            with db.get_session() as session:
                # Use session here
                pass
        """
        if not self.is_connected or not self.SessionLocal:
            raise RuntimeError("Database not connected. Call connect() first.")
            
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_raw_session(self) -> Optional[Session]:
        """
        Get a raw database session for manual management.
        
        Warning: You must manage this session manually (commit/rollback/close).
        
        Returns:
            Session object or None if not connected
        """
        if not self.is_connected or not self.SessionLocal:
            logger.warning("Database not connected, cannot create session")
            return None
            
        return self.SessionLocal()
    
    def execute_raw(self, query: str, params: dict = None) -> Any:
        """
        Execute raw SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Query result
        """
        if not self.is_connected:
            raise RuntimeError("Database not connected")
            
        with self.get_session() as session:
            return session.execute(text(query), params or {})
    
    def health_check(self) -> dict:
        """
        Perform database health check.
        
        Returns:
            dict: Health status information
        """
        if not self.database_url:
            return {
                'status': 'disabled',
                'message': 'Database functionality disabled (no URL configured)'
            }
            
        if not self.is_connected:
            return {
                'status': 'disconnected',
                'message': 'Database not connected'
            }
            
        try:
            with self.get_session() as session:
                if self.database_url.startswith('sqlite:'):
                    result = session.execute(text("SELECT 1 as test")).fetchone()
                else:
                    result = session.execute(text("SELECT 1 as test, version() as version")).fetchone()
                
                return {
                    'status': 'healthy',
                    'connected': True,
                    'url_type': 'sqlite' if self.database_url.startswith('sqlite:') else 'postgresql',
                    'test_query': bool(result)
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Health check failed: {str(e)}'
            }


class BaseRepository(Generic[T]):
    """
    Base repository class for database operations.
    
    Provides common CRUD operations for any model type.
    """
    
    def __init__(self, db: DatabaseManager, model_class: Type[T]):
        """
        Initialize repository.
        
        Args:
            db: Database manager instance
            model_class: SQLAlchemy model class
        """
        self.db = db
        self.model_class = model_class
    
    def create(self, **kwargs) -> Optional[T]:
        """Create a new record."""
        if not self.db.is_connected:
            logger.warning("Database not connected, cannot create record")
            return None
            
        try:
            with self.db.get_session() as session:
                instance = self.model_class(**kwargs)
                session.add(instance)
                session.flush()  # Get the ID
                session.refresh(instance)  # Refresh to get computed fields
                return instance
        except Exception as e:
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            raise
    
    def get_by_id(self, id: Any) -> Optional[T]:
        """Get record by ID."""
        if not self.db.is_connected:
            return None
            
        try:
            with self.db.get_session() as session:
                return session.query(self.model_class).filter(self.model_class.id == id).first()
        except Exception as e:
            logger.error(f"Error getting {self.model_class.__name__} by ID {id}: {e}")
            return None
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all records with pagination."""
        if not self.db.is_connected:
            return []
            
        try:
            with self.db.get_session() as session:
                return session.query(self.model_class).offset(offset).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting all {self.model_class.__name__}: {e}")
            return []
    
    def update(self, id: Any, **kwargs) -> Optional[T]:
        """Update record by ID."""
        if not self.db.is_connected:
            return None
            
        try:
            with self.db.get_session() as session:
                instance = session.query(self.model_class).filter(self.model_class.id == id).first()
                if instance:
                    for key, value in kwargs.items():
                        if hasattr(instance, key):
                            setattr(instance, key, value)
                    session.flush()
                    session.refresh(instance)
                    return instance
                return None
        except Exception as e:
            logger.error(f"Error updating {self.model_class.__name__} {id}: {e}")
            raise
    
    def delete(self, id: Any) -> bool:
        """Delete record by ID."""
        if not self.db.is_connected:
            return False
            
        try:
            with self.db.get_session() as session:
                instance = session.query(self.model_class).filter(self.model_class.id == id).first()
                if instance:
                    session.delete(instance)
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting {self.model_class.__name__} {id}: {e}")
            raise
    
    def count(self) -> int:
        """Get total count of records."""
        if not self.db.is_connected:
            return 0
            
        try:
            with self.db.get_session() as session:
                return session.query(self.model_class).count()
        except Exception as e:
            logger.error(f"Error counting {self.model_class.__name__}: {e}")
            return 0


# Global database instance
db = DatabaseManager()


def get_database() -> DatabaseManager:
    """Get the global database instance."""
    return db


def init_database() -> bool:
    """
    Initialize database connection.
    
    This function should be called during application bootstrap.
    
    Returns:
        bool: True if database was initialized, False if disabled or failed
    """
    return db.connect()


def close_database():
    """Close database connection during application shutdown."""
    db.disconnect()
