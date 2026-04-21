"""
Flask extensions inicializované bez app objektu (application factory pattern).

Samotné init_app() volání je v create_app() v __init__.py.
Tady jsou jen holé instance, aby je bylo možné importovat v celé aplikaci
bez circular importů.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_cors import CORS

# Limiter podle IP adresy klienta
limiter = Limiter(key_func=get_remote_address)

cache = Cache()

cors = CORS()
