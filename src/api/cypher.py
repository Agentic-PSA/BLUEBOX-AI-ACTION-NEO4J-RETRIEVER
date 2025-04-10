import json
import logging
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

class Cypher(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        cypher = request.json.get("cypher", '')
        parameters = request.json.get("parameters", {})
        response = request.app.ctx.NEO4J.execute_query(cypher, parameters)
        print(str(response)[:100])
        print(type(response))

        return JSONResponse(body=response)


    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)
