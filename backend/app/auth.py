from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
try:
    from backend.app.models import User
    from backend.app.database import get_db
except ImportError:
    from app.models import User
    from app.database import get_db
import os
from dotenv import load_dotenv

load_dotenv()

import bcrypt

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash using native bcrypt"""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        # Fallback for legacy hashes
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False

def get_password_hash(password: str) -> str:
    """Hash a password using native bcrypt"""
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def get_user_by_email(db: Session, email: str):
    """Get user by email (case-insensitive)"""
    if not email:
        return None
    normalized_email = email.lower().strip()
    return db.query(User).filter(User.email.ilike(normalized_email)).first()

def authenticate_user(db: Session, email: str, password: str):
    """Authenticate user with email and password"""
    user = get_user_by_email(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_admin_user(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get current admin user, auto-elevates designated admin email, blocks non-admins with 403"""
    admin_email_env = os.getenv("ADMIN_EMAIL", "18dkkaushik@gmail.com").lower().strip()
    user_email = current_user.email.lower().strip()
    
    if user_email == admin_email_env or user_email == "18dkkaushik@gmail.com":
        if not current_user.is_admin:
            current_user.is_admin = True
            db.commit()
            db.refresh(current_user)
        return current_user
        
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

def create_user(db: Session, email: str, password: str, full_name: str = None):
    """Create a new user"""
    normalized_email = email.lower().strip()
    # Check if user already exists
    if get_user_by_email(db, normalized_email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    admin_email_env = os.getenv("ADMIN_EMAIL", "18dkkaushik@gmail.com").lower().strip()
    is_admin_user = (normalized_email == admin_email_env or normalized_email == "18dkkaushik@gmail.com")
    
    hashed_password = get_password_hash(password)
    db_user = User(
        email=normalized_email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_active=True,
        is_verified=False,
        is_admin=is_admin_user
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user