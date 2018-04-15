# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import wsrc.site.usermodel.models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('usermodel', '0002_auto_20180328_2346'),
    ]

    operations = [
        migrations.AlterField(
            model_name='membershipapplication',
            name='guid',
            field=models.CharField(default=uuid.uuid1, max_length=36, verbose_name=b'GUID'),
        ),
        migrations.AlterField(
            model_name='membershipapplication',
            name='payment_frequency',
            field=models.CharField(default=b'annual', max_length=16, verbose_name=b'Payment Freq', choices=[(b'annual', b'Annually'), (b'triannual', b'Tri-annually'), (b'querterly', b'Quarterly'), (b'monthly', b'Monthly')]),
        ),
        migrations.AlterField(
            model_name='membershipapplication',
            name='prefs_esra_member',
            field=models.NullBooleanField(default=None, help_text=b'Allow the club to pass on your email address to England Squash, so they can contact you with details of how to activate your membership, which is free as part of your subscription to Woking Squash Rackets Club.', verbose_name=b'England Squash Enrolment'),
        ),
        migrations.AlterField(
            model_name='membershipapplication',
            name='season',
            field=models.ForeignKey(to='usermodel.Season'),
        ),
        migrations.AlterField(
            model_name='player',
            name='prefs_esra_member',
            field=models.NullBooleanField(default=None, help_text=b'Allow the club to pass on your email address to England Squash, so they can contact you with details of how to activate your membership, which is free as part of your subscription to Woking Squash Rackets Club.', verbose_name=b'England Squash Enrolment'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='payment_frequency',
            field=models.CharField(default=b'annual', max_length=16, verbose_name=b'Payment Freq', choices=[(b'annual', b'Annually'), (b'triannual', b'Tri-annually'), (b'querterly', b'Quarterly'), (b'monthly', b'Monthly')]),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='season',
            field=models.ForeignKey(to='usermodel.Season'),
        ),
    ]
