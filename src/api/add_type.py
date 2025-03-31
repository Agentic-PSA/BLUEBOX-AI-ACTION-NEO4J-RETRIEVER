import json
import logging
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from .forms.add_type import AddTypeForm

class AddType(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = AddTypeForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)

        labels = ["Type"]
        attributes = {
            "code": form.cleaned_data['code'].replace("-", "_"),
            "name": form.cleaned_data.get('name', ''),
            "specification": str(form.cleaned_data['specification'])
        }

        response = request.app.ctx.NEO4J.add_node(labels, attributes)

        return JSONResponse(body=response)


    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)
