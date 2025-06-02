from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

class PropertiesValues(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        properties_list = request.json.get('properties', [])
        labels = request.json.get('labels', [])
        labels = [label.replace("-", "_") for label in labels]

        res = request.app.ctx.NEO4J.get_params_values(properties_list, labels)
        logger.debug(res)

        return JSONResponse(body=res, status=200)