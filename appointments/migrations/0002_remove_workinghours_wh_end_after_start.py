# This migration is intentionally empty.
# The wh_end_after_start constraint added in 0001 must remain.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0001_initial'),
    ]

    operations = []
