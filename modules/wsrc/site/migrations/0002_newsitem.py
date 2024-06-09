from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('site', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='NewsItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_date', models.DateField(blank=True, null=True)),
                ('message', models.TextField()),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('link', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name_plural': 'News Items',
            },
        ),
    ]
