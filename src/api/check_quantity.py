import json
from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse
from src.services.prices import Prices
from collections import OrderedDict
from packaging.version import parse as parse_version

from .forms.add_product import AddProductForm
from ..services.cypher_search import check_quantity


class CheckQuantity(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        try:
            data = request.json
            category = data.get("category")
            if not category:
                return JSONResponse({"success": False, "error": "Brak parametru category", "cnt":-1}, status=400)
            
            try:
                count = check_quantity(category)
            except Exception as e:
                return JSONResponse({"success": False, "error": str(e), "cnt":-1}, status=500)
            return JSONResponse({"success": True, "error":"", "cnt": count})
        except Exception as e:
            return JSONResponse({"success": False, "error": f"Niepoprawny JSON {e}", "cnt":-1}, status=400)


    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)
