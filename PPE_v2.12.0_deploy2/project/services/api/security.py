"""
PPE Detection - Security Module
Безопасность: rate limiting, audit log, input validation, secrets management
"""

import os
import re
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from functools import wraps
import ipaddress

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis.asyncio as redis
import jwt

# ============================================================================
# CONFIGURATION
# ============================================================================

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Rate limiting defaults
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

# Trusted proxies (for X-Forwarded-For)
TRUSTED_PROXIES = os.getenv("TRUSTED_PROXIES", "127.0.0.1,172.16.0.0/12").split(",")

# Logging
logger = logging.getLogger(__name__)


# ============================================================================
# SECRET MANAGEMENT
# ============================================================================

class SecretManager:
    """Secure secret management."""
    
    @staticmethod
    def generate_secret(length: int = 64) -> str:
        """Generate cryptographically secure secret."""
        return secrets.token_hex(length // 2)
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash password with salt using SHA-256."""
        if salt is None:
            salt = secrets.token_hex(16)
        
        salted = f"{salt}{password}"
        hashed = hashlib.sha256(salted.encode()).hexdigest()
        
        return hashed, salt
    
    @staticmethod
    def verify_password(password: str, hashed: str, salt: str) -> bool:
        """Verify password against hash."""
        computed, _ = SecretManager.hash_password(password, salt)
        return secrets.compare_digest(computed, hashed)
    
    @staticmethod
    def mask_secret(secret: str, visible_chars: int = 4) -> str:
        """Mask secret for logging."""
        if len(secret) <= visible_chars * 2:
            return "*" * len(secret)
        return secret[:visible_chars] + "*" * (len(secret) - visible_chars * 2) + secret[-visible_chars:]


# ============================================================================
# JWT TOKEN MANAGEMENT
# ============================================================================

class JWTManager:
    """JWT token management with security best practices."""
    
    def __init__(self, secret: str = JWT_SECRET, algorithm: str = JWT_ALGORITHM):
        if not secret:
            raise ValueError("JWT_SECRET must be set!")
        if len(secret) < 32:
            logger.warning("JWT_SECRET is too short! Recommended: 64+ characters")
        
        self.secret = secret
        self.algorithm = algorithm
    
    def create_token(
        self, 
        user_id: str, 
        username: str,
        role: str = "user",
        expires_hours: int = JWT_EXPIRATION_HOURS,
        additional_claims: Optional[dict] = None
    ) -> str:
        """Create JWT token."""
        now = datetime.utcnow()
        
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=expires_hours),
            "jti": secrets.token_hex(16),  # Unique token ID
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
    
    def refresh_token(self, token: str) -> str:
        """Refresh token if valid."""
        payload = self.verify_token(token)
        return self.create_token(
            user_id=payload["sub"],
            username=payload["username"],
            role=payload.get("role", "user")
        )


# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """Redis-based rate limiter."""
    
    def __init__(
        self, 
        redis_client: redis.Redis,
        requests: int = RATE_LIMIT_REQUESTS,
        window: int = RATE_LIMIT_WINDOW
    ):
        self.redis = redis_client
        self.requests = requests
        self.window = window
    
    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check if request is allowed.
        Returns: (allowed, remaining_requests)
        """
        now = datetime.now().timestamp()
        window_start = now - self.window
        
        # Use sorted set for sliding window
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(f"ratelimit:{key}", 0, window_start)
        
        # Count current entries
        pipe.zcard(f"ratelimit:{key}")
        
        # Add current request
        pipe.zadd(f"ratelimit:{key}", {str(now): now})
        
        # Set expiry
        pipe.expire(f"ratelimit:{key}", self.window)
        
        results = await pipe.execute()
        current_count = results[1]
        
        remaining = max(0, self.requests - current_count)
        allowed = current_count < self.requests
        
        return allowed, remaining
    
    async def get_reset_time(self, key: str) -> int:
        """Get seconds until rate limit resets."""
        oldest = await self.redis.zrange(f"ratelimit:{key}", 0, 0, withscores=True)
        if oldest:
            oldest_time = oldest[0][1]
            reset_time = int(oldest_time + self.window - datetime.now().timestamp())
            return max(0, reset_time)
        return 0


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, redis_url: str = REDIS_URL, requests: int = RATE_LIMIT_REQUESTS):
        self.redis_url = redis_url
        self.requests = requests
        self._redis: Optional[redis.Redis] = None
        self._limiter: Optional[RateLimiter] = None
    
    async def _get_limiter(self) -> RateLimiter:
        if self._limiter is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            self._limiter = RateLimiter(self._redis, self.requests)
        return self._limiter
    
    def get_client_ip(self, request: Request) -> str:
        """Get client IP, handling proxies."""
        # Check X-Forwarded-For
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get first non-trusted proxy IP
            ips = [ip.strip() for ip in forwarded.split(",")]
            for ip in ips:
                if not self._is_trusted_proxy(ip):
                    return ip
        
        # Fall back to direct connection
        return request.client.host if request.client else "unknown"
    
    def _is_trusted_proxy(self, ip: str) -> bool:
        """Check if IP is a trusted proxy."""
        try:
            client_ip = ipaddress.ip_address(ip)
            for proxy in TRUSTED_PROXIES:
                if "/" in proxy:
                    if client_ip in ipaddress.ip_network(proxy, strict=False):
                        return True
                elif ip == proxy:
                    return True
        except ValueError:
            pass
        return False
    
    async def __call__(self, request: Request, call_next: Callable) -> Any:
        """Process request with rate limiting."""
        client_ip = self.get_client_ip(request)
        limiter = await self._get_limiter()
        
        allowed, remaining = await limiter.is_allowed(client_ip)
        
        if not allowed:
            reset_time = await limiter.get_reset_time(client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Retry after {reset_time} seconds.",
                headers={
                    "X-RateLimit-Limit": str(self.requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time)
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response


# ============================================================================
# AUDIT LOGGING
# ============================================================================

class AuditLogger:
    """Audit logging for security events."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.logger = logging.getLogger("audit")
        
        # Configure audit logger
        handler = logging.FileHandler("/var/log/ppe/audit.log")
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def log(
        self,
        event_type: str,
        user_id: Optional[str],
        action: str,
        resource: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        success: bool = True
    ):
        """Log audit event."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "details": details,
            "ip_address": ip_address,
            "success": success
        }
        
        # Log to file
        status_str = "SUCCESS" if success else "FAILURE"
        self.logger.info(
            f"{event_type} | {status_str} | user={user_id} | action={action} | "
            f"resource={resource} | ip={ip_address}"
        )
        
        # Store in Redis (last 1000 events)
        if self.redis:
            import json
            await self.redis.lpush("audit:log", json.dumps(event))
            await self.redis.ltrim("audit:log", 0, 999)
    
    # Convenience methods
    async def log_login(self, user_id: str, ip: str, success: bool):
        await self.log("AUTH", user_id, "LOGIN", ip_address=ip, success=success)
    
    async def log_logout(self, user_id: str, ip: str):
        await self.log("AUTH", user_id, "LOGOUT", ip_address=ip)
    
    async def log_access(self, user_id: str, resource: str, action: str, ip: str):
        await self.log("ACCESS", user_id, action, resource=resource, ip_address=ip)
    
    async def log_violation_ack(self, user_id: str, violation_id: str, ip: str):
        await self.log(
            "VIOLATION", user_id, "ACKNOWLEDGE", 
            resource=f"violation:{violation_id}", ip_address=ip
        )
    
    async def log_config_change(self, user_id: str, setting: str, ip: str, details: dict):
        await self.log(
            "CONFIG", user_id, "CHANGE", 
            resource=setting, details=details, ip_address=ip
        )


# ============================================================================
# INPUT VALIDATION
# ============================================================================

class InputValidator:
    """Input validation utilities."""
    
    # Patterns
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    CAMERA_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
    
    # Dangerous patterns (SQL injection, XSS, etc.)
    DANGEROUS_PATTERNS = [
        re.compile(r'<script', re.I),
        re.compile(r'javascript:', re.I),
        re.compile(r'on\w+\s*=', re.I),  # onclick=, onerror=, etc.
        re.compile(r'(union|select|insert|update|delete|drop)\s', re.I),
        re.compile(r';\s*(--|#|/\*)', re.I),  # SQL comment injection
    ]
    
    @classmethod
    def validate_username(cls, username: str) -> bool:
        """Validate username format."""
        return bool(cls.USERNAME_PATTERN.match(username))
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format."""
        return bool(cls.EMAIL_PATTERN.match(email))
    
    @classmethod
    def validate_camera_id(cls, camera_id: str) -> bool:
        """Validate camera ID format."""
        return bool(cls.CAMERA_ID_PATTERN.match(camera_id))
    
    @classmethod
    def validate_uuid(cls, uuid_str: str) -> bool:
        """Validate UUID format."""
        return bool(cls.UUID_PATTERN.match(uuid_str))
    
    @classmethod
    def is_safe_string(cls, value: str) -> bool:
        """Check if string is safe (no injection patterns)."""
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(value):
                return False
        return True
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        # Truncate
        value = value[:max_length]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Basic HTML escaping
        value = value.replace('&', '&amp;')
        value = value.replace('<', '&lt;')
        value = value.replace('>', '&gt;')
        value = value.replace('"', '&quot;')
        value = value.replace("'", '&#x27;')
        
        return value
    
    @classmethod
    def validate_violation_type(cls, vtype: str) -> bool:
        """Validate violation type."""
        valid_types = {'no_hardhat', 'no_vest', 'no_glasses', 'no_mask', 'no_gloves'}
        return vtype in valid_types


# ============================================================================
# SECURITY HEADERS MIDDLEWARE
# ============================================================================

async def security_headers_middleware(request: Request, call_next: Callable):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none';"
    )
    
    # Remove server header
    if "server" in response.headers:
        del response.headers["server"]
    
    return response


# ============================================================================
# CORS CONFIGURATION
# ============================================================================

def get_cors_config() -> dict:
    """Get CORS configuration."""
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:80").split(",")
    
    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]
    }


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = None
) -> dict:
    """Get current authenticated user from JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    jwt_manager = JWTManager()
    return jwt_manager.verify_token(credentials.credentials)


def require_role(required_role: str):
    """Decorator to require specific role."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            user = kwargs.get("current_user")
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated"
                )
            
            user_role = user.get("role", "user")
            
            # Role hierarchy
            roles = {"user": 1, "operator": 2, "admin": 3}
            if roles.get(user_role, 0) < roles.get(required_role, 0):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{required_role}' required"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
