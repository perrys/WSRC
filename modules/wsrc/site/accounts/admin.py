from django.contrib import admin
from django.db.models import Q

from .models import Account, Category, Transaction
from wsrc.site.usermodel.models import SubscriptionPayment, Subscription, Season
from wsrc.utils.form_utils import SelectRelatedForeignFieldMixin, SelectRelatedQuerysetMixin, PrefetchRelatedQuerysetMixin

SUBS_CATEGORY_NAME = "subscriptions"

class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "ordering", "description", "regex", "is_reconciling",)
    list_editable = ("name", "ordering", "description", "regex", "is_reconciling",)

class SubscriptionPaymentInline(SelectRelatedForeignFieldMixin, SelectRelatedQuerysetMixin, admin.StackedInline):
    model = SubscriptionPayment
    max_num = 1
    can_delete = True

def assign_subs_payment(modeladmin, request, transactions_queryset):  
    import re
    latest_season = Season.latest()
    subscriptions = Subscription.objects.filter(season=latest_season).select_related("player", "season")
    existing_payments = SubscriptionPayment.objects.all()
    existing_payment_ids = [p.transaction_id for p in existing_payments]
    subs_category = Category.objects.get(name=SUBS_CATEGORY_NAME)
    compare_set = set()
    for trans in transactions_queryset.filter(Q(category__isnull=True) | Q(category__name=SUBS_CATEGORY_NAME)):
        if trans.id in existing_payment_ids:
            continue # transaction is already a subs payment
        for sub in subscriptions:
            sub.match_transaction(trans, subs_category)
assign_subs_payment.short_description="Assign Subs Payment"
    
class TransactionAdmin(PrefetchRelatedQuerysetMixin, admin.ModelAdmin):
    inlines = (SubscriptionPaymentInline,)
    list_display = ("date_issued", "date_cleared", "account", "bank_number", "amount", "bank_memo", "category", "subscription", "comment")
    list_editable = ("comment",)
    list_filter = ('account', 'category')
    list_per_page = 100
    list_select_related = True
    prefetch_related_fields = ('subs_payments',)
    search_fields = ('bank_memo', 'comment')
    actions=(assign_subs_payment,)
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
