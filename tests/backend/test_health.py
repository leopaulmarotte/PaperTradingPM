"""
Tests for health check endpoints.

These tests verify:
- Basic health endpoint returns 200
- Readiness check reports database connection status
- Health degrades gracefully when services are down
"""

import pytest
from unittest.mock import AsyncMock, patch


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_endpoint_returns_200_when_api_running(self, client):
        """Basic health check should return 200 if API is up."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestReadinessEndpoint:
    """Tests for GET /health/ready endpoint."""

    def test_readiness_returns_200_when_all_services_healthy(
        self, client, mock_async_mongo_client, mock_async_redis
    ):
        """Readiness check should return 200 when all dependencies are up."""
        with patch("app.routers.health.get_mongo_client") as mock_mongo, \
             patch("app.routers.health.get_redis_client") as mock_redis:
            
            # Mock successful connections
            mock_mongo_client = AsyncMock()
            mock_mongo_client.admin.command = AsyncMock(return_value={"ok": 1})
            mock_mongo.return_value = mock_mongo_client
            
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock(return_value=True)
            mock_redis.return_value = mock_redis_client
            
            response = client.get("/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["checks"]["mongodb"] == "healthy"
            assert data["checks"]["redis"] == "healthy"

    def test_readiness_reports_mongodb_unhealthy_when_connection_fails(self, client):
        """Readiness should report MongoDB unhealthy when it fails."""
        with patch("app.routers.health.get_mongo_client") as mock_mongo, \
             patch("app.routers.health.get_redis_client") as mock_redis:
            
            # MongoDB fails
            mock_mongo.side_effect = Exception("Connection refused")
            
            # Redis succeeds
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock(return_value=True)
            mock_redis.return_value = mock_redis_client
            
            response = client.get("/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert "unhealthy" in data["checks"]["mongodb"]

    def test_readiness_reports_redis_unhealthy_when_connection_fails(self, client):
        """Readiness should report Redis unhealthy when it fails."""
        with patch("app.routers.health.get_mongo_client") as mock_mongo, \
             patch("app.routers.health.get_redis_client") as mock_redis:
            
            # MongoDB succeeds
            mock_mongo_client = AsyncMock()
            mock_mongo_client.admin.command = AsyncMock(return_value={"ok": 1})
            mock_mongo.return_value = mock_mongo_client
            
            # Redis fails
            mock_redis.side_effect = Exception("Connection refused")
            
            response = client.get("/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert "unhealthy" in data["checks"]["redis"]

    def test_readiness_returns_degraded_when_all_services_down(self, client):
        """Readiness should return degraded when all services fail."""
        with patch("app.routers.health.get_mongo_client") as mock_mongo, \
             patch("app.routers.health.get_redis_client") as mock_redis:
            
            mock_mongo.side_effect = Exception("MongoDB down")
            mock_redis.side_effect = Exception("Redis down")
            
            response = client.get("/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert "unhealthy" in data["checks"]["mongodb"]
            assert "unhealthy" in data["checks"]["redis"]

    def test_readiness_response_includes_all_check_keys(self, client):
        """Readiness response should include all dependency checks."""
        with patch("app.routers.health.get_mongo_client") as mock_mongo, \
             patch("app.routers.health.get_redis_client") as mock_redis:
            
            mock_mongo.side_effect = Exception("test")
            mock_redis.side_effect = Exception("test")
            
            response = client.get("/health/ready")
            
            data = response.json()
            assert "checks" in data
            assert "api" in data["checks"]
            assert "mongodb" in data["checks"]
            assert "redis" in data["checks"]
