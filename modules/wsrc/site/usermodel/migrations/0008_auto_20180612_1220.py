# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-06-12 11:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usermodel', '0007_auto_20180604_1823'),
    ]

    operations = [
        migrations.AddField(
            model_name='membershipapplication',
            name='gender',
            field=models.CharField(blank=True, choices=[(None, b'Unspecified'), (b'Male', b'Male'), (b'Female', b'Female')], default=None, max_length=16, null=True, verbose_name=b'Gender'),
        ),
        migrations.AddField(
            model_name='player',
            name='gender',
            field=models.CharField(blank=True, choices=[(None, b'Unspecified'), (b'Male', b'Male'), (b'Female', b'Female')], default=None, max_length=16, null=True, verbose_name=b'Gender'),
        ),
    ]
