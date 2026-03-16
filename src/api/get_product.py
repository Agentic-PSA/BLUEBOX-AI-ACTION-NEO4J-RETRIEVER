from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from .forms.get_product import GetProductForm
from src.services.product_specification import get_form_data_many
import json

# ComponentCollection
# {	
# 	ComponentItemID
# 	ComponentQty
# }	
# RelatedProductCollection
# {	
# 	ProductNumber
# 	RelationType
# 	RelationNo
# }	
# Speccollection
# {		
# 	Sekcja id	string
# 	Atrybut id	string
# 	Wartość	string
# 	Language id	
# }		
# Photocollection
# {	
# 	Photolink
# }	
# Filecollection?
# {	
# 	Filelink
# }	
class GetProduct(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = GetProductForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)
        ean = form.cleaned_data.get('ean', None)
        parameters = form.cleaned_data.get('parameters', False)
        if ean:
            formatted_response = {"EAN": ean}
            if parameters:
                response = request.app.ctx.NEO4J.get_product_with_parameters(ean)
            else:
                response = request.app.ctx.NEO4J.get_product(ean)
        elif 'pn' in form.cleaned_data:
            pn = form.cleaned_data.get('pn', None)
            response = request.app.ctx.NEO4J.get_product_by_pn(pn, parameters)
            if response:
                return JSONResponse(body=response)
        elif 'action' in form.cleaned_data:
            action = form.cleaned_data.get('action', None)
            response = request.app.ctx.NEO4J.get_product_by_action_code(action, parameters)
        elif 'name' in form.cleaned_data:
            name = form.cleaned_data.get('name', None)
            response = request.app.ctx.NEO4J.get_product_by_name(name, with_parameters=parameters)

        if response:
            for resp in response:
                if isinstance(resp, dict):
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


            if parameters and response[0].get("labels"):
                # dodanie sekcji z Danymi podstawowymi
                attributes_basic = []
                spec_data = get_form_data_many('category', response[0]["labels"], table='forms')
                for block in spec_data.get("form", {}):
                    for section in block.get("value", []):
                        section_name = section.get("section_name", {}).get("PL")
                        if section_name == "Dane podstawowe":
                            for attr in section.get("attributes", []):
                                attributes_basic.append(attr.get("PL"))
                to_add = []
                for resp in response:
                    resp["ComponentCollection"] = [{"ComponentItemID":"TEST", "ComponentQty":1}]
                    resp["RelatedProductCollection"] = [{"ProductNumber":"TEST", "RelationType":"Related", "RelationNo":1},{"ProductNumber":"TEST", "RelationType":"Duplicate", "RelationNo":1}]
                    for prop in resp.get("properties", []):
                        if prop.get("name") in attributes_basic:
                            prop_copy = prop.copy()
                            prop_copy["section"] = "Dane podstawowe"
                            to_add.append(prop_copy)
                    resp["properties"] = to_add + resp.get("properties", [])

            return JSONResponse(body=response)
        if not response:
            return JSONResponse(body={"error": "Product not found"}, status=404)

        formatted_response = await GetProduct.format_response(formatted_response, response)
        return JSONResponse(body=formatted_response)

    @staticmethod
    async def format_response(formatted_response, response):
        for property_dict in response:
            relationship = property_dict.get("relationship")
            section_name = relationship.get("properties", {}).get("section_name", "")
            property = property_dict.get("property")
            property_node = property.get("properties", {})
            name = property_node.get("name")
            value = property_node.get("value")
            unit = property_node.get("unit")
            for label in property.get("labels", []):
                if label.startswith("Property_"):
                    language = label.replace("Property_", "")
                    if language not in formatted_response:
                        formatted_response[language] = {}
                    if section_name not in formatted_response[language]:
                        formatted_response[language][section_name] = {}
                    if unit:
                        formatted_response[language][section_name][name] = {"value": value, "unit": unit}
                    else:
                        if isinstance(formatted_response[language][section_name].get(name), list):
                            formatted_response[language][section_name][name].append(value)
                        elif formatted_response[language][section_name].get(name):
                            formatted_response[language][section_name][name] = [
                                formatted_response[language][section_name][name], value]
                        else:
                            formatted_response[language][section_name][name] = value
        return formatted_response

    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)
