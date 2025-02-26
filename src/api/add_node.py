import json
import logging
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse
from collections import OrderedDict

from .forms.add_node import AddNodeForm

class AddNode(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = AddNodeForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)
        responses = []
        node_type = form.cleaned_data['type'].replace("-", "_")
        properties = form.cleaned_data['properties']
        region = properties.get('region', None)
        for language_key, sections in properties.items():
            if language_key == 'region':
                continue

            labels = [node_type, f"Language {language_key}"]
            if region:
                labels.append(f"Region {region}")

            logging.warning(labels)
            logging.warning(sections)
            attributes = AddNode.parse_sections(sections)

            response = request.app.ctx.NEO4J.add_node(labels, attributes)
            responses.append(response)

        return JSONResponse(body=responses)

    @staticmethod
    def parse_sections(sections: list) -> OrderedDict:
        attributes = OrderedDict()
        for section in sections:
            section_name = section.get('section_name', '')
            section_attributes = section.get('attributes', {})
            for attribute, value in section_attributes.items():
                attributes[f"{section_name}:{attribute}"] = value
        return attributes


    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)
