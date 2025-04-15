import json
from sanic.log import logger
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
        labels = ["Product", node_type]
        if region:
            labels.append(f"Region_{region}")
        # dodanie głównego node produktu
        main_node_properties = {}
        if 'EAN' in properties:
            main_node_properties['EAN'] = properties['EAN']
        if 'action' in properties:
            main_node_properties['action'] = properties.get('action', '')
        if 'common' in properties:
            if isinstance(properties['common'], dict):
                main_node_properties['name'] = properties['common'].get('Nazwa', '')
                main_node_properties['product_number'] = properties['common'].get('Product number', '')
                main_node_properties['producer'] = properties['common'].get('Producent', '')

        product_node = request.app.ctx.NEO4J.add_node(labels, main_node_properties)
        logger.info(product_node)

        for language_key, sections in properties.items():
            if not isinstance(sections, list):
                continue

            for section in sections:
                if not isinstance(section, dict):
                    continue
                section_name = section.get('section_name', '')
                section_attributes = section.get('attributes', {})
                for attribute, value in section_attributes.items():
                    relationship_properties = {'section_name': section_name}
                    response = request.app.ctx.NEO4J.add_property_node(product_node, attribute, value,
                                                                       f"Property_{language_key}",
                                                                       relationship_properties)

                    responses.append(response)
                    logger.info(response)

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
