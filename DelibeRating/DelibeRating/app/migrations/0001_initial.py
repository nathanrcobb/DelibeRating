# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-05-06 05:02
from __future__ import unicode_literals

import django.contrib.auth.models
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0008_alter_user_username_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomUser',
            fields=[
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('username', models.CharField(max_length=20, primary_key=True, serialize=False)),
                ('email', models.CharField(max_length=100)),
                ('password', models.CharField(max_length=40)),
                ('first_name', models.CharField(max_length=20)),
                ('last_name', models.CharField(max_length=20)),
            ],
            options={
                'db_table': 'app_customuser',
                'managed': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='CustomGroup',
            fields=[
                ('name', models.CharField(max_length=50, primary_key=True, serialize=False)),
                ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
            ],
            options={
                'db_table': 'app_customgroup',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='GroupVote',
            fields=[
                ('vote_id', models.CharField(max_length=30, primary_key=True, serialize=False)),
                ('vote_options', models.CharField(max_length=10000)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.CustomGroup')),
            ],
            options={
                'db_table': 'app_votes',
            },
        ),
    ]
