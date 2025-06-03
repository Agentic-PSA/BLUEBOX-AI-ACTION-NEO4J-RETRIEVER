from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from src.api.forms.add_values import AddValuesForm

# CREATE CONSTRAINT unique_value_combination IF NOT EXISTS FOR (n:Value) REQUIRE (n.label, n.property, n.value) IS UNIQUE

class AddValues(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = AddValuesForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)

        parameters_dict = form.cleaned_data.get("parameters_dict")
        label = form.cleaned_data.get("label").replace("-", "_")

        responses = []
        for property, values in parameters_dict.items():
            for value, correct_value in values.items():
                if value == correct_value:
                    logger.debug(f"Skipping value '{value}' for property '{property}' as it matches the correct value.")
                    continue
                node_params = {
                    "label": label,
                    "property": property,
                    "value": value,
                    "correct_value": correct_value
                }
                response = request.app.ctx.NEO4J.add_value_node(node_params)
                responses.append(response)
                logger.debug(response)

        return JSONResponse(body=responses)