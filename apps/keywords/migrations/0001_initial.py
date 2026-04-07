import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UploadFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255)),
                ('total_keywords', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='upload_files',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Keyword',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=500)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('processing', 'Processing'),
                            ('completed', 'Completed'),
                            ('failed', 'Failed'),
                        ],
                        default='pending',
                        max_length=20,
                    ),
                ),
                ('retry_count', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'upload_file',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='keywords', to='keywords.uploadfile'
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SearchResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_ads', models.PositiveIntegerField(default=0)),
                ('total_links', models.PositiveIntegerField(default=0)),
                ('raw_html', models.TextField(blank=True, default='')),
                ('scraped_at', models.DateTimeField(auto_now_add=True)),
                (
                    'keyword',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, related_name='search_result', to='keywords.keyword'
                    ),
                ),
            ],
        ),
    ]
