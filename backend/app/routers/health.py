"""
Health check router for liveness and readiness probes.
"""
from fastapi import APIRouter, status

from app.database.connections import get_mongo_client, get_redis_client

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
)
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 if the API is running.
    """
    return {"status": "healthy"}


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness check with dependencies",
)
async def readiness_check():
    """
    Readiness check that verifies database connections.
    Returns 200 if MongoDB and Redis are accessible.
    """
    checks = {
        "api": "healthy",
        "mongodb": "unknown",
        "redis": "unknown",
    }
    
    # Check MongoDB
    try:
        client = await get_mongo_client()
        await client.admin.command("ping")
        checks["mongodb"] = "healthy"
    except Exception as e:
        checks["mongodb"] = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        redis = await get_redis_client()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
    
    # Overall status
    all_healthy = all(v == "healthy" for v in checks.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }
