from django.contrib import admin

from .models import Account, Category, Transaction

class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "regex")
    list_editable = ("name", "description", "regex",)

class TransactionAdmin(admin.ModelAdmin):
    list_display = ("account", "date_issued", "date_cleared", "amount", "bank_memo", "comment", "category")
    list_editable = ("date_cleared", "comment", "category",)

admin.site.register(Account)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Transaction, TransactionAdmin)
