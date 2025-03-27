from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from .forms.search import SearchForm

from src.services.cypher_search import cypher_search

class Search(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = SearchForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)
        query = form.cleaned_data['query']
        response = cypher_search(query)
        # response = request.app.ctx.NEO4J.get_product(ean)
        if not response:
            return JSONResponse(body={"error": "Error"}, status=404)


        return JSONResponse(body=response)