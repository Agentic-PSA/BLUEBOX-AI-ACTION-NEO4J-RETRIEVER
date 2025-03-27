from anthropic import Anthropic
import httpx
from httpx import Client
import uuid
import time
import json
from py2neo import Graph
import openai

import src.services.product_specification
import src.services.db_schema

# client = Anthropic(
#     api_key="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",
#     # This is the default and can be omitted
# )


client_gpt = openai.OpenAI(
   api_key="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")


def search_search_group(descriptions=[]):
    client = Client(verify=False)

    token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MiwibmFtZSI6Im1idGVzdCIsInNoYXJlcG9pbnRfZW1haWwiOiJ4QHgucGwifQ.MIqGiWA2uYuW6YYZ_1movoX-92KcPdRTkVLcjINFX5M'

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

    groups = []
    for item in response.json():
        results = item.get('results', [])
        for r in results:
            group = r.get('group', "")
            groups.append(group)

    return groups


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


def cypher_search(user_query):
    times = {}
    # Krok 1: Wyszukanie typów produktów
    try:
        start = time.time()
        types = search_search_group([user_query])
        end = time.time()
        print(f"Krok 1: Wyszukiwanie typów produktów: {end - start} s")
        times["Krok 1: Wyszukiwanie typów produktów"] = end - start
        print(types)
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas wyszukiwania typów produktów: {str(e)}",
            "times": times
        }


    # Krok 2: Pobierz formatki wybranych typów produktów
    try:
        start = time.time()
        specifications = {}
        for t in types:
            # print(f"Pobieranie specyfikacji dla typu: {t}")

            specifications[type_to_label(t)] = src.services.product_specification.get_product_specification(t)
        end = time.time()
        print(f"Krok 2: Pobieranie specyfikacji: {end - start} s")
        times["Krok 2: Pobieranie specyfikacji"] = end - start
        print(specifications)
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas pobierania specyfikacji produktów: {str(e)}",
            "times": times,
            "types": types
        }

    # Krok 3: Generowanie uproszczonego zapytania Cypher
    print("\nGenerowanie zapytania Cypher na podstawie pytania użytkownika...")
    try:
        start = time.time()
        cypher_query_data = generate_simple_cypher_query_with_llm(
            src.services.db_schema.db_schema,
            "",
            user_query,
            specifications
        )
        end = time.time()

        print(f"Krok 3: Generowanie zapytania Cypher: {end - start} s")
        times["Krok 3: Generowanie zapytania Cypher"] = end - start
        print("\nWygenerowane zapytanie Cypher:")
        cypher_query = cypher_query_data['cypher']
        print(cypher_query_data)
        print(cypher_query)
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas generowania zapytania Cypher: {str(e)}",
            "times": times,
            "types": types
        }

    start = time.time()
    graph = Graph("neo4j://172.19.3.220:30687", auth=("neo4j", "testpassword"))
    end = time.time()
    print(f"Krok 4: Pobranie danych z NEO: {end - start} s")
    times["Krok 4: Pobranie danych z NEO"] = end - start

    try:
        results = graph.run(cypher_query).data()
        print(results)
    except Exception as e:
        return {
            "success": False,
            "message": f"Błąd podczas wykonywania zapytania Cypher: {str(e)}",
            "query": cypher_query,
            "times": times,
            "types": types
        }

    return {
        "success": True,
        "message": f"",
        "results": results,
        "query": cypher_query,
        "times": times,
        "types": types
    }


def type_to_label(t: str):
    return t.replace("-", "_")


if __name__ == "__main__":

    # client = openai.OpenAI(
    #    api_key="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")


    task = "Telewizor LCD z ekranem 55 cali"
    _results = cypher_search(task)
    print(f"Status: {'Sukces' if _results.get('success', False) else 'Błąd'}")
    print(f"Wiadomość: {_results.get('message', '')}")