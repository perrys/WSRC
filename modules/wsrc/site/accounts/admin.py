# This file is part of WSRC.
#
# WSRC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# WSRC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WSRC.  If not, see <http://www.gnu.org/licenses/>.

"Admin for the accounts models"

from django.contrib import admin
from django.db.models import Q

from .models import Account, Category, Transaction
from wsrc.site.usermodel.models import SubscriptionPayment, Subscription, Season
from wsrc.utils.form_utils import SelectRelatedForeignFieldMixin, \
    SelectRelatedQuerysetMixin, PrefetchRelatedQuerysetMixin
from wsrc.utils.admin_utils import CSVModelAdmin

SUBS_CATEGORY_NAME = "subscriptions"

class CategoryAdmin(CSVModelAdmin):
    "Simple admin for accounts categories"
    list_display = ("id", "name", "ordering", "description", "regex", "is_reconciling",)
    list_editable = ("name", "ordering", "description", "regex", "is_reconciling",)

class SubscriptionPaymentInline(SelectRelatedForeignFieldMixin, SelectRelatedQuerysetMixin,
                                admin.StackedInline):
    """Display a single inline for each transaction allowing it to be
       associated with a subscription"""
    model = SubscriptionPayment
    max_num = 1
    can_delete = True

def assign_subs_payment(modeladmin, request, transactions_queryset):
    """Function to run as an action on transactions - heuristically guess
       if it is a subs payment and automatically assign one"""
    import re
    latest_season = Season.latest()
    subscriptions = Subscription.objects.filter(season=latest_season) \
                                        .select_related("player", "season")
    existing_payments = SubscriptionPayment.objects.all()
    existing_payment_ids = [p.transaction_id for p in existing_payments]
    subs_category = Category.objects.get(name=SUBS_CATEGORY_NAME)
    for trans in transactions_queryset.filter(Q(category__isnull=True) |
                                              Q(category__name=SUBS_CATEGORY_NAME)):
        if trans.id in existing_payment_ids:
            continue # transaction is already a subs payment
        for sub in subscriptions:
            sub.match_transaction(trans, subs_category)
assign_subs_payment.short_description = "Assign Subs Payment"

class TransactionAdmin(PrefetchRelatedQuerysetMixin, CSVModelAdmin):
    "Admin for account transactions"
    inlines = (SubscriptionPaymentInline,)
    list_display = ("date_issued", "date_cleared", "account", "bank_number", "amount",
                    "bank_memo", "category", "subscription", "comment")
    list_editable = ("comment",)
    list_filter = ('account', 'category')
    list_per_page = 300
    list_select_related = True
    prefetch_related_fields = ('subs_payments',)
    search_fields = ('bank_memo', 'comment')
    actions = (assign_subs_payment,)
    def subscription(self, obj):
        """Accessor for a possible subscription associated with this
        transaction, for use by the display list."""
        subs_payment = obj.subs_payments
        if subs_payment:
            cache = getattr(self, 'subscription_cache', None)
            if cache is None:
                cache = dict([(sub.pk, sub) for sub in Subscription.objects.all()])
                self.subscription_cache = cache
            return unicode(cache.get(subs_payment.subscription_id))
        return None

admin.site.register(Account)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Transaction, TransactionAdmin)
