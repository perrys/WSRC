
def init():

  import os
  os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wsrc.site.settings.settings")

  import logging
  logging.basicConfig(format='%(asctime)-10s [%(levelname)s] %(message)s',datefmt="%Y-%m-%d %H:%M:%S")

  import django
  if hasattr(django, "setup"):
    django.setup()

init()
