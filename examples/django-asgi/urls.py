"""URL configuration."""
from __future__ import annotations

from django.http import JsonResponse
from django.urls import path


async def api_health(request) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health", api_health),
]
