"""
Integration Tests for PPE Detection API
Тестирует взаимодействие: API ↔ PostgreSQL ↔ Redis
"""

import pytest
import asyncio
import httpx
import asyncpg
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import AsyncGenerator
import os
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

API_URL = os.getenv("API_URL", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ppe:ppe_secret@localhost:5432/ppe_detection")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Test credentials
TEST_USER = "admin"
TEST_PASSWORD = "admin123"


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Create database connection pool."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    yield pool
    await pool.close()


@pytest.fixture(scope="session")
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Create Redis client."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.close()


@pytest.fixture(scope="session")
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create HTTP client for API requests."""
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
async def auth_token(http_client: httpx.AsyncClient) -> str:
    """Get authentication token."""
    response = await http_client.post(
        "/api/auth/login",
        json={"username": TEST_USER, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture
async def auth_headers(auth_token: str) -> dict:
    """Get authorization headers."""
    return {"Authorization": f"Bearer {auth_token}"}


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

class TestHealthChecks:
    """Test service health endpoints."""

    @pytest.mark.asyncio
    async def test_api_health(self, http_client: httpx.AsyncClient):
        """Test API health endpoint."""
        response = await http_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_database_connection(self, db_pool: asyncpg.Pool):
        """Test database connectivity."""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1

    @pytest.mark.asyncio
    async def test_redis_connection(self, redis_client: redis.Redis):
        """Test Redis connectivity."""
        await redis_client.set("test_key", "test_value", ex=10)
        value = await redis_client.get("test_key")
        assert value == "test_value"
        await redis_client.delete("test_key")


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

class TestAuthentication:
    """Test authentication flow."""

    @pytest.mark.asyncio
    async def test_login_success(self, http_client: httpx.AsyncClient):
        """Test successful login."""
        response = await http_client.post(
            "/api/auth/login",
            json={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, http_client: httpx.AsyncClient):
        """Test login with invalid credentials."""
        response = await http_client.post(
            "/api/auth/login",
            json={"username": "invalid", "password": "invalid"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self, http_client: httpx.AsyncClient):
        """Test accessing protected endpoint without token."""
        response = await http_client.get("/api/violations")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_token(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test accessing protected endpoint with valid token."""
        response = await http_client.get("/api/violations", headers=auth_headers)
        assert response.status_code == 200


# ============================================================================
# VIOLATIONS API TESTS
# ============================================================================

class TestViolationsAPI:
    """Test violations CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_violations_empty(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test getting violations list."""
        response = await http_client.get("/api/violations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_create_violation(
        self, 
        http_client: httpx.AsyncClient, 
        auth_headers: dict,
        db_pool: asyncpg.Pool
    ):
        """Test creating a new violation."""
        violation_data = {
            "camera_id": "test_camera_001",
            "violation_type": "no_hardhat",
            "confidence": 0.95,
            "person_id": "track_123",
            "zone_id": "zone_1",
            "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 100}
        }
        
        response = await http_client.post(
            "/api/violations",
            json=violation_data,
            headers=auth_headers
        )
        
        # Может быть 201 Created или 200 OK
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        
        # Verify in database
        async with db_pool.acquire() as conn:
            db_violation = await conn.fetchrow(
                "SELECT * FROM violations WHERE id = $1",
                data["id"]
            )
            assert db_violation is not None
            assert db_violation["camera_id"] == "test_camera_001"
            assert db_violation["violation_type"] == "no_hardhat"

    @pytest.mark.asyncio
    async def test_get_violations_filtered(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test getting violations with filters."""
        # Filter by camera
        response = await http_client.get(
            "/api/violations?camera_id=test_camera_001",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Filter by violation type
        response = await http_client.get(
            "/api/violations?violation_type=no_hardhat",
            headers=auth_headers
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_violations_pagination(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test violations pagination."""
        response = await http_client.get(
            "/api/violations?limit=10&offset=0",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 10

    @pytest.mark.asyncio
    async def test_acknowledge_violation(
        self,
        http_client: httpx.AsyncClient,
        auth_headers: dict,
        db_pool: asyncpg.Pool
    ):
        """Test acknowledging a violation."""
        # First create a violation
        async with db_pool.acquire() as conn:
            violation_id = await conn.fetchval("""
                INSERT INTO violations (camera_id, violation_type, confidence, timestamp)
                VALUES ('test_cam', 'no_vest', 0.9, NOW())
                RETURNING id
            """)
        
        # Acknowledge it
        response = await http_client.post(
            f"/api/violations/{violation_id}/acknowledge",
            headers=auth_headers
        )
        assert response.status_code in [200, 204]
        
        # Verify in database
        async with db_pool.acquire() as conn:
            violation = await conn.fetchrow(
                "SELECT acknowledged, acknowledged_at FROM violations WHERE id = $1",
                violation_id
            )
            assert violation["acknowledged"] is True
            assert violation["acknowledged_at"] is not None


# ============================================================================
# CAMERAS API TESTS
# ============================================================================

class TestCamerasAPI:
    """Test cameras endpoints."""

    @pytest.mark.asyncio
    async def test_get_cameras(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test getting cameras list."""
        response = await http_client.get("/api/cameras", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_camera_status(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test getting camera status."""
        response = await http_client.get("/api/cameras/status", headers=auth_headers)
        assert response.status_code == 200


# ============================================================================
# STATISTICS API TESTS
# ============================================================================

class TestStatisticsAPI:
    """Test statistics and analytics endpoints."""

    @pytest.mark.asyncio
    async def test_get_stats_summary(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test getting statistics summary."""
        response = await http_client.get("/api/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_violations" in data or "violations_today" in data

    @pytest.mark.asyncio
    async def test_get_stats_by_hour(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test getting hourly statistics."""
        response = await http_client.get("/api/stats/by-hour", headers=auth_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_stats_by_camera(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test getting statistics by camera."""
        response = await http_client.get("/api/stats/by-camera", headers=auth_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_stats_by_type(
        self, http_client: httpx.AsyncClient, auth_headers: dict
    ):
        """Test getting statistics by violation type."""
        response = await http_client.get("/api/stats/by-type", headers=auth_headers)
        assert response.status_code == 200


# ============================================================================
# REDIS INTEGRATION TESTS
# ============================================================================

class TestRedisIntegration:
    """Test Redis integration for caching and cooldowns."""

    @pytest.mark.asyncio
    async def test_violation_cooldown(self, redis_client: redis.Redis):
        """Test violation cooldown mechanism."""
        camera_id = "test_camera"
        person_id = "track_456"
        cooldown_key = f"cooldown:{camera_id}:{person_id}"
        
        # Set cooldown
        await redis_client.setex(cooldown_key, 60, "1")
        
        # Check cooldown exists
        exists = await redis_client.exists(cooldown_key)
        assert exists == 1
        
        # Check TTL
        ttl = await redis_client.ttl(cooldown_key)
        assert 0 < ttl <= 60
        
        # Cleanup
        await redis_client.delete(cooldown_key)

    @pytest.mark.asyncio
    async def test_camera_status_cache(self, redis_client: redis.Redis):
        """Test camera status caching."""
        camera_id = "cam_001"
        status_key = f"camera:status:{camera_id}"
        
        status_data = {
            "online": True,
            "fps": 25.0,
            "last_frame": datetime.now().isoformat()
        }
        
        await redis_client.set(status_key, json.dumps(status_data), ex=30)
        
        cached = await redis_client.get(status_key)
        assert cached is not None
        data = json.loads(cached)
        assert data["online"] is True
        assert data["fps"] == 25.0
        
        # Cleanup
        await redis_client.delete(status_key)

    @pytest.mark.asyncio
    async def test_redis_streams(self, redis_client: redis.Redis):
        """Test Redis Streams for frame queue."""
        stream_key = "test:frames"
        
        # Add to stream
        message_id = await redis_client.xadd(
            stream_key,
            {"camera_id": "cam_001", "frame_id": "12345"},
            maxlen=100
        )
        assert message_id is not None
        
        # Read from stream
        messages = await redis_client.xread({stream_key: "0"}, count=1)
        assert len(messages) > 0
        
        # Cleanup
        await redis_client.delete(stream_key)


# ============================================================================
# DATABASE INTEGRATION TESTS
# ============================================================================

class TestDatabaseIntegration:
    """Test database operations and constraints."""

    @pytest.mark.asyncio
    async def test_violations_table_constraints(self, db_pool: asyncpg.Pool):
        """Test violations table constraints."""
        async with db_pool.acquire() as conn:
            # Test valid insert
            violation_id = await conn.fetchval("""
                INSERT INTO violations (camera_id, violation_type, confidence, timestamp)
                VALUES ('cam_test', 'no_hardhat', 0.85, NOW())
                RETURNING id
            """)
            assert violation_id is not None
            
            # Cleanup
            await conn.execute("DELETE FROM violations WHERE id = $1", violation_id)

    @pytest.mark.asyncio
    async def test_violations_indexes(self, db_pool: asyncpg.Pool):
        """Test that important indexes exist."""
        async with db_pool.acquire() as conn:
            indexes = await conn.fetch("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'violations'
            """)
            index_names = [idx["indexname"] for idx in indexes]
            
            # Check that we have indexes (at least primary key)
            assert len(index_names) > 0

    @pytest.mark.asyncio
    async def test_concurrent_inserts(self, db_pool: asyncpg.Pool):
        """Test concurrent violation inserts."""
        async def insert_violation(i: int):
            async with db_pool.acquire() as conn:
                return await conn.fetchval("""
                    INSERT INTO violations (camera_id, violation_type, confidence, timestamp)
                    VALUES ($1, 'no_vest', 0.9, NOW())
                    RETURNING id
                """, f"concurrent_cam_{i}")
        
        # Insert 10 violations concurrently
        tasks = [insert_violation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 10
        assert all(r is not None for r in results)
        
        # Cleanup
        async with db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM violations WHERE camera_id LIKE 'concurrent_cam_%'"
            )


# ============================================================================
# END-TO-END FLOW TESTS
# ============================================================================

class TestE2EFlows:
    """Test complete end-to-end flows."""

    @pytest.mark.asyncio
    async def test_violation_flow(
        self,
        http_client: httpx.AsyncClient,
        auth_headers: dict,
        db_pool: asyncpg.Pool,
        redis_client: redis.Redis
    ):
        """Test complete violation detection flow."""
        camera_id = "e2e_test_camera"
        person_id = "e2e_track_001"
        
        # 1. Check no cooldown exists
        cooldown_key = f"cooldown:{camera_id}:{person_id}"
        await redis_client.delete(cooldown_key)
        
        # 2. Create violation via API
        response = await http_client.post(
            "/api/violations",
            json={
                "camera_id": camera_id,
                "violation_type": "no_hardhat",
                "confidence": 0.92,
                "person_id": person_id
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        violation = response.json()
        violation_id = violation["id"]
        
        # 3. Verify in database
        async with db_pool.acquire() as conn:
            db_record = await conn.fetchrow(
                "SELECT * FROM violations WHERE id = $1", violation_id
            )
            assert db_record is not None
            assert db_record["camera_id"] == camera_id
        
        # 4. Get violations list - should contain our violation
        response = await http_client.get(
            f"/api/violations?camera_id={camera_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        violations = response.json()
        assert any(v["id"] == violation_id for v in violations)
        
        # 5. Acknowledge violation
        response = await http_client.post(
            f"/api/violations/{violation_id}/acknowledge",
            headers=auth_headers
        )
        assert response.status_code in [200, 204]
        
        # 6. Verify acknowledgment
        async with db_pool.acquire() as conn:
            db_record = await conn.fetchrow(
                "SELECT acknowledged FROM violations WHERE id = $1", violation_id
            )
            assert db_record["acknowledged"] is True
        
        # Cleanup
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM violations WHERE id = $1", violation_id)

    @pytest.mark.asyncio
    async def test_statistics_after_violations(
        self,
        http_client: httpx.AsyncClient,
        auth_headers: dict,
        db_pool: asyncpg.Pool
    ):
        """Test statistics update after adding violations."""
        # Add some violations
        async with db_pool.acquire() as conn:
            for i in range(5):
                await conn.execute("""
                    INSERT INTO violations (camera_id, violation_type, confidence, timestamp)
                    VALUES ($1, $2, 0.9, NOW())
                """, f"stats_test_cam_{i % 2}", ["no_hardhat", "no_vest"][i % 2])
        
        # Get statistics
        response = await http_client.get("/api/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        stats = response.json()
        
        # Should have some violations counted
        total = stats.get("total_violations", stats.get("violations_today", 0))
        assert total >= 5
        
        # Cleanup
        async with db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM violations WHERE camera_id LIKE 'stats_test_cam_%'"
            )


# ============================================================================
# RUN CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
