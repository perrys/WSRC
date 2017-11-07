
from .models import Category, Transaction, Account
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
        fields = ["name", "transaction_set"]

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
            accounts = Account.objects.filter(pk=request.POST['account']).prefetch_related('transaction_set')
            if accounts.count() != 1:
                raise SuspiciousOperation()
            account = accounts[0]
            transaction_set = [t for t in account.transaction_set.all()]
            def isduplicate(row):
                if account is None:
                    return False
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
        
            reader = csv.DictReader(upload_generator(request.FILES['file']))
            data = [preprocess_row(row) for row in reader]
            for row in data:
                cat_id = isduplicate(row)
                if cat_id is not None:
                    row["x_duplicate"] = True
                    row["category_id"] = cat_id


    else:
        form = UploadFileForm()

    categories = Category.objects.all().order_by('description').select_related();
    categories_serialiser = CategorySerializer(categories, many=True)
    categories_data = JSON_RENDERER.render(categories_serialiser.data)
    accounts = Account.objects.all().order_by('name').prefetch_related("transaction_set")
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
            
        
