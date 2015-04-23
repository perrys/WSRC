
from .models import Category, Transaction, Account
from wsrc.utils.rest_framework_utils import LastUpdaterModelSerializer

from django import forms
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import render
from django.views.generic.list import ListView

import rest_framework.permissions as rest_permissions
import rest_framework.generics    as rest_generics
from rest_framework import serializers, status
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

import csv

JSON_RENDERER = JSONRenderer()

class AccountSerializer(serializers.ModelSerializer):
    transaction_set = serializers.PrimaryKeyRelatedField(many=True, queryset = Transaction.objects.all())
    class Meta:
        model = Account
        depth = 1
        fields = ["name", "transaction_set"]

class AccountListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["name"]

class AccountView(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

class AccountListView(rest_generics.ListCreateAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountListSerializer
                                                   
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "account", "date_issued", "date_cleared", "amount", "category", "bank_transaction_category", "bank_number", "bank_memo", "comment"]

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
        return queryset
    def put(self, request, account_id, format="json"):
        # Bulk Upload
        account_id = int(account_id)
        assert(account_id == request.DATA['account'])
        account = Account.objects.get(pk=int(account_id))
        transaction_data = request.DATA['transactions']
        categories = dict([(cat.id, cat) for cat in Category.objects.all()])
        models = []
        for tran in transaction_data:
            tran['account'] = account
            tran['category'] = categories[int(tran['category'])]
            tran['last_updated_by'] = request.user
            if 'date_cleared' in tran and len(tran['date_cleared']) < 10:
                tran['date_cleared'] = None
            models.append(Transaction(**tran))
        with transaction.atomic():
            for model in models:
                model.save()
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
        category_data = request.DATA
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

def gen(upload):
    last_line = ""
    for chunk in upload.chunks():
        lines = (last_line + chunk).split("\n")
        for i, line in enumerate(lines):
            if i < (len(lines) -1):
                yield line
            else:
                last_line = line
    if len(last_line) > 0:
        yield last_line

class UploadFileForm(forms.Form):
    file = forms.FileField()

def accounts_view(request, account_name=None):
    data = None
    def preprocess_row(row):
        # Convert old spreadsheet columns to columns to format of bank statements
        def convert(old_name, new_name, multiplier=None):
            if old_name in row:
                val = row[old_name].decode("ascii", "ignore").replace(",", "")
                if len(val) > 0 :
                  if multiplier is not None:
                    val = float(val) * multiplier
                  row[new_name] = val
        for cvt in [("Outgoing", "Amount", -1.0), ("Income", "Amount", 1.0), ("Transfers", "Amount", -1.0), ("Item", "Comment"), ("Chq No", "Number")]:
            convert(*cvt)
        return row

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            account = Account.objects.get(pk=request.POST['account'])
            def isduplicate(row):
                if account is None:
                    return False
                if "Amount" not in row:
                    return False
                datestr = row["Date"]
                datestr = datestr[6:10] + "-" + datestr[3:5] + "-" + datestr[0:2]
                matches = account.transaction_set.filter(date_issued = datestr)
                matches = matches.filter(amount = float(row["Amount"]))
                return len(matches) == 1
        
            reader = csv.DictReader(gen(request.FILES['file']))
            data = [preprocess_row(row) for row in reader]
            for row in data:
                row["x_duplicate"] = isduplicate(row)


    else:
        form = UploadFileForm()

    categories = Category.objects.all().order_by('description');
    categories_serialiser = CategorySerializer(categories, many=True)
    categories_data = JSON_RENDERER.render(categories_serialiser.data)
    accounts = Account.objects.all().order_by('name')
    account_data = {}
    for account in accounts:
        transactions = account.transaction_set.all()
        transaction_serializer = TransactionSerializer(transactions, many=True)
        transaction_data = JSON_RENDERER.render(transaction_serializer.data)
        account_data[account.id] = transaction_data

    return render(request, 'csv_upload.html', {
        'form': form,
        'csv_data': data,
        'categories': categories,
        'categories_data': categories_data,
        'accounts': accounts,
        'account_data': account_data,
    })        
        
        
