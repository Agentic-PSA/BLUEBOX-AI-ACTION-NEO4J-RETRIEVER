import os
from src import get_app
from sanic import Sanic
from functools import partial
from sanic.worker.loader import AppLoader

from dotenv import load_dotenv


def start():
    load_dotenv()
    loader = AppLoader(factory=partial(get_app, os.getcwd()))
    app = loader.load()

    workers = int(os.environ.get('WORKERS', 4))
    debug = os.environ.get('DEBUG', False) == 'true'
    port = int(os.environ.get('PORT', 5013))

    if os.environ.get('SSL', False) == 'true':
        ssl = {
            "cert": os.path.join(os.getcwd(), 'certs', 'cert.pem'),
            "key": os.path.join(os.getcwd(), 'certs', 'key.pem'),
        }

        app.prepare('0.0.0.0', port, debug=debug, workers=workers, ssl=ssl)
    else:
        app.prepare('0.0.0.0', port, debug=debug, workers=workers)

    Sanic.serve(primary=app, app_loader=loader)


if __name__ == '__main__':
    start()


