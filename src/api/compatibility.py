import json
from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from .forms.compatibility import CompatibilityForm


class Compatibility(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        if "compatibilities" in request.json:
            return Compatibility.multiple_compatibilities(request)

        form = CompatibilityForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)



        type1 = form.cleaned_data.get("type1", '')
        type2 = form.cleaned_data.get("type2", '')
        type_compatibility = form.cleaned_data["type_compatibility"].upper()
        type1_parameters = form.cleaned_data.get("type1_parameters", {})
        if type1_parameters:
            type1_parameters = {"properties": type1_parameters}
        else:
            type1_parameters = {}
        type2_parameters = form.cleaned_data.get("type2_parameters", {})
        if type2_parameters:
            type2_parameters = {"properties": type2_parameters}
        else:
            type2_parameters = {}

        response = request.app.ctx.NEO4J.add_bidirectional_relationship_with_properties(type1, type2, type_compatibility,
                                                                                        type1_parameters, type2_parameters)

        logger.info(f"Compatibility response: {response}")

        return JSONResponse(body={})


    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)

    @staticmethod
    def multiple_compatibilities(request):
        compatibilities = request.json.get("compatibilities")
        for compatibility in compatibilities:
            type1 = compatibility.get("type1", '')
            type2 = compatibility.get("type2", '')
            type_compatibility = compatibility.get("type_compatibility", "").upper()
            response = request.app.ctx.NEO4J.add_bidirectional_relationship_with_properties(type1, type2,
                                                                                            type_compatibility)
            #logger.info(f"Compatibility response: {response}")
        return JSONResponse(body={})

