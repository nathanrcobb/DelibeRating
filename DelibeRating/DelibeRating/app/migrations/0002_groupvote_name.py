# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-05-17 05:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupvote',
            name='name',
            field=models.CharField(default='', max_length=50),
            preserve_default=False,
        ),
    ]