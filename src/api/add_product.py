import json
from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse
from collections import OrderedDict

from .forms.add_product import AddProductForm
from ..services.cypher_search import get_embedding


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
        pim_data = form.cleaned_data.get('pim_data', {})
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
                if properties['common'].get('Nazwa'):
                    main_node_properties['nameEmbedding'] = get_embedding(properties['common']['Nazwa'])
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
                section_sort = section.get('section_sort', 0)
                section_attributes = section.get('attributes', {})
                attributes_types = section.get('attributes_types', {})
                i = 0
                for attribute, value in section_attributes.items():
                    i += 1
                    attribute_sort = i
                    attribute_type = attributes_types.get(attribute, '')
                    relationship_properties = {
                        'section_name': section_name,
                        'section_sort': section_sort,
                        'attribute_sort': attribute_sort,
                        'attribute_type': attribute_type
                    }
                    response = request.app.ctx.NEO4J.add_property_node(product_node, attribute, value,
                                                                       f"Property_{language_key}",
                                                                       relationship_properties)

                    responses.append(response)
                    logger.info(response)

        if pim_data:
            pim_node = request.app.ctx.NEO4J.add_node(["PIM_Data"], {
                "PIMProductId": pim_data.get("PIMProductId"),
                "ProductNumber": pim_data.get("ProductNumber"),
                "ProductVersion": pim_data.get("ProductVersion"),
                "ProductType": pim_data.get("ProductType"),
                "Brand": pim_data.get("Brand"),
                "Weight": pim_data.get("Weight"),
                "Height": pim_data.get("Height"),
                "Width": pim_data.get("Width"),
                "Depth": pim_data.get("Depth"),
                "Battery100Wh": pim_data.get("Battery100Wh"),
                "LooseBattery": pim_data.get("LooseBattery"),
                "InstalledBattery": pim_data.get("InstalledBattery"),
                "PKWiU": pim_data.get("PKWiU"),
                "Large": pim_data.get("Large"),
                "ImporterGPSR": pim_data.get("ImporterGPSR"),
                "ProducerGPSR": pim_data.get("ProducerGPSR"),
                "SferisName": pim_data.get("SferisName")
            })
            responses.append(pim_node)

            # relacja Product -> PIM_Data
            request.app.ctx.NEO4J.add_relationship(product_node, "ENRICHED_BY", pim_node)

            # kolekcje PIM_Data
            collections_mapping = {
                "TranslationCollection": "Translation",
                "BarcodeCollection": "Barcode",
                "CategoryMapCollection": "Category",
                "ComponentCollection": "Component",
                "RelatedProductCollection": "RelatedProduct"
            }
            for collection_name, node_label in collections_mapping.items():
                items = pim_data.get(collection_name, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    collection_node = request.app.ctx.NEO4J.add_node([node_label], item)
                    request.app.ctx.NEO4J.add_relationship(pim_node, "HAS_COLLECTION", collection_node)
                    responses.append(collection_node)

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
