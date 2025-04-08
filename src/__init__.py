import logging
import os


from sanic import Sanic
from sanic_cors import CORS

from .services import Neo4jConnector
from .utils import UnitConverter

from .api import AddNode, AddType, AddProduct, Cypher, Compatibility
from .api import GetProduct, GetProducts, Search


def get_app(root_path: str) -> Sanic:
    app = Sanic(
        name=os.environ.get('APP_NAME', 'NEO4J_RETRIEVER')
    )
    CORS(app)
    app.config.REQUEST_MAX_SIZE = 1000000000

    app.ctx.ROOT_PATH = root_path

    app.ctx.NEO4J = Neo4jConnector()

    app.add_route(GetProduct.as_view(), 'get_product/')
    app.add_route(GetProducts.as_view(), 'get_products/')
    app.add_route(Search.as_view(), 'search/')

    app.add_route(AddNode.as_view(), 'add_node/')
    app.add_route(AddProduct.as_view(), 'add_product/')
    app.add_route(AddType.as_view(), 'add_type/')
    app.add_route(Cypher.as_view(), 'cypher/')
    app.add_route(Compatibility.as_view(), 'compatibility/')


    return app
