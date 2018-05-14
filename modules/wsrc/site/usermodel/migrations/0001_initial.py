# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import re
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DoorCardEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('event', models.CharField(db_index=True, max_length=128, verbose_name=b'Event Type', blank=True)),
                ('timestamp', models.DateTimeField(help_text=b'Timestamp from the cardreader', db_index=True)),
                ('received_time', models.DateTimeField(help_text=b'Server timestamp', auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Door Card Event',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DoorCardLease',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_issued', models.DateField(default=datetime.date.today, verbose_name=b'Issue Date', db_index=True)),
                ('date_returned', models.DateField(db_index=True, null=True, verbose_name=b'Return Date', blank=True)),
            ],
            options={
                'ordering': ['player__user__last_name', 'player__user__first_name'],
                'verbose_name': 'Door Card Lease Period',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DoorEntryCard',
            fields=[
                ('cardnumber', models.CharField(max_length=8, serialize=False, verbose_name=b'Card #', primary_key=True, validators=[django.core.validators.RegexValidator(b'^\\d{8}$', b'Enter an eight-digit card number.', b'invalid_id')])),
                ('is_registered', models.BooleanField(default=True, help_text=b'Whether card is currently registred with the card reader', verbose_name=b'Card Valid')),
                ('comment', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ['cardnumber'],
                'verbose_name': 'Door Entry Card',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('cell_phone', models.CharField(blank=True, max_length=30, verbose_name=b'Mobile Phone', validators=[django.core.validators.RegexValidator(re.compile(b'^\\+?[\\d ]+$'), b'Enter a valid phone number.', b'invalid')])),
                ('other_phone', models.CharField(blank=True, max_length=30, verbose_name=b'Other Phone', validators=[django.core.validators.RegexValidator(re.compile(b'^\\+?[\\d ]+$'), b'Enter a valid phone number.', b'invalid')])),
                ('short_name', models.CharField(max_length=32, verbose_name=b'Short Name', blank=True)),
                ('wsrc_id', models.IntegerField(help_text=b'Index in the membership spreadsheet', null=True, verbose_name=b'WSRC ID', db_index=True, blank=True)),
                ('booking_system_id', models.IntegerField(help_text=b'ID in the booking system', null=True, verbose_name=b'Booking Site ID', db_index=True, blank=True)),
                ('squashlevels_id', models.IntegerField(help_text=b'ID on the SquashLevels website', null=True, verbose_name=b'SquashLevels ID', db_index=True, blank=True)),
                ('england_squash_id', models.CharField(help_text=b'England Squash Membership Number', max_length=16, null=True, verbose_name=b'ES Membership #', blank=True)),
                ('prefs_receive_email', models.NullBooleanField(default=True, help_text=b'Receive general emails from the club - news, social events, competition reminders etc.', verbose_name=b'General Email')),
                ('prefs_esra_member', models.NullBooleanField(default=True, help_text=b'Automatically enroll for England Squash membership, which is free as part of your subscription. In answering "Yes" you are giving the club permission to pass on your email address to England Squash.', verbose_name=b'ES Membership')),
                ('prefs_display_contact_details', models.NullBooleanField(default=True, help_text=b'Whether your contact details appear in the membership list on this website, enabling other members to contact you regarding league games etc.', verbose_name=b'Details Visible')),
                ('subscription_regex', models.CharField(max_length=256, null=True, verbose_name=b'Regexp for subscription transactions', blank=True)),
                ('date_of_birth', models.DateField(null=True, verbose_name=b'DoB', blank=True)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['user__last_name', 'user__first_name'],
                'verbose_name': 'Member',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Season',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start_date', models.DateField(unique=True, db_index=True)),
                ('end_date', models.DateField(unique=True, db_index=True)),
                ('has_ended', models.BooleanField(default=False, help_text=b'Indicates no longer relvant for input forms', db_index=True, verbose_name=b'Has Ended')),
            ],
            options={
                'ordering': ['start_date'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('pro_rata_date', models.DateField(null=True, verbose_name=b'Pro Rata Date', blank=True)),
                ('payment_frequency', models.CharField(max_length=16, verbose_name=b'Payment Freq', choices=[(b'annual', b'Annually'), (b'triannual', b'Tri-annually'), (b'querterly', b'Quarterly'), (b'monthly', b'Monthly')])),
                ('signed_off', models.BooleanField(default=False, verbose_name=b'Signoff')),
                ('comment', models.TextField(null=True, blank=True)),
                ('player', models.ForeignKey(to='usermodel.Player', on_delete=models.CASCADE)),
                ('season', models.ForeignKey(to='usermodel.Season', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['-season__start_date', 'player__user__last_name', 'player__user__first_name'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SubscriptionCost',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('amount', models.FloatField(verbose_name='Cost (\xa3)')),
                ('joining_fee', models.FloatField(default=0, verbose_name='Joining Fee (\xa3)')),
                ('season', models.ForeignKey(related_name=b'costs', to='usermodel.Season', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['-season', '-amount'],
                'verbose_name': 'Subscription Cost',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SubscriptionPayment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('subscription', models.ForeignKey(related_name=b'payments', to='usermodel.Subscription', on_delete=models.CASCADE)),
                ('transaction', models.ForeignKey(related_name=b'subs_payments', to='accounts.Transaction', unique=True, on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SubscriptionType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('short_code', models.CharField(max_length=16)),
                ('name', models.CharField(max_length=32)),
                ('is_default', models.BooleanField(default=False, help_text=b'Please ensure only one subscription type is set as default')),
                ('max_age_years', models.IntegerField(null=True, blank=True)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Subscription Type',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='subscriptioncost',
            name='subscription_type',
            field=models.ForeignKey(to='usermodel.SubscriptionType', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='subscription',
            name='subscription_type',
            field=models.ForeignKey(to='usermodel.SubscriptionType', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='doorcardlease',
            name='card',
            field=models.ForeignKey(to='usermodel.DoorEntryCard', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='doorcardlease',
            name='player',
            field=models.ForeignKey(to='usermodel.Player', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='doorcardevent',
            name='card',
            field=models.ForeignKey(blank=True, to='usermodel.DoorEntryCard', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
