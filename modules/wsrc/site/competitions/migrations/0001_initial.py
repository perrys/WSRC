# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-06-25 18:32
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
            name='Competition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('state', models.CharField(choices=[(b'not_started', b'Not Started'), (b'active', b'In Process'), (b'complete', b'Concluded')], default=b'not_started', max_length=16)),
                ('end_date', models.DateField()),
                ('url', models.CharField(blank=True, max_length=128)),
                ('ordering', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-group__end_date', 'ordering', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CompetitionGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('comp_type', models.CharField(choices=[(b'wsrc_boxes', b'Club Leagues'), (b'wsrc_tournaments', b'Club Tournaments'), (b'wsrc_qualifiers', b'Club Tournament Qualifiers')], max_length=32)),
                ('end_date', models.DateField()),
                ('active', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['comp_type', '-end_date'],
                'verbose_name': 'Competition Group',
            },
        ),
        migrations.CreateModel(
            name='CompetitionRound',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('round', models.IntegerField()),
                ('end_date', models.DateField()),
                ('competition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rounds', to='competitions.Competition')),
            ],
            options={
                'verbose_name': 'Competition Round',
            },
        ),
        migrations.CreateModel(
            name='Entrant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordering', models.IntegerField(help_text=b'Exact meaning depends on the competition type')),
                ('handicap', models.IntegerField(blank=True, null=True)),
                ('hcap_suffix', models.CharField(blank=True, max_length=4)),
                ('seeded', models.BooleanField(default=False)),
                ('competition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='competitions.Competition')),
                ('player1', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='usermodel.Player')),
                ('player2', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='player2', to='usermodel.Player')),
            ],
            options={
                'ordering': ['-competition__end_date', 'competition', 'ordering'],
            },
        ),
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('competition_match_id', models.IntegerField(blank=True, help_text=b'Unique ID of this match within its competition', null=True)),
                ('team1_score1', models.IntegerField(blank=True, null=True)),
                ('team1_score2', models.IntegerField(blank=True, null=True)),
                ('team1_score3', models.IntegerField(blank=True, null=True)),
                ('team1_score4', models.IntegerField(blank=True, null=True)),
                ('team1_score5', models.IntegerField(blank=True, null=True)),
                ('team2_score1', models.IntegerField(blank=True, null=True)),
                ('team2_score2', models.IntegerField(blank=True, null=True)),
                ('team2_score3', models.IntegerField(blank=True, null=True)),
                ('team2_score4', models.IntegerField(blank=True, null=True)),
                ('team2_score5', models.IntegerField(blank=True, null=True)),
                ('walkover', models.IntegerField(blank=True, choices=[(1, b'Opponent 1'), (2, b'Opponent 2')], null=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('competition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='competitions.Competition')),
                ('team1', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='match_1+', to='competitions.Entrant')),
                ('team2', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='match_2+', to='competitions.Entrant')),
            ],
            options={
                'verbose_name_plural': 'matches',
            },
        ),
        migrations.AddField(
            model_name='competition',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='competitions.CompetitionGroup'),
        ),
        migrations.AlterUniqueTogether(
            name='entrant',
            unique_together=set([('competition', 'player1'), ('competition', 'ordering')]),
        ),
        migrations.AlterUniqueTogether(
            name='competition',
            unique_together=set([('group', 'ordering')]),
        ),
    ]
