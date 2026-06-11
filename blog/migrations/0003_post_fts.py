from django.db import migrations


class Migration(migrations.Migration):
    """Create the FTS5 virtual table searched by blog.search and populated by sync."""

    dependencies = [
        ("blog", "0002_alter_post_options_alter_tag_options_post_excerpt_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE VIRTUAL TABLE post_fts USING fts5("
                "slug UNINDEXED, title, body, tokenize='unicode61');"
            ),
            reverse_sql="DROP TABLE IF EXISTS post_fts;",
        ),
    ]
