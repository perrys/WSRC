# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-07-30 18:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courts', '0011_cascade_player_eventfilter'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingsystemevent',
            name='opponent',
            field=models.CharField(max_length=64, null=True),
        ),
    ]