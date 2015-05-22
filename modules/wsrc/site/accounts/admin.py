from django.contrib import admin

from .models import Account, Category, Transaction

class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "ordering", "description", "regex", "is_reconciling",)
    list_editable = ("name", "ordering", "description", "regex", "is_reconciling",)

class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date_issued", "date_cleared", "account", "bank_number", "amount", "bank_memo", "comment", "category")
    list_editable = ("date_cleared", "account", "comment", "category",)
    list_filter = ('account', 'category')

admin.site.register(Account)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Transaction, TransactionAdmin)
