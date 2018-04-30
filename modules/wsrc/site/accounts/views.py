
from functools import partial

from .models import Category, Transaction, Account
from .admin import SUBS_CATEGORY_NAME
from wsrc.site.usermodel.models import Subscription, SubscriptionPayment, Season
from wsrc.utils.rest_framework_utils import LastUpdaterModelSerializer
from wsrc.utils.upload_utils import UploadFileForm, upload_generator

from django import forms
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import render
from django.views.generic.list import ListView
from django.http import HttpResponse

import rest_framework.permissions as rest_permissions
import rest_framework.generics    as rest_generics
from rest_framework import serializers, status
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

import csv
import re

JSON_RENDERER = JSONRenderer()

def is_staff_test(user):
    return user.is_staff

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "account", "date_issued", "date_cleared", "amount", "category", "bank_transaction_category", "bank_number", "bank_memo", "comment"]

class AccountSerializer(serializers.ModelSerializer):
#    transaction_set = serializers.PrimaryKeyRelatedField(many=True, queryset = Transaction.objects.all())
    transaction_set = TransactionSerializer(many=True)
    class Meta:
        model = Account
        depth = 2
        fields = ["name", "sort_code", "acc_number", "transaction_set"]

class AccountListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["name"]

class AccountView(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = Account.objects.all().prefetch_related("transaction_set")
    serializer_class = AccountSerializer

class AccountListView(rest_generics.ListCreateAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountListSerializer
                                                   
class TransactionView(rest_generics.ListAPIView):
    permission_classes = (rest_permissions.IsAuthenticated,)
    serializer_class = TransactionSerializer
    def get_queryset(self):
        account_name = self.kwargs.get('account_name')
        if account_name is None:
            account_id = int(self.kwargs.get('account_id'))
            queryset = Transaction.objects.filter(account__id=account_id) 
        else:
            queryset = Transaction.objects.filter(account__name=account_name) 
        return queryset.select_related()
    def put(self, request, account_id, format="json"):
        # Bulk Upload
        account_id = int(account_id)
        assert(account_id == request.data['account'])
        account = Account.objects.get(pk=int(account_id))
        transaction_data = request.data['transactions']
        categories = dict([(cat.id, cat) for cat in Category.objects.all()])
        subscriptions = dict([(sub.id, sub) for sub in Subscription.objects.exclude(season__has_ended=True)])
        latest_season = Season.latest()
        models = []
        for tran in transaction_data:
            tran['account'] = account
            tran['category'] = categories[int(tran['category'])]
            tran['last_updated_by'] = request.user
            if 'date_cleared' in tran and len(tran['date_cleared']) < 10:
                tran['date_cleared'] = None
            sub_id = tran.pop('subscription', None)
            sub_update = tran.pop('sub_update', False)
            trans_model = Transaction(**tran)
            models.append(partial(Transaction.save, trans_model))
            if sub_id is not None:
                sub_model = subscriptions.get(int(sub_id))
                if sub_model is not None:
                    if sub_update:
                        sub_model = sub_model.clone_to_latest_season(latest_season)
                    def create_and_save(fsubs, ftrans):
                        # need to defer creating this until after the
                        # transaction is saved and hence has an ID
                        payment = SubscriptionPayment(subscription=fsubs, transaction=ftrans)
                        payment.save()
                    models.append(partial(create_and_save, sub_model, trans_model))
        with transaction.atomic():
            for model in models:
                model()
        return Response(status=status.HTTP_201_CREATED)

class CategorySerializer(LastUpdaterModelSerializer):
  last_updater_field = "last_updated_by"
  class Meta:
      model = Category
      exclude = ("last_updated", "last_updated_by",)

class CategoryListView(rest_generics.ListAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()

    def put(self, request, format="json"):
        """Full reset of the category list. Because of the ordering
        parameter, it is not that useful to be able to create a new
        category in isolation, you need to update the old ones at the
        same time"""
        if not request.user.is_authenticated():
            raise PermissionDenied()
        category_data = request.data
        existing_categories = dict([(c.id, c) for c in Category.objects.all()])
        errors = []
        with transaction.atomic():
            for (id, category_model_obj) in existing_categories.iteritems():
                category_model_obj.ordering += 10000
                category_model_obj.save()
            serializers = []
            for datum in category_data:
                id = datum.get("id")
                if id is not None and id in existing_categories:
                    serializer = CategorySerializer(existing_categories[id], data=datum, user=request.user)
                    del existing_categories[id]
                else:
                    serializer = CategorySerializer(data=datum, user=request.user)
                serializers.append(serializer)
            for serializer in serializers:
                if not serializer.is_valid():
                    errors.append(serializer.errors)
                else:
                    serializer.save()
            for (id, category_model_obj) in existing_categories.iteritems():
                category_model_obj.delete() # may throw if still linked to existing transactions
        if len(errors) > 0:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        categories = Category.objects.all();
        serialiser = CategorySerializer(categories, many=True)
        return Response(serialiser.data, status=status.HTTP_201_CREATED)

class CategoryDetailView(rest_generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()

@user_passes_test(is_staff_test)
def accounts_view(request, account_name=None):
    data = None

    accounts = Account.objects.all().order_by('name').prefetch_related("transaction_set")
    categories = Category.objects.all().order_by('description').select_related();
    subscriptions = Subscription.objects.filter(season__has_ended=False).select_related()
    subs_category = [c for c in categories if c.name == SUBS_CATEGORY_NAME][0]
    uploaded_account = None
    
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            reader = csv.DictReader(upload_generator(request.FILES['file']))
            data = [row for row in reader]
            if len(data) == 0:
                raise SuspiciousOperation("empty dataset uploaded")                
            for row in data:
                if uploaded_account is None:
                    uploaded_account = row["Account"]
                elif uploaded_account != row["Account"]:
                    raise SuspiciousOperation("mixed account data uploaded")
            sort_code, acc_number = uploaded_account.split()            
            uploaded_account = accounts.get(sort_code=sort_code, acc_number=acc_number)
            transaction_set = [t for t in uploaded_account.transaction_set.all()]
            regexes = [(c.id, re.compile(c.regex, re.IGNORECASE)) for c in categories if c.regex != "__missing__"]
            
            def isduplicate(row):
                if "Amount" not in row:
                    return False
                comment = row.get("Comment")
                bank_memo = row.get("Memo")
                datestr = row["Date"]
                datestr = datestr[6:10] + "-" + datestr[3:5] + "-" + datestr[0:2]
                matches = [t for t in transaction_set if t.date_issued.isoformat() == datestr]
                matches = [t for t in matches if t.amount == float(row["Amount"])]
                if comment is not None and len(comment) > 0:
                    matches = [t for t in matches if t.comment == comment]
                if bank_memo is not None and len(bank_memo) > 0:
                    matches = [t for t in matches if t.bank_memo == bank_memo]
                if len(matches) == 1:
                    return matches[0].category_id
                return None

            def get_category(row):
                memo = row["Memo"]
                if not memo:
                    return None
                for cat_id, regex in regexes:
                    result = regex.search(memo)
                    if result:
                        return cat_id
                # We're going to assume that any payment which is a
                # standing order paid near the start of the month is
                # also a subscription payment:
                day_of_month = int(row["Date"][0:2])
                if float(row["Amount"]) > 0 and memo.endswith("STO") and (day_of_month <=3 or day_of_month >= 27):
                    return subs_category.id
                return None

            def get_subscription(row, cat_id):
                class Transaction:
                    def __init__(self, row, cat_id):
                        self.bank_memo = row.get("Memo")
                        self.comment = ''
                        self.category_id = cat_id
                tran = Transaction(row, cat_id)
                for sub in subscriptions:
                    if sub.match_transaction(tran, subs_category, persist=False):
                        return sub
                return None
                
            for row in data:
                cat_id = isduplicate(row)
                if cat_id is not None:
                    row["x_duplicate"] = True
                    row["category_id"] = cat_id
                else:
                    cat_id = get_category(row)
                    row["category_id"] = cat_id or ''
                row["subscription"] = get_subscription(row, cat_id)

    else:
        form = UploadFileForm()

    categories_serialiser = CategorySerializer(categories, many=True)
    categories_data = JSON_RENDERER.render(categories_serialiser.data)
    account_data = {}
    for account in accounts:
        account_serializer = AccountSerializer(account)
        account_data[account.id] = JSON_RENDERER.render(account_serializer.data)

    return render(request, 'accounts.html', {
        'form': form,
        'csv_data': data,
        'categories': categories,
        'categories_data': categories_data,
        'accounts': accounts,
        'account_data': account_data,
        'uploaded_acc': uploaded_account,
        'subscriptions': subscriptions,
        'subs_category': subs_category,
        'latest_season': Season.latest()
    })        

from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def transaction_csv_view(request, account_name):
    account = Account.objects.get(name__iexact=account_name)
    queryset = Transaction.objects.filter(account__name=account_name) 
    start_date = request.GET.get("start_date")
    if start_date is not None:
        queryset = queryset.filter(date_issued__gte = start_date)
    end_date = request.GET.get("end_date")
    if end_date is not None:
        queryset = queryset.filter(date_issued__lt = end_date)
    queryset = queryset.order_by("-date_issued")
    response = HttpResponse(content_type='text/csv')
    filename = "WSRC_%s.csv" % (account.name)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    csvwriter = csv.writer(response)
    fields = ['date_issued', 'date_cleared', 'amount', 'bank_transaction_category', 'bank_number', 'bank_memo', 'category', 'comment']
    csvwriter.writerow(fields)
    for row in queryset:
        print row.date_cleared
        data = [getattr(row, field) for field in fields]
        csvwriter.writerow(data)
    return response
            
        
