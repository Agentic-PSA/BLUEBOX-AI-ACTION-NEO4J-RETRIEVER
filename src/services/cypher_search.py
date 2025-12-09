import os

import httpx
from httpx import Client
import uuid
import time
import json
from py2neo import Graph
import openai
import google.generativeai as genai
from neo4j import GraphDatabase, Result
from sanic import Sanic
from sanic.log import logger
from copy import deepcopy

import src.services.product_specification
import src.services.db_schema

# client = Anthropic(
#     api_key="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",
#     # This is the default and can be omitted
# )
uri = f"neo4j://{os.environ.get('NEO4J_HOST')}:{os.environ.get('NEO4J_PORT')}"
driver = GraphDatabase.driver(uri, auth=(os.environ.get("NEO4J_USER"), os.environ.get("NEO4J_PASSWORD")))

client_gpt = openai.OpenAI(
   api_key="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")

def clean_json(text: str):
    if text is None:
        return ""
    text = text.strip()
    # usuń ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        # usuń ewentualny prefiks json
        text = text.replace("json", "", 1).strip()
    return text

def llm(prompt, model="gpt-4.1"):
    #return llm_gemini(prompt)
    print("services cypher_search llm")
    print("-------------")
    print(model)
    print(prompt)
    print("-------------")
    response = client_gpt.chat.completions.create(
        model=model,
        # reasoning_effort='high',
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    logger.debug(response)
    response_text = response.choices[0].message.content
    logger.debug(response_text)
    # print("-------------")
    # print(response_text)
    # print("-------------")
    return response_text

def llm_gemini(prompt):
    print("services cypher_search llm gemini")
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "Brak klucza Google Gemini. Podaj go jako parametr lub ustaw zmienną środowiskową GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    # print('------------------')
    # for m in genai.list_models():
    #     print(m.name, m.supported_generation_methods)
    # print('------------------')
    # exit()
    model = genai.GenerativeModel("models/gemini-2.5-pro")
    response = model.generate_content(
        prompt,
        safety_settings=None,  # opcjonalnie usunięcie filtrów bezpieczeństwa
        generation_config={
            "temperature": 0.0,
            "max_output_tokens": 30000
        }
    )
    raw_text = response.text
    cleaned = clean_json(raw_text)    
    # print("-------------")
    # print(cleaned)
    # print("-------------")
    return cleaned


def search_index(names=[]):
    print("services cypher_search search_index")
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
    print("services cypher_search search_group")
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
    print("services cypher_search generate_simple_cypher_query_with_llm")
    # Przygotuj dane jako tekst
    # schema_text = get_schema_text(db_schema)
    # print(schema_text)
    # print(json.dumps(specifications, ensure_ascii=False, indent=2))


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
        #model="gpt-4.1",
        #reasoning_effort='high',
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    print('----------response-----------')
    print(response)
    response_text = response.choices[0].message.content
    print('----------response text-----------')
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




def merge_sections(data):
    merged = {}

    for category, sections in data.items():
        for section in sections:
            section_name = section["section_name"]

            # jeśli pierwszy raz widzimy sekcję, kopiujemy ją w całości
            if section_name not in merged:
                merged[section_name] = deepcopy(section)
                continue

            # scalanie atrybutów
            existing_attrs = merged[section_name]["attributes"]

            for attr in section["attributes"]:
                attr_name = next(iter(attr))
                attr_value = attr[attr_name]

                # znajdź istniejący atrybut
                existing = next((a for a in existing_attrs if attr_name in a), None)

                if not existing:
                    # jeśli nie ma, dodaj nowy
                    existing_attrs.append(deepcopy(attr))
                    continue

                # scalanie istniejącego
                existing_value = existing[attr_name]

                # scalanie słowników (unit/min/max itp.)
                for key, val in attr_value.items():
                    if key == "values":
                        # scalanie wartości + usunięcie duplikatów + normalizacja spacji
                        combined = set(v.strip() for v in existing_value.get("values", []) + val)
                        existing_value["values"] = list(combined)
                    else:
                        # inne pola nadpisujemy lub dodajemy
                        existing_value[key] = val

    # zwróć listę sekcji
    return list(merged.values())


def generate_params(question, product_specification):
    print("services cypher_search generate_params")

    # Zapytanie do LLM z elastycznym podejściem
    prompt = f'''
Na podstawie pytania użytkownika i specyfikacji produktów wybierz odpowiednie parametry do zapytania bazy danych.

1. Wypełnij pole "requiredProperties":
   - Tylko te pola, których wartości są podane w pytaniu i które występują w specyfikacji dla danego typu produktu.
   - Ustaw "unit" na null, jeśli nie jest potrzebne.
   - W polu "value":
     * jeśli użytkownik podał kilka wartości → lista,
     * jeśli jedną wartość → pojedyncza wartość,
     * liczby z przecinkiem zamień na kropkę.
   - W polu "condition" ustaw znak warunku zgodnie z pytaniem (=, <, >, <=, >=, <>). 
   - Nie wypełniaj pól niezwiązanych bezpośrednio z produktem (np. marka, model, producent).
   - Jeśli użytkownik pyta o parametr, który w specyfikacji jest rozbity na kilka osobnych atrybutów powiązanych, dodaj wszystkie te powiązane atrybuty do requiredProperties

2. Pomijaj parametry wynikające z nazwy kategorii
   - Nie dodawaj do requiredProperties parametrów, których wartość jest już zawarta w nazwie kategorii produktu.
   - Jeśli jednak dana cecha nie występuje w nazwie kategorii, ale występuje:
    * w pytaniu użytkownika lub
    * w specyfikacji produktu jako możliwa opcja
      → to parametr wolno dodać.

3. Wypełnij pole "price" (jeśli użytkownik pyta o cenę):
   - Słownik z kluczami min, max, equal w zależności od tego, jakie wartości podano.
   - Pole "currency" ustaw na podaną walutę lub PLN.

4. Jednostki możliwe: m, in, nm, mm, cm, dm, g, mg, kg, t, s, ms, us, ns, min, h, d, Wh, kWh, MWh, GWh, Hz * mm ** 3, Hz * cm ** 3, Hz * m ** 3, m ** 3 / h, m ** 3 / s, W, kW, MW, GW, VA, kVA, MVA, GVA, Hz, kHz, MHz, GHz, bit, kbit, Mbit, Gbit, B, kB, MB, GB, TB, PB, RPM, PLN, mmH2O, bit / s, kbit / s, Mbit / s, Gbit / s, B / s, kB / s, MB / s, GB / s, TB / s, lm / m ** 2, cd / m ** 2, lx, mm ** 3, cm ** 3, m ** 3, l, IOPS, lm, cd, °C, K, °F, Ah, A*s, mAh, EUR, AWG, str/min, Pa, kPa, MPa, GPa, dni, Ohm, szt, VAh, stron/min, stron/mies., ark., mmAq, szt., px, obr/min, stron, pages/min, sheets, CFM, TBW, spm, dBV/Pa, pages, son, m/s2, str/mies, arkuszy, str/mies., lanes, x mm, kWh/rok, miesiące, pages/month, Lux, max, lat, IOPs, st, arka, ark

5. Wartości atrybutów w specyfikacji:
   - Jeśli atrybut ma klucz "unit" → podaj wartość liczbową i jednostkę
   - Jeśli atrybut ma klucz "values" → wybierz wszystkie pasujące wartości z listy (nie poprawiaj wielkości liter, błędów, odmiany ani stylu - tekst ma zostać skopiowany 1:1, nawet jeśli wygląda niepoprawnie)
   - Jeśli atrybut ma klucz "values", a nazwa atrybutu lub wartości wskazują na dane zakresowe → pomiń go

6. Znajdź **wszystkie możliwe powiązania OR** między **znalezionymi** atrybutami:
   - Podobieństwo nazw atrybutów (np. „Specyficzne potrzeby zwierzęcia” ↔ „Dodatkowe cechy”)
   - Podobieństwo wartości (np. wspólne słowa kluczowe: „nadwaga”, „utrzymanie wagi”)
   - Dla każdego atrybutu wstaw pole `"or_with"`: lista nazw powiązanych atrybutów które są w requiredProperties. Jeśli brak powiązań → pusty array.
   - Powiązania OR twórz WYŁĄCZNIE pomiędzy atrybutami, które znalazły się w requiredProperties. 
   - Nigdy nie analizuj ani nie wykorzystuj atrybutów, które nie zostały wybrane.

7. Jeśli ten sam atrybut w specyfikacji występuje kilka razy w różnych jednostkach (np. kg i g) ale pod tą samą nazwą:
   ZASADA JEDNEGO PARAMETRU (OBOWIĄZKOWA — NIE WOLNO NARUSZYĆ):
   - Traktuj je jako JEDEN parametr i wybierz tylko jeden wariant.
     * Jeśli użytkownik poda jednostkę → wybierz wariant w tej jednostce.
     * Jeśli użytkownik nie poda jednostki → wybierz jednostkę wyższą w hierarchii (np. kg > g, m > cm > mm).
   - Nigdy nie dodawaj więcej niż jednego wariantu tego parametru do requiredProperties.
   - Nigdy nie twórz OR pomiędzy wariantami tego samego parametru (różne jednostki lub formaty nazwy).
     OR może łączyć wyłącznie różne parametry, nigdy alternatywne wersje jednego parametru.

8. W polu advice wpisz informację, czy wszystko było dla Ciebie jasne, oraz co moglibyśmy poprawić w podpowiedzi i/lub danych wejściowych.

Pytanie użytkownika:
{question}

Specyfikacja produktu:
{merge_sections(product_specification)}

Odpowiedz w poprawnym formacie JSON:
{{
  "requiredProperties": [
    {{
      "name": "property_name",
      "value": 5,
      "unit": "kg",
      "condition": "=",
      "or_with": ["property_name_2", "property_name_4"]
    }},
    {{
      "name": "property_name1",
      "value": "wartość",
      "unit": null,
      "condition": "=",
      "or_with": []
    }}
  ],
  "price": {{
    "min": 100,
    "max": 1000,
    "equal": 500,
    "currency": "PLN"
  }},
  "advice": "Twoja sugestia na poprawienie zapytania"
}}
    '''

    print('PROMPT LEN: ', len(prompt))
    #print(json.dumps(product_specification, indent=4, ensure_ascii=False))
    # print(product_specification)
    #response_content = response_text.replace('```', '').replace('json', '')
    #print('AAAAAAA___________________AAAAAAAAAAAAAAAA')
    #print(prompt)
    #print('BBBBBBBBBB________________________BBBBBBBBBBBBBBBBBBBBBBB')
    response_text = llm(prompt)
    params = json.loads(response_text)
    #print('----------------response--------------')
    #print(params)
    # params["productTypes"] = labels
    return params



def generate_params_OLD(question, product_specification, labels):
    print("services cypher_search generate_params")

    # Zapytanie do LLM z elastycznym podejściem
    prompt = f'''
Na podstawie pytania użytkownika i specyfikacji produktów wybierz odpowiednie parametry do zapytania bazy danych.
Pola podaj w requiredProperties. Wypełnij tylko te pola, których wartości są podane w pytaniu i które są na liście pól danego typu.
Ustaw unit na null jeżeli nie jest potrzebne.
Jeżeli użytkownik pyta o cenę podaj ją w polu price jako słownik z kluczami min, max, equal w zależności od tego jakie wartości podał użytkownik. 
W polu currency podaj walutę ceny, jeżeli nie jest podana w pytaniu to PLN. Możliwe waluty: PLN, EUR, USD.
Dostępne jednostki:
m, in, nm, mm, cm, dm, g, mg, kg, t, s, ms, us, ns, min, h, d, Wh, kWh, MWh, GWh, Hz * mm ** 3, Hz * cm ** 3, Hz * m ** 3, m ** 3 / h, m ** 3 / s, W, kW, MW, GW, VA, kVA, MVA, GVA, Hz, kHz, MHz, GHz, bit, kbit, Mbit, Gbit, B, kB, MB, GB, TB, PB, RPM, PLN, mmH2O, bit / s, kbit / s, Mbit / s, Gbit / s, B / s, kB / s, MB / s, GB / s, TB / s, lm / m ** 2, cd / m ** 2, lx, mm ** 3, cm ** 3, m ** 3, l, IOPS, lm, cd, °C, K, °F, Ah, A*s, mAh, EUR, AWG, str/min, Pa, kPa, MPa, GPa, dni, Ohm, szt, VAh, stron/min, stron/mies., ark., mmAq, szt., px, obr/min, stron, pages/min, sheets, CFM, TBW, spm, dBV/Pa, pages, son, m/s2, str/mies, arkuszy, str/mies., lanes, x mm, kWh/rok, miesiące, pages/month, Lux, max, lat, IOPs, st, arka, ark
W polu condition podaj znak warunku jeżeli wynika z pytania. Dostępne znaki: =, <, >, <=, >, <>.
Znak warunku <> oznacza różny i działa też dla napisów. 
Jeżeli użytkownik podał przedział wartości parametru zapisz go jako dwa oddzielne warunki używając odpowiednich znaków nierówności.
Jeżeli użytkownik podał kilka możliwych wartości danego parametru podaj je w value jako listę.
Jeżeli użytkownik podał tylko jedną wartość dla danego parametru podaj tą wartość w value.
Wypełnij tylko parametry, które dotyczą bezpośrednio szukanego produktu, a nie jego zgodności z innymi produktami. Pomiń parametry takie jak marka, model, producent, kompatybilność, itp.

Wartości liczbowe mogą być podane z przecinkiem lub kropką, ale w odpowiedzi użyj kropki jako separatora dziesiętnego.
Przykłady:
55,3 metrów - value: 55.3 unit: "m"
0,7 l - value: 0.7 unit: "l"
1,00009 GWh - value: 1.00009 unit: "GWh"

Specyfikacji produktu jest postaci:
{{
    "Nazwa typu":
        [
            {{
                "section_name": "Nazwa sekcji",
                "attributes":
                    [
                        {{
                            "Nazwa atrybutu":
                                {{
                                    "unit": "jednostka"
                                    "values" : ["wartość 1", "wartość 2", "wartość N"]

                                }}
                        }}
                    ]
            }}
        ]
}}

W specyfikacji produktu, dla każdego atrybutu występuje klucz unit lub values.
Jeśli występuje klucz unit, należy dobrać wartość.
Jeśli wystepuje klucz values, należy wybrać z dostępnych opcji (zachowaj dokładne dopasowanie, nie zmieniaj wielkości liter)
W otrzymanych wynikach znajdź **wszystkie atrybuty, które mogą być traktowane zamiennie (OR)**, na podstawie:
1. **Podobieństwa nazw** atrybutów (np. „Specyficzne potrzeby zwierzęcia” i „Dodatkowe cechy” mogą być powiązane, jeśli odnoszą się do tego samego zagadnienia)
2. **Podobieństwa wartości** atrybutów (np. jeśli wartości zawierają te same słowa kluczowe, np. „nadwaga”, „utrzymanie wagi”).
- Dla każdego atrybutu dodaj pole `"or_with"`: lista nazw innych atrybutów, z którymi może być powiązany.  
- Jeśli nie ma powiązań, pole `"or_with"` powinno być pustą tablicą 
- Nie dodawaj powiązań, które nie mają sensu.  


Pytanie użytkownika:
{question}

Pola dostępne w wybranych typach produktów (specyfikacja produktu):
{product_specification}

Odpowiedz w formacie json:
{{
  "requiredProperties": [
    {{
      "name": "property_name",
      "value": 5,
      "unit": "kg",
      "condition": "=",
      "or_with": ["property_name_2", "property_name_4"]
    }},
    {{
      "name": "property_name1",
      "value": "wartość",
      "unit": null,
      "condition": "=",
      "or_with": []
    }},
    {{
      "name": "property_name2",
      "value": "wartość",
      "unit": null,
      "condition": "<>",
      "or_with": ["property_name"]
    }},
    {{
      "name": "property_name3",
      "value": ["wartość 1", "wartość 2", "wartość 3"],
      "unit": null,
      "condition": "=",
      "or_with": []
    }},
    {{
      "name": "property_name4",
      "value": 50,
      "unit": "in",
      "condition": ">=",
      "or_with": ["property_name"]
    }},
    {{
      "name": "property_name5",
      "value": 0.004,
      "unit": "GWh",
      "condition": "<=",
      "or_with": []
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
    print('PROMPT LEN: ', len(prompt))
    # print(product_specification)
    #response_content = response_text.replace('```', '').replace('json', '')
    #print('AAAAAAA___________________AAAAAAAAAAAAAAAA')
    #print(prompt)
    #print('BBBBBBBBBB________________________BBBBBBBBBBBBBBBBBBBBBBB')
    response_text = llm(prompt)
    params = json.loads(response_text)
    #print('----------------response--------------')
    #print(params)
    # params["productTypes"] = labels
    return params


def exec_query_ORYG(params, return_parameters=False):
    print("services cypher_search exec_query")
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
    toLower(prop.name) = toLower(reqProp.name)
 AND
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

    print(cypher_query)
    print(params)

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














def build_or_groups(required_props):
    """
    Tworzy listę grup:
    - Każda grupa z połączeń OR -> lista nazw właściwości
    - Właściwości bez połączeń OR -> grupa jednoelementowa (AND)
    """
    groups = []
    visited = set()

    for prop in required_props:
        name = prop["name"]
        if name in visited:
            continue

        or_with = prop.get("or_with", [])
        if not or_with:  # brak powiązań → osobna grupa
            groups.append([name])
            visited.add(name)
            continue

        # budujemy grupę OR
        group = {name}
        stack = [prop]
        while stack:
            p = stack.pop()
            visited.add(p["name"])
            for other in required_props:
                other_name = other["name"]
                if other_name in visited:
                    continue
                if other_name in p.get("or_with", []) or p["name"] in other.get("or_with", []):
                    group.add(other_name)
                    stack.append(other)
                    visited.add(other_name) #usun, jesli ma byc relacja dwustronna
        groups.append(list(group))
    return groups


def exec_query(params, return_parameters=False):
    print("services cypher_search exec_query")
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

    required_props = params.get("requiredProperties", [])
    or_groups = build_or_groups(required_props)  # automatycznie generuje OR-grupy

    cypher_query = """
MATCH (product:Product)
WHERE any(label in $productTypes WHERE label IN labels(product))
OPTIONAL MATCH (product)-[:HAS]->(prop:Property_PL)
"""
    cypher_query += price_query
    cypher_query += """
WITH product, collect({
  name: prop.name,
  value: prop.value,
  unit: prop.unit
}) AS properties

WHERE size([
  group IN $orGroups WHERE
    size([
      reqProp IN $requiredProperties WHERE
        reqProp.name IN group AND size([
          prop IN properties WHERE
            toLower(prop.name) = toLower(reqProp.name) AND
            (
              (apoc.meta.cypher.type(reqProp.value) IN ["LIST OF ANY", "LIST OF STRING"] AND toString(prop.value) IN reqProp.value) OR
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
    ]) > 0
]) = size($orGroups)
RETURN product
"""
    if return_parameters:
        cypher_query += ", properties"

    # wysyłamy parametry do Neo4j
    neo4j_params = params.copy()
    neo4j_params["orGroups"] = or_groups
    #print(cypher_query)
    print(neo4j_params)
    with driver.session() as session:
        result = session.run(cypher_query, neo4j_params)
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
    print("services cypher_search get_embedding")
    response = client_gpt.embeddings.create(
        model=model,
        input=text
    )
    return response.data[0].embedding

def analize_query(user_query):
    print("services cypher_search analize_query")
    prompt = f'''
Użytkownik może szukać produktów podając jego parametry lub szukać jednego lub kilku konkretnych produktów podając nazwy, numery EAN lub Part number.
Jeżeli dla jednego produktu została podana zarówno nazwa jak i EAN, kod Action lub Part number to podaj tylko jedną z tych wartości z priorytetem: EAN > Kod Action > PN > name.
Kod Action to 13-znakowy kod identyfikujący produkt. Najczęściej składa się z 9 liter i 4 cyfr, ale może też być inny. Np. zawierać same litery.
Określ jakich typów produktów może dotyczyć pytanie lub jeżeli pytanie dotyczy konkretnego produktu o podanej nazwie podaj jego nazwę.
Jeżeli pytanie dotyczy znalezienia produktu kompatybilnego z innym produktem podaj typ szukanego produktu i nazwę, EAN, Kod Action, lub Part number produktu, z którym ma być kompatybilny.
W pytaniach o kompatybilność określ czy pytanie zawiera parametry szukanego produktu lub ograniczenia ceny czy tylko typ i produkt, z którym ma być kompatybilny. 
Jeżeli zawiera parametry lub ograniczenia ceny to podaj pole params jako true, jeżeli podany jest tylko kompatybilny produkt to false.
Odpowiedz w formacie json:
{{"types": ["lodówki"]}}
lub
{{"name": "Nazwa produktu"}}
lub jeżeli użytkownik podał kilka produktów:
{{"products": [{{"name": "Nazwa produktu X"}}, {{"EAN": "EAN produktu Y"}}, {{"PN": "Part number produktu Z"}}, ...] }}
lub jeżeli dotyczy kompatybilności:
{{"types": ["komputery", "laptopy"], "compatible_with": {{"name": "Nazwa produktu", "EAN": "EAN produktu", "PN": "Part number produktu", "action": "Kod action"}} "params":true/false }}


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
Odpowiedź: {{"types": ["karty pamięci"], "compatible_with": {{"name": "Samsung Galaxy S21"}}, "params": false}}
Pytanie: Procesor do płyty głównej o part number 90DD02H0-M09000
Odpowiedź: {{"types": ["procesory"], "compatible_with": {{"PN": "90DD02H0-M09000"}}, "params": false}}
Pytanie: Dysk SSD 512GB do laptopa Dell XPS 13
Odpowiedź: {{"types": ["dyski SSD"], "compatible_with": {{"name": "Dell XPS 13"}}, "params": true}}
Pytanie: pamięć RAM 16GB do laptopa 0987654321098
Odpowiedź: {{"types": ["pamięci RAM"], "compatible_with": {{"EAN": "0987654321098"}}, "params": true}}
Pytanie: torba do laptopa 0987654321098 tańcza niż 200zł
Odpowiedź: {{"types": ["torby do laptopa"], "compatible_with": {{"EAN": "0987654321098"}}, "params": true}}


Pytanie użytkownika:
{user_query}
    '''
    print(prompt)
    response_text = llm(prompt)
    data = json.loads(response_text)
    print('--------------response--------------')
    print(data)
    return data

def filter_types(user_query, types_response):
    print("services cypher_search filter_types")
    prompt = f'''
Określ, których z podanych typów produktów może dotyczyć pytanie użytkownika.
W odpowiedzi podaj listę type_code.
Musisz wybrać co najmniej jeden type_code.
Typy:
{types_response}

Pytanie użytkownika:
{user_query}

Odpowiedz w formacie json:
{{"types": ["type_code1", "type_code2"]}}
    '''
    print(prompt)
    response_text = llm(prompt)
    data = json.loads(response_text)
    return data

def check_ean(text):
    print("services cypher_search check_ean")
    return 11 <= len(text) <= 13 and text.isdigit()

def check_pn(text):
    print("services cypher_search check_pn")
    if len(text) > 20:
        return None
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
    print("services cypher_search is_action_code")
    return len(text) == 13 #and text[9:].isdigit()

def check_action(text):
    print("services cypher_search check_action")
    app = Sanic.get_app()
    response = app.ctx.NEO4J.get_product_by_action_code(text)
    return response


def get_params_values(params, types):
    print("services cypher_search get_params_values")
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
    print("services cypher_search correct_generated_params")
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

    print(prompt)
    response_text = llm(prompt)
    data = json.loads(response_text)
    return data.get('params')


def get_incorrect_params(params, params_values):
    print("services cypher_search get_incorrect_params")
    #print(params)
    #print(params_values)
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
    print("services cypher_search get_ai_answer")
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


def filter_none_params(params_values):
    print("services cypher_search filter_none_params")
    if 'requiredProperties' in params_values:
        params_values['requiredProperties'] = [
            param for param in params_values['requiredProperties']
            if not ('value' in param and param['value'] is None)
        ]
        for param in params_values['requiredProperties']:
            value = param.get('value')
            if isinstance(value, list) and len(value) == 1:
                param['value'] = value[0]

    return params_values


def cypher_search(user_query, return_parameters=False, ai_answer=False):
    print("services cypher_search cypher_search")
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
            "message": f"1 Błąd podczas analizy pytania: {str(e)}",
            "times": times,
            "time": sum(times.values())
        }

    types_query = user_query
    if "compatible_with" in data:
        try:
            params_search = data.get("params", False)
            if isinstance(params_search, str):
                params_search = True if params_search.lower() == "true" else False
            start = time.time()
            types_response = app.ctx.NEO4J.get_similar_types(types_query)
            #price_response = self.neo4j.get_product_price(action_code, currency)
            types = [t["type_code"] for t in types_response]
            logger.debug(types)
            data["types"] = types
            end = time.time()
            logger.info(f"Wyszukiwanie typów produktów 1: {end - start} s")
            times["Wyszukiwanie typów produktów 1"] = end - start
        except Exception as e:
            return {
                "success": False,
                "message": f"1 Błąd podczas wyszukiwania typów produktów: {str(e)}",
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
            logger.info(f"Filtrowanie typów produktów 1: {end - start} s")
            times["Filtrowanie typów produktów 1"] = end - start
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

                arr = src.services.product_specification.get_product_specification(t)
                specification = arr[0]
                mapping = arr[1]
                categories = arr[2]
                excludes = arr[3]
                category_type = arr[4]
                if specification:
                    specification = src.services.product_specification.filter_language(specification, "PL", mapping, categories, excludes, t, category_type)
                    specifications[type_to_label(t)] = specification
            end = time.time()
            logger.info(f"Pobieranie specyfikacji 1: {end - start} s")
            times["Pobieranie specyfikacji 1"] = end - start
            logger.info(specifications)
        except Exception as e:
            return {
                "success": False,
                "message": f"Błąd podczas pobierania specyfikacji produktów 1: {str(e)}",
                "times": times,
                "types": types_response,
                "time": sum(times.values())
            }

        if params_search:
            try:
                start = time.time()
                params = generate_params(user_query, specifications)
                params = filter_none_params(params)
                end = time.time()
                logger.info(f"Generowanie parametrów cypher 1: {end - start} s")
                times["Generowanie parametrów cypher 1"] = end - start
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
        else:
            params = None


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
            "params": params,
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

        if name_response:
            similarity = name_response[0].get("similarity")
            if isinstance(similarity, (int, float)) and similarity >= 0.995:
                del name_response[1:]

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
        actions = []
        eans = []
        pns = []
        for product in products:
            if "name" in product:
                names.append(product["name"])
            if "action" in product:
                actions.append(product["action"])
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
        for action in actions:
            action_response = app.ctx.NEO4J.get_product_by_action_code(action, with_parameters=return_parameters)
            if action_response:
                responses.append(action_response[0])
        for pn in pns:
            pn_response = app.ctx.NEO4J.get_product_by_pn(pn, with_parameters=return_parameters)
            if pn_response:
                responses.append(pn_response[0])
        end = time.time()
        logger.info(f"Wyszukiwanie produktów: {end - start} s")
        times["Wyszukiwanie produktów"] = end - start

        #filtrowanie powtórek
        eans_set = set()
        filtered_responses = []
        for response in responses:
            if response and "EAN" in response:
                ean = response.get("EAN")
                if ean in eans_set:
                    continue
                eans_set.add(ean)
                filtered_responses.append(response)
        responses = filtered_responses

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
            "message": f"2 Błąd podczas analizy pytania: {data}",
            "times": times,
            "time": sum(times.values())
        }


    # Krok 1: Wyszukanie typów produktów
    try:
        start = time.time()
        types_response = app.ctx.NEO4J.get_similar_types(types_query)
        #price_response = self.neo4j.get_product_price(action_code, currency)
        types = [t["type_code"] for t in types_response]
        end = time.time()
        logger.info(f"Wyszukiwanie typów produktów 2: {end - start} s")
        times["Wyszukiwanie typów produktów 2"] = end - start
    except Exception as e:
        return {
            "success": False,
            "message": f"2 Błąd podczas wyszukiwania typów produktów: {str(e)}",
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
        logger.info(f"Filtrowanie typów produktów 2: {end - start} s")
        times["Filtrowanie typów produktów 2"] = end - start
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
            arr = src.services.product_specification.get_product_specification(t)
            specification = arr[0]
            mapping = arr[1]
            categories = arr[2]
            excludes = arr[3]
            category_type = arr[4]
            if specification:
                specification = src.services.product_specification.filter_language(specification, "PL", mapping, categories, excludes, t, category_type)
                specifications[type_to_label(t)] = specification
        end = time.time()
        logger.info(f"Pobieranie specyfikacji 2: {end - start} s")
        times["Pobieranie specyfikacji 2"] = end - start
        #logger.info(specifications)
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas pobierania specyfikacji produktów 2: {str(e)}",
            "times": times,
            "types": types_response,
            "time": sum(times.values())
        }

    try:
        start = time.time()
        params = generate_params(user_query, specifications)
        params = filter_none_params(params)
        end = time.time()
        logger.info(f"Generowanie parametrów cypher2 : {end - start} s")
        times["Generowanie parametrów cypher 2"] = end - start
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
    logger.info(f"Znalezienie możliwych wartości parametrów 2: {end - start} s")
    times["Znalezienie możliwych wartości parametrów 2"] = end - start
    #logger.info(params_values)

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
    print("services cypher_search type_to_label")
    return t.replace("-", "_")


def compatibility_search(data, params=None):
    print("services cypher_search compatibility_search")
    logger.debug(data)
    app = Sanic.get_app()
    types = data.get("types", [])
    ean = ""
    compatible_with = data.get("compatible_with", {})

    pn = compatible_with.get("PN")
    if pn and len(pn) == 13 and pn[9:].isdigit():
        compatible_with["action"] = pn
        del compatible_with["PN"]

    if not params:
        if compatible_with.get("action"):
            action = compatible_with["action"]
            response = app.ctx.NEO4J.get_compatible_products(types=types, action=action)
            logger.debug(response)
            return response, types
        if compatible_with.get("PN"):
            pn = compatible_with["PN"]
            response = app.ctx.NEO4J.get_compatible_products(types=types, pn=pn)
            logger.debug(response)
            return response, types
        if compatible_with.get("EAN"):
            ean = compatible_with["EAN"]
            response = app.ctx.NEO4J.get_compatible_products(types=types, ean=ean)
            logger.debug(response)
            return response, types

    ean = None
    action = None
    pn = None
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
    elif compatible_with.get("action"):
        action = compatible_with["action"]
    elif compatible_with.get("PN"):
        pn = compatible_with["PN"]
    else:
        logger.error("Brak informacji o kompatybilności w danych wejściowych")
        return [], []
    logger.info(f"EAN: {ean}")

    response = app.ctx.NEO4J.get_compatible_products_filtered_by_price(types=types, ean=ean, action=action, pn=pn, params=params)
    if response:
        eans = [cp['EAN'] for cp in response if cp.get('EAN')]
        logger.info(f"EANs: {eans}")
        if eans and params.get("requiredProperties"):
            response = app.ctx.NEO4J.filter_compatible_products(eans=eans, params=params)

    logger.debug(response)
    return response, types




def simple_search(user_query):
    print("services cypher_search simple_search")
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
        if action_response:
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