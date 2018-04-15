# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import re
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('usermodel', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MembershipApplication',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('cell_phone', models.CharField(blank=True, max_length=30, verbose_name=b'Mobile Phone', validators=[django.core.validators.RegexValidator(re.compile(b'^\\+?[\\d ]+$'), b'Enter a valid phone number.', b'invalid')])),
                ('other_phone', models.CharField(blank=True, max_length=30, verbose_name=b'Other Phone', validators=[django.core.validators.RegexValidator(re.compile(b'^\\+?[\\d ]+$'), b'Enter a valid phone number.', b'invalid')])),
                ('prefs_receive_email', models.NullBooleanField(default=None, help_text=b'Receive general emails from the club - news, social events, competition reminders etc.', verbose_name=b'General Email')),
                ('prefs_esra_member', models.NullBooleanField(default=None, help_text=b'Automatically enroll for England Squash membership, which is free as part of your subscription. In answering "Yes" you are giving the club permission to pass on your email address to England Squash.', verbose_name=b'ES Membership')),
                ('prefs_display_contact_details', models.NullBooleanField(default=None, help_text=b'Whether your contact details appear in the membership list on this website, enabling other members to contact you regarding league games etc.', verbose_name=b'Details Visible')),
                ('date_of_birth', models.DateField(help_text=b'Date of birth (only required for age-restricted subscriptions)', null=True, verbose_name=b'DoB', blank=True)),
                ('pro_rata_date', models.DateField(null=True, verbose_name=b'Pro Rata Date', blank=True)),
                ('payment_frequency', models.CharField(max_length=16, verbose_name=b'Payment Freq', choices=[(b'annual', b'Annually'), (b'triannual', b'Tri-annually'), (b'querterly', b'Quarterly'), (b'monthly', b'Monthly')])),
                ('comment', models.TextField(null=True, blank=True)),
                ('username', models.CharField(validators=[django.core.validators.RegexValidator(b'^[\\w.@+-]+$', b'Enter a valid username.', b'invalid')], max_length=30, blank=True, help_text=b'Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.', null=True, verbose_name=b'username')),
                ('first_name', models.CharField(max_length=30, verbose_name=b'first name')),
                ('last_name', models.CharField(max_length=30, verbose_name=b'last name')),
                ('email', models.EmailField(max_length=75, verbose_name=b'email address')),
                ('guid', models.CharField(max_length=36, verbose_name=b'GUID')),
                ('email_verified', models.BooleanField(default=False)),
                ('signed_off', models.BooleanField(default=False, help_text=b'Signed off by the membership secretary - after which the next save will create this member in the database.')),
                ('player', models.ForeignKey(blank=True, to='usermodel.Player', null=True)),
                ('season', models.ForeignKey(to='usermodel.Season')),
                ('subscription_type', models.ForeignKey(to='usermodel.SubscriptionType')),
            ],
            options={
                'verbose_name': 'Membership Application',
            },
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name='player',
            name='date_of_birth',
            field=models.DateField(help_text=b'Date of birth (only required for age-restricted subscriptions)', null=True, verbose_name=b'DoB', blank=True),
        ),
        migrations.AlterField(
            model_name='player',
            name='prefs_display_contact_details',
            field=models.NullBooleanField(default=None, help_text=b'Whether your contact details appear in the membership list on this website, enabling other members to contact you regarding league games etc.', verbose_name=b'Details Visible'),
        ),
        migrations.AlterField(
            model_name='player',
            name='prefs_esra_member',
            field=models.NullBooleanField(default=None, help_text=b'Automatically enroll for England Squash membership, which is free as part of your subscription. In answering "Yes" you are giving the club permission to pass on your email address to England Squash.', verbose_name=b'ES Membership'),
        ),
        migrations.AlterField(
            model_name='player',
            name='prefs_receive_email',
            field=models.NullBooleanField(default=None, help_text=b'Receive general emails from the club - news, social events, competition reminders etc.', verbose_name=b'General Email'),
        ),
    ]
