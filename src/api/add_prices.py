import json
from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse
from src.services.prices import Prices
from collections import OrderedDict
from packaging.version import parse as parse_version

from .forms.add_product import AddProductForm
from ..services.cypher_search import get_embedding


class AddPrices(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        prices = Prices()
        prices.actualize_prices()
        return JSONResponse(body={'success': True})

    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)
