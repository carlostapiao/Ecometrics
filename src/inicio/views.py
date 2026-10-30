from django.db import OperationalError, connection
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_safe


@require_safe
def inicio(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect("resumen" if request.user.rol == "gerente" else "registrar")


@require_safe
def salud(request):
    return JsonResponse({"estado": "ok"})


@require_safe
def disponibilidad(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError:
        return JsonResponse({"estado": "no_disponible"}, status=503)
    return JsonResponse({"estado": "ok"})
