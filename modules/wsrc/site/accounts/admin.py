from django.contrib import admin

from .models import Account, Category, Transaction
from wsrc.site.usermodel.models import SubscriptionPayment, Subscription
from wsrc.utils.form_utils import SelectRelatedForeignFieldMixin, SelectRelatedQuerysetMixin, PrefetchRelatedQuerysetMixin

class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "ordering", "description", "regex", "is_reconciling",)
    list_editable = ("name", "ordering", "description", "regex", "is_reconciling",)

class SubscriptionPaymentInline(SelectRelatedForeignFieldMixin, SelectRelatedQuerysetMixin, admin.StackedInline):
    model = SubscriptionPayment
    max_num = 1
    can_delete = True
    
class TransactionAdmin(PrefetchRelatedQuerysetMixin, admin.ModelAdmin):
    inlines = (SubscriptionPaymentInline,)
    list_display = ("date_issued", "date_cleared", "account", "bank_number", "amount", "bank_memo", "category", "subscription", "comment")
    list_editable = ("comment",)
    list_filter = ('account', 'category')
    list_per_page = 200
    list_select_related = True
    prefetch_related_fields = ('subs_payments',)
    search_fields = ('bank_memo', 'comment')
    def subscription(self, obj):
        subs_payments = obj.subs_payments
        for sp in subs_payments.all():
            cache = getattr(self, 'subscription_cache', None)
            if cache is None:
                self.subscription_cache = cache = dict([(sub.pk, sub) for sub in Subscription.objects.all()])
            return unicode(cache.get(sp.subscription_id))
        return None

admin.site.register(Account)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Transaction, TransactionAdmin)
