from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('keywords', '0002_weekly_partitioning'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadfile',
            name='file_hash',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
