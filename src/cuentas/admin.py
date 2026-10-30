from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Sede, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("EcoMetrics", {"fields": ("rol", "sede")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("EcoMetrics", {"fields": ("rol", "sede")}),)


admin.site.register(Sede)
