from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse


class GetProducts(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        skip = request.json.get("skip", 0)
        limit = request.json.get("limit", 100)
        type = request.json.get("type", None)
        if type:
            type = type.replace("-", "_")
        parameters = request.json.get("parameters", False)

        if parameters:
            response = request.app.ctx.NEO4J.get_products_with_parameters(skip, limit, type)
        else:
            response = request.app.ctx.NEO4J.get_products(skip, limit)
        return JSONResponse(response)

    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)