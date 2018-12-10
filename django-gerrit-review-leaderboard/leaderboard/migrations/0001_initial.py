# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Change',
            fields=[
                ('timestamp', models.DateTimeField()),
                ('owner_full_name', models.CharField(max_length=70)),
                ('subject', models.CharField(max_length=200)),
                ('project_name', models.CharField(max_length=50)),
                ('change_id', models.CharField(max_length=50, serialize=False, primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('timestamp', models.DateTimeField()),
                ('message', models.CharField(max_length=2000)),
                ('change', models.ForeignKey(to='leaderboard.Change')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Reviewer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('full_name', models.CharField(max_length=70)),
                ('changes', models.ManyToManyField(to='leaderboard.Change')),
                ('comments', models.ManyToManyField(to='leaderboard.Comment')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
