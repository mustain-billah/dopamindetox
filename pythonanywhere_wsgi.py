"""Contents for PythonAnywhere's WSGI file.

Do NOT deploy this file as-is — PythonAnywhere ignores it. Copy what's below
into the file the Web tab links to:

    /var/www/dopamindetox_pythonanywhere_com_wsgi.py

Delete everything already in that file first, then Save and hit Reload.
"""

import os
import sys

# Absolute path to the folder holding manage.py.
path = "/home/dopamindetox/dopamindetox"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

# Settings come from /home/dopamindetox/dopamindetox/.env, so nothing else here.
from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
