# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-09-13 22:57
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('email', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='virtualalias',
            options={'verbose_name': 'Virtual Alias', 'verbose_name_plural': 'Virtual Aliases'},
        ),
        migrations.AlterModelOptions(
            name='virtualdomain',
            options={'verbose_name': 'Virtual Domain', 'verbose_name_plural': 'Virtual Domains'},
        ),
        migrations.AlterModelOptions(
            name='virtualuser',
            options={'verbose_name': 'Virtual User', 'verbose_name_plural': 'Virtual Users'},
        ),
        migrations.AddField(
            model_name='virtualalias',
            name='use_user_email',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterUniqueTogether(
            name='virtualalias',
            unique_together=set([('from_username', 'from_domain', 'to')]),
        ),
        migrations.AlterUniqueTogether(
            name='virtualuser',
            unique_together=set([('user', 'domain')]),
        ),
    ]
