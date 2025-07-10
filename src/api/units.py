import json
import logging
import re

from pint import UnitRegistry

from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse



class Units(HTTPMethodView):
    ureg = UnitRegistry()
    Q_ = ureg.Quantity

    @staticmethod
    async def post(request: Request) -> JSONResponse:
        numerical = request.json.get("numerical", {})
        response = {}
        for key, value in numerical.items():
            value = value.replace(",", ".", 1)
            match = re.search(r'(\d+(?:\.\d+)?)(\")?', value)
            if match and match.group(2) == '"':
                value = value.replace('"', ' in', 1)

            q = Units.Q_(value)
            v = q.m
            u = q.u
            logging.debug(f"Processing {key}: value = {v}, unit = {u}")
            response[key] = {
                'value': v,
                'unit': f"{u:~}"
            }


        return JSONResponse(body=response)


    @staticmethod
    async def options(self, request: Request, *args, **kwargs) -> JSONResponse:
        body = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        headers = {'Access-Control-Allow-Methods': 'POST,OPTIONS'}
        return JSONResponse(body=body, headers=headers)
