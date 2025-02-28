import logging
import os


from sanic import Sanic
from sanic_cors import CORS

from .services import Neo4jConnector

from .api import AddNode
from .api import AddProduct


def get_app(root_path: str) -> Sanic:
    app = Sanic(
        name=os.environ.get('APP_NAME', 'NEO4J_RETRIEVER')
    )
    CORS(app)
    app.config.REQUEST_MAX_SIZE = 1000000000

    app.ctx.ROOT_PATH = root_path


    app.ctx.NEO4J = Neo4jConnector()

    app.add_route(AddNode.as_view(), 'add_node/')
    app.add_route(AddProduct.as_view(), 'add_product/')

    # app.add_route(Health.as_view(), 'health/')

    return app
