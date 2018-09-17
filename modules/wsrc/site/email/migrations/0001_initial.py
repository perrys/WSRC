# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-09-12 13:12
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import os

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VirtualAlias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_username', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='VirtualDomain',
            fields=[
                ('name', models.CharField(max_length=255, primary_key=True, serialize=False)),
            ],
        ),
        migrations.CreateModel(
            name='VirtualUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='email.VirtualDomain')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='virtualalias',
            name='from_domain',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='email.VirtualDomain'),
        ),
        migrations.AddField(
            model_name='virtualalias',
            name='to',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='email.VirtualUser'),
        ),
        migrations.RunSQL(
            "CREATE USER IF NOT EXISTS 'mailuser'@'%' IDENTIFIED BY '{0}'".format(os.getenv('DB_PASSWORD'))
        ),
        migrations.RunSQL(
            "GRANT SELECT ON email_virtualdomain TO 'mailuser'"
        ),
        migrations.RunSQL(
            "GRANT SELECT ON email_virtualuser TO 'mailuser'"
        ),
        migrations.RunSQL(
            "GRANT SELECT ON email_virtualalias TO 'mailuser'"
        ),
        migrations.RunSQL(
            "GRANT SELECT ON auth_user TO 'mailuser'"
        ),
    ]
