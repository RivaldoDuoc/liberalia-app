from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='must_change_password',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text='Si está en True, debe cambiar la contraseña al iniciar sesión.'
            ),
        ),
    ]

