from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse


class GetProducts(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        skip = request.json.get("skip", 0)
        limit = request.json.get("limit", 100)
        response = request.app.ctx.NEO4J.get_products(skip, limit)
        return JSONResponse(response)

    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)