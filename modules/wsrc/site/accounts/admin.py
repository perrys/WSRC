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
        print trans
        if trans.id in existing_payment_ids:
            continue # transaction is already a subs payment
        for sub in subscriptions:
            print sub
            def matches(regex):
                return regex is not None and (regex.search(trans.bank_memo) or regex.search(trans.comment))
            def create_payment():
                payment = SubscriptionPayment(subscription=sub, transaction=trans)
                payment.save()
            regex = getattr(sub, "regex", None)
            if regex is None:
                regex_expr = sub.player.subscription_regex
                if regex_expr is not None:
                    sub.regex = regex = re.compile(regex_expr, re.IGNORECASE)
            if matches(regex):
                if trans.category is None:
                    trans.category = subs_category
                    trans.save()
                create_payment()
                continue
            # couldn't match using any player's regexp. Try their names, but
            # only for transactions already categorized as subscriptions:
            if trans.category.name == SUBS_CATEGORY_NAME:
                regex = re.compile(sub.player.user.get_full_name(), re.IGNORECASE)
                if regex.search(trans.bank_memo) or regex.search(trans.comment):
                    create_payment()
                    continue
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
