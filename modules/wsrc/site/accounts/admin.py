from django.contrib import admin

from .models import Category

class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "regex")
    list_editable = ("name", "description", "regex",)

admin.site.register(Category, CategoryAdmin)
