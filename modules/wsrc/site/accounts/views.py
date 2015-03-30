
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
        fields = ["account", "date", "amount", "category", "bank_transaction_category", "bank_number", "bank_memo", "comment"]

class TransactionView(rest_generics.ListCreateAPIView):
    permission_classes = (rest_permissions.IsAuthenticated,)
    serializer_class = TransactionSerializer
    def get_queryset(self):
        account_name = self.kwargs['account_name']
        queryset = Transaction.objects.filter(account__name=account_name) 

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
        category in isolation, and it is often necessary to recreate
        the list from scratch"""
        if not request.user.is_authenticated():
            raise PermissionDenied()
        category_data = request.DATA
        serializers = []
        for datum in category_data:
            serializer = CategorySerializer(data=datum, user=request.user)
            serializers.append(serializer)
        errors = []
        with transaction.atomic():
            Category.objects.all().delete() # have to delete before validating or unique ordering fails
            for serializer in serializers:
                if not serializer.is_valid():
                    errors.push(serializer.errors)
                else:
                    serializer.save()
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

def csv_upload(request):
    data = None
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            reader = csv.DictReader(gen(request.FILES['file']))
            data = [row for row in reader]
    else:
        form = UploadFileForm()

    categories = Category.objects.all();
    serialiser = CategorySerializer(categories, many=True)
    categories_data = JSON_RENDERER.render(serialiser.data)

    return render(request, 'csv_upload.html', {
        'form': form,
        'csv_data': data,
        'categories': categories,
        'categories_data': categories_data,
    })        
        
        
