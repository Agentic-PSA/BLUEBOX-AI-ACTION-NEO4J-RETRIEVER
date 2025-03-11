from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from .forms.get_product import GetProductForm

class GetProduct(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = GetProductForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)
        ean = form.cleaned_data['ean']
        response = request.app.ctx.NEO4J.get_product(ean)
        if not response:
            return JSONResponse(body={"error": "Product not found"}, status=404)

        formatted_response = await GetProduct.format_response(ean, response)

        return JSONResponse(body=formatted_response)

    @staticmethod
    async def format_response(ean, response):
        formatted_response = {'EAN': ean}
        for property_dict in response:
            relationship = property_dict.get("relationship")
            section_name = relationship.get("properties", {}).get("section_name", "")
            property = property_dict.get("property")
            property_node = property.get("properties", {})
            name = property_node.get("name")
            value = property_node.get("value")
            unit = property_node.get("unit")
            for label in property.get("labels", []):
                if label.startswith("Property "):
                    language = label.replace("Property ", "")
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
