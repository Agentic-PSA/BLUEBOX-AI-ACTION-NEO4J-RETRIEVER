import json
import logging
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse
from collections import OrderedDict

from .forms.add_product import AddProductForm

class AddProduct(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = AddProductForm(request.json)
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
            # dodanie głównego node produktu
            product_node = request.app.ctx.NEO4J.add_node(labels, {})
            responses.append(product_node)
            logging.warning("product_node")
            logging.warning(product_node)

            for section in sections:
                section_name = section.get('section_name', '')
                section_attributes = section.get('attributes', {})
                for attribute, value in section_attributes.items():
                    relationship_properties = {'section_name': section_name}
                    response = request.app.ctx.NEO4J.add_property_node(product_node, attribute, value, relationship_properties)

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
