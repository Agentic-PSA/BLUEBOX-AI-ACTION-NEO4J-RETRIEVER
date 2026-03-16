import re
import json

from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from .forms.search import SearchForm

from src.services.cypher_search import cypher_search
from src.services.ai_search import ai_search


class Search(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        print("Search(HTTPMethodView)")
        form = SearchForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)
        query = form.cleaned_data['query']
        query = re.sub(r'(?<!\\)"', r'\"', query)
        query = query.replace("::", ":")
        parameters = form.cleaned_data.get('parameters', False)
        logger.debug(f"parameters: {parameters}")
        # ai_answer = form.cleaned_data.get('ai', False)
        # if ai_answer:
        #     response = ai_search(query, parameters)
        # else:
        #     response = cypher_search(query, parameters)
        notFullMatch = form.cleaned_data.get('notFullMatch', False)
        response = cypher_search(query, parameters, notFullMatch)
        if not response:
            return JSONResponse(body={"error": "Error"}, status=404)

        for resp in response.get("results",[]):
            value_p = resp.get("Photocollection")
            if isinstance(value_p, str):
                resp["Photocollection"] = json.loads(value_p)
            elif value_p is None:
                resp["Photocollection"] = []
            value_f = resp.get("Filecollection")
            if isinstance(value_f, str):
                resp["Filecollection"] = json.loads(value_f)
            elif value_f is None:
                resp["Filecollection"] = []
        return JSONResponse(body=response)

    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)