from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_cors import CORS

limiter = Limiter(key_func=get_remote_address)
cache = Cache()
cors = CORS()
