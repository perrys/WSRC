# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-06-26 18:14
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0003_auto_20180626_0934'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='competitiongroup',
            name='comp_type',
        ),
        migrations.AlterField(
            model_name='competitiongroup',
            name='competition_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='competitions.CompetitionType'),
        ),
    ]
