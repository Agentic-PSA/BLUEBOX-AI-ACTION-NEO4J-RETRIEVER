import json
import time
import os

import openai
from sanic import Sanic
from sanic.log import logger

client_gpt = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def llm(prompt):
    print("services ai_search llm")
    response = client_gpt.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    print(response)
    response_text = response.choices[0].message.content
    print(response_text)
    return response_text



def prompt1(query):
    print("services ai_search prompt1")
    prompt = """
Jesteś chatbotem obsługi klienta w sklepie z elektroniką. Twoim zadaniem jest analizowanie zapytań klientów i odpowiadanie na nie w optymalny sposób, tak aby pomóc im w doborze odpowiedniego sprzętu. Twoje odpowiedzi MUSZĄ być zwracane w formacie JSON i nie możesz zadawać dodatkowych pytań. Pamiętaj o poprawności języka i gramatyki.

• Rozpoznaj intencje klienta:
Czy klient szuka konkretnego produktu (podaje Part Number, EAN lub nazwę)?
Czy szuka produktu z konkretnej kategorii?
Czy klient oczekuje doboru sprzętu z kilku kategorii, które wspólnie spełnią jego wymagania (np. podzespoły komputerowe; aparat fotograficzny, obiektyw i statyw)?
• Oflaguj typ zapytania(query_type):
product: Jeśli klient pyta ogólnie o dobór sprzętu i musisz korzystać z wiedzy z internetu, aby zaproponować produkty (np. "Podaj mi 5 najlepszych gamingowych laptopów do gier"). W odpowiedzi zamieść Part Number (jeśli dostępny), EAN (jeśli dostępny), nazwę produktu lub wszystkie trzy, jeśli posiadasz te informacje. Nie wymyślaj EAN-ów i kodów producenta, jeśli nie masz pewności. 
product: Jeśli klient szuka konkretnego produktu po Part Number, EAN lub nazwie lub produktu z danej kategorii.
product_parameters: Jeśli klient prosi o dobór kompatybilnego produktu, zidentyfikuj i podaj parametr, na podstawie którego ta kompatybilność ma być zapewniona (np. socket procesora).
Jeżeli potrafisz na podstawie wiedzy z internetu zaproponować konkretne modele, to to zrób. Zwracaj do 10 propozycji. Postaraj się odnaleźć i dodać Part Number dla każdego z nich, o ile to możliwe.
product_parameters: Jeśli w pytaniu pojawiają się konkretne parametry techniczne produktu, odpowiedź powinna zawierać flagę "Konkretne parametry": true oraz listę tych parametrów i typ produktu (określający grupę produktową, do której ten produkt należy). Jeżeli zwracasz konkretny produkt (lub produkty) pasujące do parametrów podanych przez użytkownika, dodaj flagę "Typ i parametry": true.
• Generuj odpowiedź w następującym formacie JSON:

Jeśli zapytanie dotyczy produktu jednego typu i JESTEŚ w stanie zaproponować konkretne modele:
{
  "query_type": "product",
  "answer": "[Szczegółowa odpowiedź na zapytanie klienta]",
  "products": [
      {        
        "product_type": "[Typ produktu]",
        "name": "[Nazwa konkretnego modelu 1]",
        "part_number": "[Part Number 1]",
        "requirements": null      
      },
      {        
        "product_type": "[Typ produktu]",
        "name": "[Nazwa konkretnego modelu 2]",
        "part_number": "[Part Number 2]",
        "requirements": null      
      },
       // ... do 10 propozycji
    ],
  }
}

Jeśli zapytanie dotyczy produktu jednego typu i NIE jesteś w stanie zaproponować konkretnego modelu:
{
  "query_type": "product_parameters",
  "answer": "[Szczegółowa odpowiedź na zapytanie klienta]",
  "product_parameters": {
    "compatibility_parameter": "[Parametr kompatybilności]",
    "requirements": {
      "[Parametr 1]": "[Wartość 1]",
      "[Parametr 2]": "[Wartość 2]"    
    },    
    "product_type": "[Typ produktu]"
  }
}

Jeśli zapytanie dotyczy zestawu produktów (kilka produktów z różnych kategorii) i NIE zawiera konkretnych parametrów technicznych:
{
  "query_type": "products_set",
  "answer": "[Szczegółowa odpowiedź na zapytanie klienta]",
  "products_set": [
      {        
        "product_type": "[Typ produktu]",
        "requirements": null      
      }
    ]
  }
}

Jeśli zapytanie dotyczy zestawu produktów (kilka produktów z różnych kategorii) i ZAWIERA konkretne parametry techniczne:
{
  "query_type": "products_set_parameters",
  "answer": "[Szczegółowa odpowiedź na zapytanie klienta]",
  "products_set": [
      {        
        "product_type": "[Typ produktu 1]",
        "requirements": {
          "[Parametr 1]": "[Wartość 1]",
          "[Parametr 2]": "[Wartość 2]",
          "[Parametr 3]": "[Wartość 3]"        }      
        },      
    {        
        "product_type": "[Typ produktu 2]",
        "requirements": {
          "[Parametr 1]": "[Wartość 1]",
          "[Parametr 2]": "[Wartość 2]"
        }
      }
    ]
  
}

Ważne: Jeśli w zapytaniu pojawia się kilka opcji dla jednego typu produktu, rozbij to na osobne typy produktów w Zestawie produktów. Nigdy nie zwracaj odpowiedzi w jednym typie zawierającej kilka typów produktów.

Pytanie użytkownika:
"""

    prompt+= query

    return llm(prompt)

def prompt2(query):
    print("services ai_search prompt2")
    prompt = """
ZADANIE:
Działasz jako specjalista ds. sprzętu IT. Twoim zadaniem jest zwrócić jeden wspólny obiekt JSON zawierający propozycje produktów dopasowanych do zapytania użytkownika – z uwzględnieniem znanych modeli handlowych.

ZASADY:
Zawsze zwracaj jeden obiekt JSON w poniższej strukturze:

{
  "nazwa_semantyczna": string,
  "products": [
    {
      "model": string | null,
      "part_number": string | null,
      "ean": string | null
    },
    {
      "model": string | null,
      "part_number": string | null,
      "ean": string | null
    },
    ...
  ]
}

LOGIKA:

1. Jeśli zapytanie zawiera 5 lub więcej istotnych parametrów technicznych, np. CPU, RAM, typ GPU, standard portów, dokładne wymagania SIWZ:
   - dobierz 2–3 konkretne modele handlowe, które spełniają wymagania (wraz z part number i EAN, jeśli znane),
   - nazwa_semantyczna = "ai_search [typ produktu] [parametry techniczne wynikające z nazw modeli]",
   - dodaj także wszystkie parametry ze specyfikacji klienta, jeśli nie pojawiły się w nazwie modelu – poza tymi, które są zbyt oczywiste dla danej kategorii,
   - bardzo specyficzne cechy oznaczaj flagą (!).

2. Jeśli zapytanie zawiera tylko ogólną specyfikację (np. "monitor 24 cale 120Hz"):
   - pozostaw modele i kody jako null,
   - nazwa_semantyczna zgodnie z dotychczasowym schematem.

3. Jeśli zapytanie dotyczy aspektów nieproduktowych (np. tylko kod EAN, certyfikat, zgodność, producent):
   - odpowiedź: null

DODATKOWE UWAGI:
- nazwa_semantyczna zawsze zaczyna się od prefiksu: "ai_search"
- nazwa_semantyczna nie może zawierać nazw producentów, numerów katalogowych, kodów EAN
- Nie dodawaj żadnego komentarza – zwracaj wyłącznie czysty JSON
- Wartości tekstowe w nazwa_semantyczna muszą odzwierciedlać realne dane z nazw modeli
- Nie uwzględniaj informacji o gwarancji w nazwie semantycznej

Pytanie użytkownika:
"""

    prompt+= query

    return llm(prompt)

def ai_search(query, properties=False):
    print("services ai_search ai_search")
    app = Sanic.get_app()
    start = time.time()
    answer = prompt2(query)
    end = time.time()
    logger.info(answer)

    json_answer = json.loads(answer)
    json_answer["time"] = end-start


    # if json_answer.get("query_type", "").lower() == "product":
    #     products = json_answer.get("products", [])
    #
    #     products_responses = []
    #     for product in products:
    #         name = product.get("name", "")
    #         if name:
    #             start = time.time()
    #             name_response = app.ctx.NEO4J.get_product_by_name(name)
    #             end = time.time()
    #             products_responses.append(name_response)
    #
    #     json_answer["products_responses"] = products_responses
    #
    # elif json_answer.get("query_type", "").lower() == "product_parameters":
    #     pass
    # elif json_answer.get("query_type", "").lower() == "products_set":
    #     pass
    # elif json_answer.get("query_type", "").lower() == "products_set_parameters":
    #     pass


    return json_answer
