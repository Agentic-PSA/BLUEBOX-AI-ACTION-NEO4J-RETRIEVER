import json
import logging
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse
from .forms.add_node import AddNodeForm

class AddNode(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = AddNodeForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)

        node_type = form.cleaned_data['type'].replace("-", "_")
        properties = form.cleaned_data['properties']
        logging.warning(node_type)
        logging.warning(properties)

        response = request.app.ctx.NEO4J.add_node(node_type, properties)

        return JSONResponse(body=response)


    @staticmethod
    def _execute_query(tx, query, parameters):
        return tx.run(query, parameters)

    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)
