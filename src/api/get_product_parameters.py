from sanic.log import logger
from sanic.request import Request
from sanic.views import HTTPMethodView
from sanic.response import JSONResponse

from .forms.get_product import GetProductForm
from src.services.product_specification import get_form_data_many
import json

# PIMProductId
# Brand
# CategoryMapCollection
# ProductType
# NameEN
# NameDE
# TranslationCollection
# SferisName
# CNCode
# PKWiU
# Intrastatname
# IntrastatnameLong
# CountryOfOrigin
# Weight
# Height
# Width
# Depth
# ProducerGPSR
# ImporterGPSR
# Piktograms
# EnergyLabel
# Battery100Wh
# InstalledBattery
# LooseBattery
# Large
class GetProductParameters(HTTPMethodView):
    @staticmethod
    async def post(request: Request) -> JSONResponse:
        form = GetProductForm(request.json)
        if not form.is_valid():
            return JSONResponse(body=form.errors, status=400)
        action = form.cleaned_data.get('action', None)
        response = request.app.ctx.NEO4J.get_pim_data(action)
        result = {}

        if response:
            pd = response.get("pim_data", {})
            result["action"] = response.get("action", '')
            result["PIMProductId"] = pd.get("PIMProductId", '')
            result["Brand"] = pd.get("Brand", '')
            CategoryMapCollection = pd.get("CategoryMapCollection")
            if isinstance(CategoryMapCollection, str):
                result["CategoryMapCollection"] = json.loads(CategoryMapCollection)
            elif CategoryMapCollection is None:
                result["CategoryMapCollection"] = []
            result["ProductType"] = pd.get("ProductType", '')
            result["NamePL"] = response.get("namePL", '') #nazwa fakturowa PL
            result["NameEN"] = response.get("nameEN", '') #mazwa fakturowa EN
            result["NameDE"] = response.get("nameDE", '') #mazwa fakturowa DE
            result["NameISerwisPL"] = response.get("nameISerwisPL", '')
            result["NameISerwisEN"] = response.get("nameISerwisEN", '')
            result["NameISerwisDE"] = response.get("nameISerwisDE", '')
            result["SferisName"] = pd.get("SferisName", '')
            result["CNCode"] = pd.get("", '')
            result["PKWiU"] = pd.get("PKWiU", '')
            result["Intrastatname"] = pd.get("", '')
            result["IntrastatnameLong"] = pd.get("", '')
            result["CountryOfOrigin"] = pd.get("", '')
            result["Weight"] = pd.get("Height", '') #w gramach
            result["Height"] = pd.get("", '') #w mm
            result["Width"] = pd.get("", '') #w mm
            result["Depth"] = pd.get("Depth", '') #w mm
            result["ProducerGPSR"] = pd.get("", '') #"Lista pól: Nazwa Producenta	Ulica	Nr domu	Kod pocztowy	Miasto	Kraj	Nr kierunkowy	Nr telefonu	Email"
            result["ImporterGPSR"] = pd.get("", '') #"Lista pól: Nazwa Producenta	Ulica	Nr domu	Kod pocztowy	Miasto	Kraj	Nr kierunkowy	Nr telefonu	Email"
            result["Piktograms"] = pd.get("", '') #słownik
                # 851070 – Substancje łatwopalne
                # 851071 – Substancje pod ciśnieniem
                # 851072 – Drażniące lub szkodliwe
                # 851073 – Korozja
                # 851082 – Toksyczne dla zdrowia
                # 851103 – Materiały wybuchowe
                # 831752 – GHS01: Substancje wybuchowe
                # 830908 – GHS02: Flammable
                # 831754 – GHS03: Substancje utleniające
                # 831753 – GHS04: Gazy pod ciśnieniem
                # 830057 – GHS05: Corrosive
                # 831755 – GHS06: Toxic
                # 807686 – GHS07: Szkodliwy
            result["EnergyLabel"] = pd.get("", '')
            result["Battery100Wh"] = pd.get("Battery100Wh", '') #czy bateria w zestawie
            result["InstalledBattery"] = pd.get("InstalledBattery", '') #czy bateria zainstalowana
            result["LooseBattery"] = pd.get("LooseBattery", '') #czy bateria luzem
            result["Large"] = pd.get("Large", '')
            #result["TranslationCollection"] = pd.get("TranslationCollection", [])
            return JSONResponse(body=result)
        if not response:
            return JSONResponse(body={"error": "Product not found"}, status=404)

        formatted_response = await GetProductParameters.format_response(formatted_response, response)
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
