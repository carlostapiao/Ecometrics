from django.db import migrations


def crear_categorias(apps, schema_editor):
    Categoria = apps.get_model("residuos", "Categoria")
    for clave, nombre, grupo in [
        ("no-reciclable", "No reciclables", "no_reciclable"),
        ("plastico", "Plástico", "reciclable"),
        ("carton", "Cartón", "reciclable"),
        ("vidrio", "Vidrio", "reciclable"),
        ("metal", "Metal", "reciclable"),
        ("organico", "Orgánicos", "organico"),
    ]:
        Categoria.objects.using(schema_editor.connection.alias).get_or_create(clave=clave, defaults={"nombre": nombre, "grupo": grupo})


class Migration(migrations.Migration):
    dependencies = [("residuos", "0001_initial")]
    operations = [migrations.RunPython(crear_categorias, reverse_code=migrations.RunPython.noop)]
