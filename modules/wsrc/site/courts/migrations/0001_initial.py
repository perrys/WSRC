# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-07-21 23:07
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('usermodel', '0008_auto_20180612_1220'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingOffence',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('offence', models.CharField(choices=[(b'lc', b'Late Cancelation'), (b'ns', b'No Show')], max_length=2)),
                ('entry_id', models.IntegerField()),
                ('start_time', models.DateTimeField()),
                ('duration_mins', models.IntegerField()),
                ('court', models.SmallIntegerField()),
                ('name', models.CharField(max_length=64)),
                ('description', models.CharField(blank=True, max_length=128, null=True)),
                ('owner', models.CharField(max_length=64)),
                ('creation_time', models.DateTimeField()),
                ('cancellation_time', models.DateTimeField(blank=True, null=True)),
                ('rebooked', models.BooleanField(default=False)),
                ('penalty_points', models.SmallIntegerField(verbose_name=b'Points')),
                ('comment', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True, verbose_name=b'Active')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='usermodel.Player')),
            ],
            options={
                'ordering': ['-start_time'],
                'verbose_name': 'Booking Offence',
                'verbose_name_plural': 'Booking Offences',
            },
        ),
        migrations.CreateModel(
            name='BookingSystemEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_time', models.DateTimeField(db_index=True)),
                ('end_time', models.DateTimeField()),
                ('court', models.SmallIntegerField()),
                ('name', models.CharField(max_length=64)),
                ('event_type', models.CharField(choices=[(b'I', b'Member'), (b'E', b'Club')], max_length=1)),
                ('event_id', models.IntegerField(blank=True, null=True)),
                ('description', models.CharField(blank=True, max_length=128, null=True)),
                ('created_time', models.DateTimeField()),
                ('no_show', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='usermodel.Player')),
            ],
            options={
                'verbose_name': 'Booking',
            },
        ),
        migrations.CreateModel(
            name='DayOfWeek',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=3)),
                ('ordinal', models.IntegerField(unique=True)),
            ],
            options={
                'ordering': ['ordinal'],
                'verbose_name_plural': 'DaysOfTheWeek',
            },
        ),
        migrations.CreateModel(
            name='EventFilter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('earliest', models.TimeField()),
                ('latest', models.TimeField()),
                ('notice_period_minutes', models.IntegerField(verbose_name=b'Minimum Notice')),
                ('days', models.ManyToManyField(blank=True, to='courts.DayOfWeek')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='usermodel.Player')),
            ],
            options={
                'verbose_name': 'Cancellation Notifier',
            },
        ),
    ]
