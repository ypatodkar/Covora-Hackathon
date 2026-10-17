from fastapi import APIRouter, Depends
from sqlalchemy import text

from covora.api.deps import Services, get_services

router = APIRouter()


@router.get("/health")
async def health(services: Services = Depends(get_services)) -> dict:
    try:
        async with services.sessionmaker() as session:
            await session.execute(text("select 1"))
        database = True
    except Exception:  # noqa: BLE001 - health reports, never raises
        database = False
    checks = {
        "database": database,
        "nvidia_key": services.settings.nvidia_api_key is not None,
        "youcom_key": services.settings.ydc_api_key is not None,
    }
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
