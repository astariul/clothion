"""`clothion` module.

`clothion` is the module containing the code to run Clothion server. You can
simply run the command line to run the server locally, using a local database.
Then go to your browser and use the website.
"""


__version__ = "0.2.0.dev0"

# isort: off

from .configuration import config
from .app import app
