import re

from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from .forms.search import SearchForm

from src.services.cypher_search import simple_search


class SimpleSearch(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = SearchForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)
        query = form.cleaned_data['query']
        query = re.sub(r'(?<!\\)"', r'\"', query)
        query = query.replace("::", ":")

        response = simple_search(query)
        if not response:
            return JSONResponse(body={"error": "Error"}, status=404)


        return JSONResponse(body=response)

    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)