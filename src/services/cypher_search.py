import os

import httpx
from httpx import Client
import uuid
import time
import json
from py2neo import Graph
import openai
from neo4j import GraphDatabase, Result
from sanic import Sanic
from sanic.log import logger

import src.services.product_specification
import src.services.db_schema

# client = Anthropic(
#     api_key="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",
#     # This is the default and can be omitted
# )
uri = f"neo4j://{os.environ.get("NEO4J_HOST")}:{os.environ.get("NEO4J_PORT")}"
driver = GraphDatabase.driver(uri, auth=(os.environ.get("NEO4J_USER"), os.environ.get("NEO4J_PASSWORD")))

client_gpt = openai.OpenAI(
   api_key="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")



def llm(prompt):
    response = client_gpt.chat.completions.create(
        model="gpt-4o-mini",
        # reasoning_effort='high',
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    print(response)
    response_text = response.choices[0].message.content
    print(response_text)
    return response_text

def search_index(names=[]):
    client = Client(verify=False)
    items = [{
                "item_id": str(uuid.uuid4()),
                "item_description": name
            } for name in names]

    token = os.environ.get("ACTION_TOKEN")
    response = client.post(
        'https://bbx.action.pl:5555/search_index',
        headers={
            'Authorization': f'Bearer {token}'
        },
        json=items,
        timeout=httpx.Timeout(60)
    )
    logger.debug(response.json())

    results = []
    for item in response.json():
        item_number = item.get('item_number', '')
        if item_number:
            results.append(item_number)
    return results

def search_group(descriptions=[]):
    client = Client(verify=False)

    token = os.environ.get("ACTION_TOKEN")
    response = client.post(
        'https://bbx.action.pl:5555/search_group',
        headers={
            'Authorization': f'Bearer {token}'
        },
        json=[
            {
                "item_id": str(uuid.uuid4()),
                "item_description": description,
            } for description in descriptions
        ],
        timeout=httpx.Timeout(60)
    )

    print(response.json())

    results = []
    for item in response.json():
        item_results = item.get('results', [])
        if item_results and isinstance(item_results, list):
            results.append(item_results[0])
    return results


def generate_simple_cypher_query_with_llm(schema_text, relationships, user_query, specifications):
    # Przygotuj dane jako tekst
    # schema_text = get_schema_text(db_schema)
    # print(schema_text)

    relationships_text = "\n".join([
        f"- {rel['source']} -> {rel['relationship']} -> {rel['target']}"
        for rel in relationships
    ])

    # Zapytanie do LLM z elastycznym podejściem
    prompt = f"""
Wygeneruj zapytanie Cypher dla Neo4j, które najlepiej odpowiada na potrzeby użytkownika w oparciu o dostępne typy węzłów i relacje w bazie danych.

DOSTĘPNE TYPY WĘZŁÓW I ICH WŁAŚCIWOŚCI:
{schema_text}

Pola dostępne w wybranych typach produktów:
{specifications}

ZAPYTANIE UŻYTKOWNIKA:
{user_query}

WSKAZÓWKI:
1. Przeanalizuj dokładnie zapytanie użytkownika i zidentyfikuj, których węzłów i relacji będzie ono dotyczyć
2. Dopasuj odpowiednie wektory semantyczne do kontekstu zapytania
3. Dobierz optymalną strukturę zapytania - może to być:
   - Wyszukiwanie semantyczne oparte na podobieństwie wektorów
   - Wyszukiwanie po właściwościach konkretnych węzłów
   - Kombinacja powyższych metod
4. Zdecyduj, czy konieczne jest wyszukiwanie powiązanych węzłów, a jeśli tak - na jakim poziomie głębokości

WYMAGANIA TECHNICZNE:
1. Etykiety węzłów ze spacjami umieszczaj w backtickach, np. `Fundusz Inwestycyjny`
2. Do porównań wektorowych używaj funkcji gds.similarity.cosine() dla wartości opisowych. Zabronione jest korzystanie z porównań na polach tekstowych innych niż wektorowe. 
3. Dla pól liczbowych i logicznych używaj operacji porównania (>, <, =, >=, <=, <>)
4. Dla wyszukiwań semantycznych dodaj zabezpieczenia w postaci warunków:
   WHERE n.wektor_pola IS NOT NULL
   AND $parametrVector IS NOT NULL
   AND size(n.wektor_pola) = size($parametrVector)
5. Koniecznie bierz pod uwagę obie relacje odwzajemniające np.:
   REFERS_TO i REFERENCES
   CONTAINS i BELONGS_TO
   HAS_AUTHORITY i HAS_JURISDICTION
   itp.
6. Dostosuj wartość progu podobieństwa (threshold) do kontekstu zapytania oraz długości porównywanych zwrotów: 0.3-0.7
7. Sortuj wyniki według najbardziej odpowiedniego kryterium dla danego zapytania
8. Model ma zawsze znaleźć najpewniejszą informację (lub kilka o takiej samej największej pewności) ale query nie powinno zawierać LIMIT 1
9. Jeśli zliczasz obiekty dodaj osobny klucz zawierający ich id, pod żadnym pozorem nie zapisuj ich vectorów i sprawdz czy nie ma dupliaktów
10. Zawsze zwracaj ID węzłów, aby uniknąć duplikatów oraz pola tych węzłów
11. Nigdy nie deklaruj wartości w zapytaniu jeśli używasz dopasowania wektora. Użyj zamiast tego parametrów.
12. Klucze wynikowe mają być w formacie camel_case.
13. Jeśli zwracane jest kilka obiektów nie mogą być duplikatami.
 14. Pole name jest zazwyczaj najbardziej znaczące w kontekście zapytania użytkownika.
 15. Nie używaj labels_combine oraz labels_vector, series_vector w zapytaniu Cypher.
 16. W odpowiedzi użyj formatownia JSON.
{{
    "description": "szczegółowe wyjaśnienie dlaczego zaproponowane zapytanie Cypher jest optymalne",
    "cypher": "zapytanie Cypher",
    "keys": "klucze w strukturze węzłów neo które uznałeś że mogą zawierać poszukiwane informacje np. Document.location_of_signing",
    "embeddings_value": [
        {{"$parametrVector": "tekst szukanego parametru"}}
    ]
}}
    """
    # print(prompt)
    response = client_gpt.chat.completions.create(
        model="o1",
        #reasoning_effort='high',
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    print(response)
    response_text = response.choices[0].message.content
    print(response_text)
    response_content = response_text.replace('```', '').replace('json', '')
    # message = json.loads(response_text)
    # print(type(message))


    # message = client.messages.create(
    #     messages=[
    #         {
    #             "role": "user",
    #             "content": prompt,
    #         }
    #     ],
    #     model="claude-3-7-sonnet-20250219",
    #     # thinking={
    #     #     "type": "enabled",
    #     #     "budget_tokens": 8000
    #     # },
    #     max_tokens=20000
    # )

    # Odpowiedź modelu jest już obiektem Pythona, nie potrzebujesz json.loads() bezpośrednio na nim
    # print(f"Pełna odpowiedź: {message}")
    # # response_content = message.content[1].text
    # response_content = message.content[0].text
    # response_content = response_content.replace('```', '').replace('json', '')
    print(response_content)
    # Jeśli odpowiedź modelu zawiera JSON, możesz go teraz sparsować
    try:
        data = json.loads(response_content)
        return data
    except json.JSONDecodeError:
        def parse_json_with_multiline_strings(json_string):
            """
            Parsuje JSON, który może zawierać wieloliniowe stringi.

            Args:
                json_string (str): String zawierający JSON do sparsowania

            Returns:
                dict: Sparsowany słownik JSON
            """
            try:
                # Próba standardowego parsowania
                return json.loads(json_string)
            except json.JSONDecodeError as e:
                print(f"Błąd parsowania JSON: {e}")

                # Sprawdzamy czy to może być problem z wieloliniowymi stringami
                if "cypher" in json_string:
                    try:
                        # Próba ręcznego wyodrębnienia i naprawy pola cypher
                        start_idx = json_string.find('"cypher": "') + len('"cypher": "')
                        end_idx = json_string.find('",', start_idx)

                        if start_idx > 0 and end_idx > start_idx:
                            # Wyodrębnij zawartość pola cypher
                            cypher_content = json_string[start_idx:end_idx]

                            # Zamień na jednoliniowy string z \n
                            cypher_fixed = cypher_content.replace('\n', '\\n')

                            # Zbuduj naprawiony JSON
                            fixed_json = (
                                    json_string[:start_idx] +
                                    cypher_fixed +
                                    json_string[end_idx:]
                            )

                            return json.loads(fixed_json)
                    except Exception as inner_e:
                        print(f"Nie udało się naprawić JSONa: {inner_e}")

                # Jeśli naprawa się nie powiodła, rzuć wyjątek
                raise ValueError(f"Nie można sparsować JSON: {e}")

        return parse_json_with_multiline_strings(response_content)


def generate_params(question, product_specification, labels):

    # Zapytanie do LLM z elastycznym podejściem
    prompt = f'''
Na podstawie pytania użytkownika i specyfikacji produktów wybierz odpowiednie parametry do zapytania bazy danych.
Pola podaj w requiredProperties. Wypełnij tylko te pola, których wartości są podane w pytaniu i które są na liście pól danego typu.
Ustaw unit na null jeżeli nie jest potrzebne.
Jeżeli użytkownik pyta o cenę podaj ją w polu price jako słownik z kluczami min, max, equal w zależności od tego jakie wartości podał użytkownik. 
W polu currency podaj walutę ceny, jeżeli nie jest podana w pytaniu to PLN. Możliwe waluty: PLN, EUR, USD.
Dostępne jednostki:
m, in, nm, mm, cm, dm, g, mg, kg, t, s, ms, us, ns, min, h, d, Wh, kWh, MWh, GWh, Hz * mm ** 3, Hz * cm ** 3, Hz * m ** 3, m ** 3 / h, m ** 3 / s, W, kW, MW, GW, VA, kVA, MVA, GVA, Hz, kHz, MHz, GHz, bit, kbit, Mbit, Gbit, B, kB, MB, GB, TB, PB, RPM, PLN, mmH2O, bit / s, kbit / s, Mbit / s, Gbit / s, B / s, kB / s, MB / s, GB / s, TB / s, lm / m ** 2, cd / m ** 2, lx, mm ** 3, cm ** 3, m ** 3, l, IOPS, lm, cd, °C, K, °F, Ah, A*s, mAh, EUR, AWG, str/min, Pa, kPa, MPa, GPa, dni, Ohm, szt, VAh, stron/min, stron/mies., ark., mmAq, szt., px, obr/min, stron, pages/min, sheets, CFM, TBW, spm, dBV/Pa, pages, son, m/s2, str/mies, arkuszy, str/mies., lanes, x mm, kWh/rok, miesiące, pages/month, Lux, max, lat, IOPs, st, arka, ark
W polu condition podaj znak warunku jeżeli wynika z pytania. Dostępne znaki: <, >, <=, >, <>.
Znak warunku <> oznacza różny i działa też dla napisów. 
Jeżeli użytkownik podał przedział wartości parametru zapisz go jako dwa oddzielne warunki używając odpowiednich znaków nierówności.
Jeżeli użytkownik podał kilka możliwych wartości danego parametru podaj je w value jako listę. Wszystkie wartości w liście zapisz tylko małymi literami.
Jeżeli użytkownik podał tylko jedną wartość dla danego parametru podaj tą wartość w value.
Nie podawaj parametrów dotyczących kompatybilności z innymi produktami!
Pytanie użytkownika:
{question}

Pola dostępne w wybranych typach produktów:
{product_specification}

Odpowiedz w formacie json:
{{
  "requiredProperties": [
    {{
      "name": "property_name",
      "value": 5,
      "unit": "kg"
      "condition": "="
    }},
    {{
      "name": "property_name1",
      "value": "wartość",
      "unit": null
      "condition": "="
    }},
    {{
      "name": "property_name2",
      "value": "wartość",
      "unit": null
      "condition": "<>"
    }},
    {{
      "name": "property_name3",
      "value": ["wartość 1", "wartość 2", "wartość 3"],
      "unit": null
      "condition": "="
    }},
    {{
      "name": "property_name4",
      "value": 50,
      "unit": in
      "condition": ">="
    }},
    {{
      "name": "property_name4",
      "value": 80,
      "unit": in
      "condition": "<="
    }},
  ],
  "price": {{
    "min": 100,
    "max": 1000,
    "equal": 500,
    "currency": "PLN"
  }}
}}
    '''

    #response_content = response_text.replace('```', '').replace('json', '')
    response_text = llm(prompt)
    params = json.loads(response_text)
    # params["productTypes"] = labels
    return params


def exec_query(params, return_parameters=False):
    price_query = ""
    price = params.get("price")
    if price:
        currency = params.get("currency", "PLN")
        if price.get("equal"):
            price_query = f'MATCH (product)-[:HAS]->(price:Price {{value: {price.get("equal")}, currency: "{currency}"}})'
        elif price.get("min") and price.get("max"):
            price_query = f'MATCH (product)-[:HAS]->(price:Price) WHERE price.value >= {price.get("min")} AND price.value <= {price.get("max")} AND price.currency = "{currency}"'
        elif price.get("min"):
            price_query = f'MATCH (product)-[:HAS]->(price:Price) WHERE price.value >= {price.get("min")} AND price.currency = "{currency}"'
        elif price.get("max"):
            price_query = f'MATCH (product)-[:HAS]->(price:Price) WHERE price.value <= {price.get("max")} AND price.currency = "{currency}"'

    cypher_query = """
MATCH (product:Product)
WHERE any(label in $productTypes WHERE label IN labels(product))
OPTIONAL MATCH (product)-[:HAS]->(prop:Property_PL) """
    cypher_query += price_query
    cypher_query += """ WITH product, collect({
  name: prop.name,
  value: prop.value,
  unit: prop.unit
}) as properties
WHERE size([reqProp IN $requiredProperties WHERE
  size([prop IN properties WHERE
    prop.name = reqProp.name AND
    (
      (apoc.meta.cypher.type(reqProp.value) IN ["LIST OF ANY", "LIST OF STRING"] AND toLower(toString(prop.value)) IN reqProp.value) OR
      (reqProp.condition = '<>' AND apoc.meta.cypher.type(reqProp.value) = 'STRING' AND toLower(toString(prop.value)) <> toLower(toString(reqProp.value))) OR
      (reqProp.condition = '<>' AND apoc.meta.cypher.type(reqProp.value) <> 'STRING' AND prop.value <> reqProp.value) OR
      (reqProp.condition = '<' AND prop.value < reqProp.value) OR
      (reqProp.condition = '>' AND prop.value > reqProp.value) OR
      (reqProp.condition = '<=' AND prop.value <= reqProp.value) OR
      (reqProp.condition = '>=' AND prop.value >= reqProp.value) OR
      ((reqProp.condition IS NULL OR reqProp.condition = '=') AND apoc.meta.cypher.type(reqProp.value) = 'STRING' AND toLower(toString(prop.value)) = toLower(toString(reqProp.value))) OR
      ((reqProp.condition IS NULL OR reqProp.condition = '=') AND apoc.meta.cypher.type(reqProp.value) = 'INTEGER' AND apoc.meta.cypher.type(prop.value) = 'STRING' AND prop.value STARTS WITH toString(reqProp.value)) OR
      ((reqProp.condition IS NULL OR reqProp.condition = '=') AND (prop.value = reqProp.value))
    ) AND
    (reqProp.unit IS NULL OR prop.unit = reqProp.unit)
  ]) > 0
]) = size($requiredProperties)
RETURN product
"""
    if return_parameters:
        cypher_query += ", properties"

    with driver.session() as session:
        result = session.run(cypher_query, params)
        records = list(result)
        if not len(records):
            print("Brak wyników")
        results = [record.data().get("product", {}) for record in records]
        for record in results:
            if record.get("nameEmbedding"):
                del record["nameEmbedding"]
            if record.get("productNumberEmbedding"):
                del record["productNumberEmbedding"]
        return results

def get_embedding(text, model="text-embedding-3-small"):
    response = client_gpt.embeddings.create(
        model=model,
        input=text
    )
    return response.data[0].embedding

def analize_query(user_query):
    prompt = f'''
Użytkownik może szukać produktów podając jego parametry lub szukać jednego lub kilku konkretnych produktów podając nazwy, numery EAN lub Part number.
Jeżeli dla jednego produktu została podana zarówno nazwa jak i EAN lub Part number to podaj tylko jedną z tych wartości z priorytetem: EAN > PN > name.
Określ jakich typów produktów może dotyczyć pytanie lub jeżeli pytanie dotyczy konkretnego produktu o podanej nazwie podaj jego nazwę.
Jeżeli pytanie dotyczy znalezienia produktu kompatybilnego z innym produktem podaj typ szukanego produktu i nazwę, EAN lub Part number produktu, z którym ma być kompatybilny.
Odpowiedz w formacie json:
{{"types": ["lodówki", "tablety"]}}
lub
{{"name": "Nazwa produktu"}}
lub jeżeli użytkownik podał kilka produktów:
{{"products": [{{"name": "Nazwa produktu X"}}, {{"EAN": "EAN produktu Y"}}, {{"PN": "Part number produktu Z"}}, ...] }}
lub jeżeli dotyczy kompatybilności:
{{"types": ["komputery", "laptopy"], "compatible_with": {{"name": "Nazwa produktu", "EAN": "EAN produktu", "PN": "Part number produktu"}} }}


Przykłady:
Pytanie: Telefon z systemem iOS
Odpowiedź: {{"types": ["telefony komórkowe"]}}
Pytanie: Telewizor 55" 4K, Wi-Fi, DP, HDMI, HDR
Odpowiedź: {{"types": ["telewizory"]}}
Pytanie: biały iPhone 13
Odpowiedź: {{"name": "biały iPhone 13"}}
Pytanie: Router Mikrotik RB4011iGS+RM
Odpowiedź: {{"name": "Router Mikrotik RB4011iGS+RM"}}
Pytanie: iPhone 15, Samsung S24, Xiaomi 15
Odpowiedź: {{"products": [{{"name": "iPhone 15"}}, {{"name": "Samsung S24"}}, {{"name": "Xiaomi 15"}}] }}
Pytanie: iPhone 15 12345678901234, Samsung S24 0987654321098, Xiaomi 15 1122334455667
Odpowiedź: {{"products": [{{"EAN": "12345678901234"}}, {{"EAN": "0987654321098"}}, {{"EAN": "1122334455667"}}] }}
Pytanie: 1234567890123, 0987654321098
Odpowiedź: {{"products": [{{"EAN": "1234567890123"}}, {{"EAN": "0987654321098"}}] }}
Pytanie: Karta pamięci do Samsung Galaxy S21
Odpowiedź: {{"types": ["karty pamięci"], "compatible_with": {{"name": "Samsung Galaxy S21"}} }}
Pytanie: Tani procesor do płyty głównej o part number 90DD02H0-M09000
Odpowiedź: {{"types": ["procesory"], "compatible_with": {{"PN": "90DD02H0-M09000"}} }}
Pytanie: Dysk SSD 512GB do laptopa Dell XPS 13
Odpowiedź: {{"types": ["dyski SSD"], "compatible_with": {{"name": "Dell XPS 13"}} }}
Pytanie: pamięć RAM 16GB do laptopa 0987654321098
Odpowiedź: {{"types": ["pamięci RAM"], "compatible_with": {{"EAN": "0987654321098"}} }}


Pytanie użytkownika:
{user_query}
    '''
    response_text = llm(prompt)
    data = json.loads(response_text)
    return data

def filter_types(user_query, types_response):
    prompt = f'''
Określ, których z podanych typów produktów może dotyczyć pytanie użytkownika.
W odpowiedzi podaj listę type_code.
Typy:
{types_response}

Pytanie użytkownika:
{user_query}

Odpowiedz w formacie json:
{{"types": ["type_code1", "type_code2"]}}
    '''

    response_text = llm(prompt)
    data = json.loads(response_text)
    return data

def check_ean(text):
    return 11 <= len(text) <= 13 and text.isdigit()

def check_pn(text):
    app = Sanic.get_app()
    try:
        response = app.ctx.NEO4J.get_product_by_pn(text)
        for record in response:
            if record.get('similarity', 0) >= 0.98:
                return record
    except Exception as e:
        logger.warning(f"PN check error: {str(e)}")
    return None

def is_action_code(text):
    return len(text) == 13 and text[9:].isdigit()

def check_action(text):
    app = Sanic.get_app()
    response = app.ctx.NEO4J.get_product_by_action_code(text)
    return response


def get_params_values(params, types):
    names = []
    for property in params.get('requiredProperties', []):
        if isinstance(property.get('value'), str) or isinstance(property.get('value'), bool):
            name = property.get('name')
            names.append(name)

    cypher_query = '''
MATCH (n)-[:HAS]->(p:Property_PL {name: $name})
WHERE any(label in labels(n) WHERE label IN $labels)
RETURN DISTINCT p.value
'''

    params_values = {}
    with driver.session() as session:
        for name in names:
            name_params = {'name': name, 'labels': types}
            logger.debug(name_params)
            result: Result = session.run(cypher_query, name_params)
            name_values = [v[0] for v in result.values()]
            logger.debug(name_values)
            params_values[name] = name_values

    return params_values


def correct_generated_params(params, params_values, user_query):
    prompt = f'''
    Na podstawie pytania użytkownika została wygenerowana lista parametrów i ich wartości. 
    Sprawdź czy wszystkie podane wartości są dostępne na liście dopuszczalnych wartości.
    Popraw wartości, które zostały wypełnione błędnie. 
    Usuń pola, których wartości nie pasują do żadnej dopuszczalnej wartości.
    Odpowiedz w formacie JSON takim jak format wejściowy.
    
    Dopuszczalne wartości parametrów:
    {params_values}

    Pytanie użytkownika:
    {user_query}
    
    Lista wygenerowanych parametry:
    {{'params': {params}}}
        '''

    response_text = llm(prompt)
    data = json.loads(response_text)
    return data.get('params')


def get_incorrect_params(params, params_values):
    properties = params.get('requiredProperties', [])
    incorrect_params = []
    for property in properties:
        if isinstance(property.get('value'), str) or isinstance(property.get('value'), bool):
            name = property.get('name')
            value = property.get('value')
            if value not in params_values.get(name, []):
                incorrect_params.append(property)
    return incorrect_params


def get_ai_answer(user_query, results):
    prompt = f'''
Jesteś chatbotem obsługi klienta w sklepie z elektroniką. Twoim zadaniem jest analizowanie zapytań klientów i odpowiadanie na nie w optymalny sposób, tak aby pomóc im w doborze odpowiedniego sprzętu. 
Odpowiedz na pytanie użytkownika na podstawie dostarczonych danych.

Pytanie użytkownika:
{user_query}

Dane:
{results}

Odpowiedz w formacie JSON:
{{"answer": ""}}
'''

    response_text = llm(prompt)
    data = json.loads(response_text)
    return data.get('answer')


def cypher_search(user_query, return_parameters=False, ai_answer=False):
    times = {}
    app = Sanic.get_app()

    try:
        start = time.time()
        data = analize_query(user_query)
        end = time.time()
        logger.debug(data)
        logger.info(f"Analiza pytania: {end - start} s")
        times["Analiza pytania"] = end - start
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas analizy pytania: {str(e)}",
            "times": times,
            "time": sum(times.values())
        }

    types_query = user_query
    if "compatible_with" in data:
        try:
            start = time.time()
            types_response = app.ctx.NEO4J.get_similar_types(types_query)
            types = [t["type_code"] for t in types_response]
            logger.debug(types)
            data["types"] = types
            end = time.time()
            logger.info(f"Wyszukiwanie typów produktów: {end - start} s")
            times["Wyszukiwanie typów produktów"] = end - start
        except Exception as e:
            return {
                "success": False,
                "message": f"Błąd podczas wyszukiwania typów produktów: {str(e)}",
                "times": times,
                "time": sum(times.values())
            }
        try:
            start = time.time()
            types = filter_types(user_query, types_response).get("types", [])
            types = [type_to_label(t) for t in types]
            data["types"] = types
            end = time.time()
            logger.debug(data)
            logger.info(f"Filtrowanie typów produktów: {end - start} s")
            times["Filtrowanie typów produktów"] = end - start
        except Exception as e:
            return {
                "success": False,
                "message": f"Błąd podczas filtrowania typów: {str(e)}",
                "times": times,
                "time": sum(times.values())
            }

        try:
            start = time.time()
            specifications = {}
            for t in types:
                # print(f"Pobieranie specyfikacji dla typu: {t}")
                specification = src.services.product_specification.get_product_specification(t)
                if specification:
                    specification = src.services.product_specification.filter_language(specification, "PL")
                    specifications[type_to_label(t)] = specification
            end = time.time()
            logger.info(f"Pobieranie specyfikacji: {end - start} s")
            times["Pobieranie specyfikacji"] = end - start
            logger.info(specifications)
        except Exception as e:
            return {
                "success": False,
                "message": f"Błąd podczas pobierania specyfikacji produktów: {str(e)}",
                "times": times,
                "types": types_response,
                "time": sum(times.values())
            }

        try:
            start = time.time()
            params = generate_params(user_query, specifications, types)
            end = time.time()
            logger.info(f"Generowanie parametrów cypher: {end - start} s")
            times["Generowanie parametrów cypher"] = end - start
        except Exception as e:
            return {
                "success": False,
                "message": f"Błąd podczas generowania parametrów Cypher: {str(e)}",
                "times": times,
                "types": types_response,
                "time": sum(times.values())
            }
        start = time.time()
        params_values = get_params_values(params, types)
        end = time.time()
        logger.info(f"Znalezienie możliwych wartości parametrów: {end - start} s")
        times["Znalezienie możliwych wartości parametrów"] = end - start
        logger.info(params_values)

        if params_values:
            incorrect_params = get_incorrect_params(params, params_values)
            logger.info(f"incorrect_params: {incorrect_params}")
            if incorrect_params:
                original_params = params
                start = time.time()
                corrected_params = correct_generated_params(incorrect_params, params_values, user_query)
                logger.info(f"corrected_params: {corrected_params}")
                corrected_params_dict = {}
                for param in corrected_params:
                    corrected_params_dict[param.get("name")] = param.get("value")
                for param in params.get('requiredProperties', []):
                    if param.get('name') in corrected_params_dict:
                        param['value'] = corrected_params_dict[param.get('name')]
                end = time.time()
                logger.info(f"Poprawienie parametrów: {end - start} s")
                times["Poprawienie parametrów"] = end - start
                logger.info(params)

        # dodanie informacji o typach, które pyta cypher
        params["productTypes"] = types


        logger.info(f"Kompatybilność z produktem: {data['compatible_with']}")
        start = time.time()
        compatibility_response, types = compatibility_search(data, params)
        end = time.time()
        logger.info(f"Wyszukiwanie kompatybilnych produktów: {end - start} s")
        times["Wyszukiwanie kompatybilnych produktów"] = end - start
        return {
            "success": True,
            "search_type": "compatibility",
            "compatible_with": data["compatible_with"],
            "results": compatibility_response,
            "types": types,
            "times": times,
            "time": sum(times.values())
        }
    if "types" in data:
        types = data["types"]
        if not types:
            return None
        types_query = types[0]
    elif "name" in data:
        name = data["name"]
        logger.info(f"Wyszukiwanie nazwy: {name}")
        start = time.time()
        name_response = app.ctx.NEO4J.get_product_by_name_vector(name, n=50, with_parameters=return_parameters, similarity=0.8)
        end = time.time()
        logger.info(f"Wyszukiwanie nazwy: {end - start} s")
        times["Wyszukiwanie nazwy"] = end - start

        answer = None
        if ai_answer:
            start = time.time()
            answer = get_ai_answer(user_query, name_response)
            end = time.time()
            logger.info(f"Odpowiedź AI: {end - start} s")
            times["Odpowiedź AI"] = end - start

        return {
            "success": True,
            "search_type": "name",
            "message": answer if answer else "",
            "results": name_response,
            "times": times,
            "time": sum(times.values())
        }
    elif "products" in data:
        products = data["products"]
        logger.info(f"Wyszukiwanie produktów: {products}")
        names = []
        eans = []
        pns = []
        for product in products:
            if "name" in product:
                names.append(product["name"])
            if "EAN" in product:
                eans.append(product["EAN"])
            if "PN" in product:
                pns.append(product["PN"])
        start = time.time()
        responses = []
        alternative_search = []
        for name in names:
            response = app.ctx.NEO4J.get_product_by_name(name, 1, with_parameters=return_parameters, similarity=0.97)
            if response:
                responses.append(response[0])
            else:
                alternative_search.append(name)
        for ean in eans:
            if return_parameters:
                ean_response = app.ctx.NEO4J.get_product_with_parameters(ean)
            else:
                ean_response = app.ctx.NEO4J.get_product(ean)
            responses.append(ean_response)
        for pn in pns:
            pn_response = app.ctx.NEO4J.get_product_by_pn(pn, with_parameters=return_parameters)
            if pn_response:
                responses.append(pn_response[0])
        end = time.time()
        logger.info(f"Wyszukiwanie produktów: {end - start} s")
        times["Wyszukiwanie produktów"] = end - start

        if alternative_search:
            start = time.time()
            alternative_search_response = search_index(alternative_search)
            logger.debug(alternative_search_response)
            for act_code in alternative_search_response:
                act_code_response = check_action(act_code)
                if act_code_response:
                    responses.append(act_code)
                else:
                    logger.warning(f"{act_code} not found")

            end = time.time()
            logger.info(f"Alternatywne szukanie produktów: {end - start} s")
            times["Alternatywne szukanie produktów"] = end - start

        return {
            "success": True,
            "search_type": "products",
            "results": responses,
            "times": times,
            "time": sum(times.values())
        }
    else:
        return {
            "success": False,
            "message": f"Błąd podczas analizy pytania",
            "times": times,
            "time": sum(times.values())
        }


    # Krok 1: Wyszukanie typów produktów
    try:
        start = time.time()
        types_response = app.ctx.NEO4J.get_similar_types(types_query)
        types = [t["type_code"] for t in types_response]
        end = time.time()
        logger.info(f"Wyszukiwanie typów produktów: {end - start} s")
        times["Wyszukiwanie typów produktów"] = end - start
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas wyszukiwania typów produktów: {str(e)}",
            "times": times,
            "time": sum(times.values())
        }


    #Krok 2: Filtrowanie typów produktów
    try:
        start = time.time()
        data = filter_types(user_query, types_response)
        types = data.get("types", [])
        types = [type_to_label(t) for t in types]
        end = time.time()
        logger.debug(data)
        logger.info(f"Filtrowanie typów produktów: {end - start} s")
        times["Filtrowanie typów produktów"] = end - start
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas filtrowania typów: {str(e)}",
            "times": times,
            "time": sum(times.values())
        }

    # Krok 3: Pobierz formatki wybranych typów produktów
    try:
        start = time.time()
        specifications = {}
        for t in types:
            # print(f"Pobieranie specyfikacji dla typu: {t}")
            specification = src.services.product_specification.get_product_specification(t)
            if specification:
                specification = src.services.product_specification.filter_language(specification, "PL")
                specifications[type_to_label(t)] = specification
        end = time.time()
        logger.info(f"Pobieranie specyfikacji: {end - start} s")
        times["Pobieranie specyfikacji"] = end - start
        logger.info(specifications)
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas pobierania specyfikacji produktów: {str(e)}",
            "times": times,
            "types": types_response,
            "time": sum(times.values())
        }

    try:
        start = time.time()
        params = generate_params(user_query, specifications, types)
        end = time.time()
        logger.info(f"Generowanie parametrów cypher: {end - start} s")
        times["Generowanie parametrów cypher"] = end - start
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas generowania parametrów Cypher: {str(e)}",
            "times": times,
            "types": types_response,
            "time": sum(times.values())
        }
    start = time.time()
    params_values = get_params_values(params, types)
    end = time.time()
    logger.info(f"Znalezienie możliwych wartości parametrów: {end - start} s")
    times["Znalezienie możliwych wartości parametrów"] = end - start
    logger.info(params_values)

    if params_values:
        incorrect_params = get_incorrect_params(params, params_values)
        logger.info(f"incorrect_params: {incorrect_params}")
        if incorrect_params:
            original_params = params
            start = time.time()
            corrected_params = correct_generated_params(incorrect_params, params_values, user_query)
            logger.info(f"corrected_params: {corrected_params}")
            corrected_params_dict = {}
            for param in corrected_params:
                corrected_params_dict[param.get("name")] = param.get("value")
            for param in params.get('requiredProperties', []):
                if param.get('name') in corrected_params_dict:
                    param['value'] = corrected_params_dict[param.get('name')]
            end = time.time()
            logger.info(f"Poprawienie parametrów: {end - start} s")
            times["Poprawienie parametrów"] = end - start
            logger.info(params)

    #dodanie informacji o typach, które pyta cypher
    params["productTypes"] = types

    try:
        start = time.time()
        results = exec_query(params, return_parameters)
        end = time.time()
        logger.info(f"Odpytanie bazy: {end - start} s")
        times["Odpytanie bazy"] = end - start
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas odpytania bazy: {str(e)}",
            "params": params,
            "times": times,
            "types": types_response,
            "time": sum(times.values())
        }

    answer = None
    if ai_answer:
        start = time.time()
        answer = get_ai_answer(user_query, results)
        end = time.time()
        logger.info(f"Odpowiedź AI: {end - start} s")
        times["Odpowiedź AI"] = end - start

    return {
        "success": True,
        "search_type": "parameters",
        "message": answer if answer else "",
        "results": results,
        "params": params,
        "times": times,
        "types": types_response,
        "types_query": types_query,
        "time": sum(times.values())
    }


def type_to_label(t: str):
    return t.replace("-", "_")


def compatibility_search(data, params=None):
    logger.debug(data)
    app = Sanic.get_app()
    types = data.get("types", [])
    compatible_with = data.get("compatible_with", {})
    if compatible_with.get("PN"):
        pn = compatible_with["PN"]
        response = app.ctx.NEO4J.get_compatible_products(types=types, pn=pn)
        logger.debug(response)
        return response, types
    ean = ""
    if compatible_with.get("name"):
        name = compatible_with["name"]
        start = time.time()
        name_response = app.ctx.NEO4J.get_product_by_name_vector(name, n=1, similarity=0.9)
        logger.info(f"Name response: {name_response}")
        if name_response:
            ean = name_response[0].get("EAN")
        end = time.time()
        logger.info(f"Wyszukiwanie nazwy: {end - start} s")
    elif compatible_with.get("EAN"):
        ean = compatible_with["EAN"]
    else:
        logger.error("Brak informacji o kompatybilności w danych wejściowych")
        return [], []
    logger.info(f"EAN: {ean}")
    if params:
        response = app.ctx.NEO4J.get_compatible_products_filtered_by_price(types=types, ean=ean, params=params)
        eans = [cp['EAN'] for cp in response if cp.get('EAN')]
        logger.info(f"EANs: {eans}")
        if eans and params.get("requiredProperties"):
            response = app.ctx.NEO4J.filter_compatible_products(eans=eans, params=params)

    else:
        response = app.ctx.NEO4J.get_compatible_products(types=types, ean=ean)
    logger.debug(response)
    return response, types




def simple_search(user_query):
    times = {}
    app = Sanic.get_app()

    # Sprawdź EAN
    ean_response = None
    start = time.time()
    if check_ean(user_query):
        logger.info(f"Szukanie EAN: {user_query}")
        ean_response = app.ctx.NEO4J.get_product(user_query)
    end = time.time()
    times["Wyszukiwanie EAN"] = end - start
    if ean_response:
        return {
            "success": True,
            "search_type": "EAN",
            "results": ean_response,
            "times": times,
            "time": sum(times.values())
        }


    # Sprawdź Action code
    if is_action_code(user_query):
        start = time.time()
        action_response = check_action(user_query)
        end = time.time()
        times["Wyszukiwanie Action"] = end - start
        return {
            "success": True,
            "search_type": "action",
            "results": action_response,
            "times": times,
            "time": sum(times.values())
        }

    start = time.time()
    # Sprawdź PN
    logger.info(f"Szukanie PN: {user_query}")
    pn_response = check_pn(user_query)

    end = time.time()
    times["Wyszukiwanie PN"] = end - start
    logger.info(pn_response)
    if pn_response:
        return {
            "success": True,
            "search_type": "pn",
            "results": pn_response,
            "times": times,
            "time": sum(times.values())
        }

    start = time.time()
    # Szukaj nazwy
    logger.info(f"Szukaj nazwy: {user_query}")
    name_response = app.ctx.NEO4J.get_product_by_name(user_query, n=40, with_parameters=False, similarity=0.5)

    end = time.time()
    times["Wyszukiwanie nazwy"] = end - start
    logger.info(name_response)
    if name_response:
        return {
            "success": True,
            "search_type": "name",
            "results": name_response,
            "times": times,
            "time": sum(times.values())
        }

    return {
        "success": False,
        "times": times,
        "time": sum(times.values())
    }

if __name__ == "__main__":

    # client = openai.OpenAI(
    #    api_key="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")


    task = "Telewizor LCD z ekranem 55 cali"
    _results = cypher_search(task)
    print(f"Status: {'Sukces' if _results.get('success', False) else 'Błąd'}")
    print(f"Wiadomość: {_results.get('message', '')}")