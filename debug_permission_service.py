import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.core.database import get_async_session_local
from app.services.auth.permission_request_service import PermissionRequestService


async def main():
    session_factory = get_async_session_local()
    async with session_factory() as session:
        service = PermissionRequestService(session)
        result = await service.get_my_requests("77107791")
        print("Total:", result["total"])
        print("Requests:")
        for item in result["requests"]:
            print(item)


if __name__ == "__main__":
    asyncio.run(main())
