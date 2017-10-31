from django.contrib import admin

from .models import Account, Category, Transaction

class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "ordering", "description", "regex", "is_reconciling",)
    list_editable = ("name", "ordering", "description", "regex", "is_reconciling",)

class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date_issued", "date_cleared", "account", "bank_number", "amount", "bank_memo", "comment", "category")
#    list_editable = ("date_cleared", "account", "comment", "category",)
    list_filter = ('account', 'category')
    def get_queryset(self, request):
        qs = super(TransactionAdmin, self).get_queryset(request)
        qs = qs.select_related('category', 'account')
        return qs

admin.site.register(Account)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Transaction, TransactionAdmin)
