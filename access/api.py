import json
import threading
import time
from .store import Store


class Application:
    def __init__(self, store):
        self.store = store
        self.rates = {}
        self.lock = threading.Lock()

    def allowed(self, address):
        now = time.monotonic()
        with self.lock:
            self.rates = {key: value for key, value in self.rates.items() if value[0] > now - 60}
            if address not in self.rates and len(self.rates) >= 4096:
                return False
            start, count = self.rates.get(address, (now, 0))
            self.rates[address] = (start, count + 1)
            return count < 20

    def __call__(self, environ, start_response):
        code, result = '200 OK', {}
        try:
            if environ.get('wsgi.url_scheme') != 'https':
                code, result = '403 Forbidden', {'error': 'HTTPS required'}
            elif not self.allowed(environ.get('REMOTE_ADDR', 'unknown')):
                code, result = '429 Too Many Requests', {'error': 'Please wait before retrying'}
            elif environ.get('REQUEST_METHOD') != 'POST':
                code, result = '405 Method Not Allowed', {'error': 'POST required'}
            else:
                length = int(environ.get('CONTENT_LENGTH') or '0')
                if not 0 < length <= 4096 or environ.get('CONTENT_TYPE') != 'application/json':
                    raise ValueError('Invalid request')
                body = json.loads(environ['wsgi.input'].read(length))
                if not isinstance(body, dict):
                    raise ValueError('Invalid request')
                path = environ.get('PATH_INFO')
                if path == '/v1/area52/enroll':
                    result = self.store.enroll(body['invitation'], body['request_token'],
                                               body['username'], body['password'])
                elif path in ('/v1/area52/status', '/v1/area52/downloads'):
                    authorization = environ.get('HTTP_AUTHORIZATION', '')
                    if not authorization.startswith('Bearer '):
                        raise ValueError('Access credential required')
                    result = self.store.status(authorization[7:])
                    if path.endswith('/downloads'):
                        code, result = '503 Service Unavailable', {'error': 'Client distribution not configured'}
                else:
                    code, result = '404 Not Found', {'error': 'Unknown endpoint'}
        except (ValueError, KeyError, TypeError, UnicodeError):
            code, result = '400 Bad Request', {'error': 'Request rejected; check invitation and account details'}
        except Exception:
            code, result = '503 Service Unavailable', {'error': 'Service unavailable; retry using the same request credential'}
        encoded = json.dumps(result).encode('utf-8')
        start_response(code, [('Content-Type', 'application/json'), ('Cache-Control', 'no-store'),
                              ('X-Content-Type-Options', 'nosniff'), ('Content-Length', str(len(encoded)))])
        return [encoded]


def create_app(path):
    return Application(Store(path))
