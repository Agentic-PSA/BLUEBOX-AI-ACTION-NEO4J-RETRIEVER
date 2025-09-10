import logging
import os


from sanic import Sanic
from sanic_cors import CORS

from .services import Neo4jConnector
from .utils import UnitConverter

from .api import AddNode, AddType, AddProduct, Cypher, Compatibility, PropertiesValues, AddValues, Units
from .api import GetProduct, GetProducts, Search, SimpleSearch
from sanic import Sanic, response


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
    app.add_route(SimpleSearch.as_view(), 'simple_search/')

    app.add_route(AddNode.as_view(), 'add_node/')
    app.add_route(AddProduct.as_view(), 'add_product/')
    app.add_route(AddType.as_view(), 'add_type/')
    app.add_route(Cypher.as_view(), 'cypher/')
    app.add_route(Compatibility.as_view(), 'compatibility/')
    app.add_route(PropertiesValues.as_view(), 'properties_values/')
    app.add_route(AddValues.as_view(), 'add_values/')
    app.add_route(Units.as_view(), 'units/')

    @app.route("/demo_search", methods=["GET"])
    async def serve_index(request):
        return await response.file("demo/index.html")

    @app.route("/demo_ean", methods=["GET"])
    async def serve_index_ean(request):
        return await response.file("demo/index1.html")

    return app
