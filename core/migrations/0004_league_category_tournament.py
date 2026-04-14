from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0003_classification_assignment_window'),
    ]

    operations = [
        # 1. Add category to League
        migrations.AddField(
            model_name='league',
            name='category',
            field=models.CharField(
                choices=[
                    ('a_ligi', 'A Ligi'),
                    ('b_ligi', 'B Ligi'),
                    ('gencler', 'Gencler'),
                    ('kucukler', 'Kucukler'),
                    ('diger', 'Diger'),
                ],
                default='diger',
                max_length=20,
                verbose_name='Kategori',
            ),
        ),

        # 2. Create Tournament model
        migrations.CreateModel(
            name='Tournament',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Turnuva Adi')),
                ('short_name', models.CharField(blank=True, max_length=50, verbose_name='Kisa Ad')),
                ('description', models.TextField(blank=True, verbose_name='Aciklama')),
                ('start_date', models.DateField(verbose_name='Baslangic Tarihi')),
                ('end_date', models.DateField(verbose_name='Bitis Tarihi')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Olusturan',
                )),
                ('venue', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='core.venue',
                    verbose_name='Salon',
                )),
            ],
            options={
                'verbose_name': 'Turnuva',
                'verbose_name_plural': 'Turnuvalar',
                'ordering': ['-start_date'],
            },
        ),

        # 3. Make Match.league nullable
        migrations.AlterField(
            model_name='match',
            name='league',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='matches',
                to='core.league',
            ),
        ),

        # 4. Add tournament FK to Match
        migrations.AddField(
            model_name='match',
            name='tournament',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='matches',
                to='core.tournament',
                verbose_name='Turnuva',
            ),
        ),

        # 5. Add tournament FK to AssignmentWindow
        migrations.AddField(
            model_name='assignmentwindow',
            name='tournament',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assignment_windows',
                to='core.tournament',
                verbose_name='Turnuva',
                help_text='Bos=global (lig maclari). Secilirse sadece o turnuva icin gecerlidir.',
            ),
        ),
    ]
