#!/usr/bin/python  -Wd
#!/usr/bin/env python
import os
import sys
import logging

if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)-10s [%(levelname)s] %(message)s',datefmt="%Y-%m-%d %H:%M:%S")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wsrc.site.settings.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
