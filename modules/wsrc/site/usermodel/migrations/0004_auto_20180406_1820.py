# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import wsrc.site.usermodel.models


class Migration(migrations.Migration):

    dependencies = [
        ('usermodel', '0003_auto_20180331_1836'),
    ]

    operations = [
        migrations.AddField(
            model_name='doorcardlease',
            name='comment',
            field=models.TextField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='membershipapplication',
            name='season',
            field=models.ForeignKey(default=wsrc.site.usermodel.models.latest_season, to='usermodel.Season'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='season',
            field=models.ForeignKey(default=wsrc.site.usermodel.models.latest_season, to='usermodel.Season'),
        ),
    ]
