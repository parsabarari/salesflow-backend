from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "is_email_verified", "created_at")
    list_filter = ("is_email_verified",)
    search_fields = ("email",)
    ordering = ("email",)
    readonly_fields = ("created_at",)
