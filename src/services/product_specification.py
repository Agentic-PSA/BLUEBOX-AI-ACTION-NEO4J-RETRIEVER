import psycopg2
from psycopg2 import extras, sql

from src.services.spiff_connector import SpiffConnector
import os

user = "spiffworkflow_backend"
password = "spiffworkflow_backend"
host = "172.19.3.220"
port = "30432"
database = "spiffworkflow_backend"
connector = SpiffConnector(user=os.environ.get("SPIFF_DB_USER"),
                           password=os.environ.get("SPIFF_DB_PASSWORD"),
                           host=os.environ.get("SPIFF_DB_HOST"),
                           port=os.environ.get("SPIFF_DB_PORT"),
                           database=os.environ.get("SPIFF_DB_DATABASE"))


def get_form_data(column: str, value: str) -> dict:
    """
    Pobiera dane formularza z bazy danych PostgreSQL dla podanej kolumny.

    Args:
        column (str): nazwa kolumny w tabeli forms
        value (str): wartość do wyszukania w kolumnie

    Returns:
        dict: rekord z tabeli forms jako słownik

    Raises:
        ValueError: jeśli nie znaleziono danych lub kolumna jest niedozwolona
        psycopg2.Error: w przypadku błędu połączenia lub zapytania
    """


    try:
        with psycopg2.connect(
                host="172.16.10.3",
                port=30008,
                database="postgres",
                user="postgres",
                password="CQ15V1xNC9"
        ) as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                query = sql.SQL("SELECT * FROM forms WHERE {field} = %s LIMIT 1").format(
                    field=sql.Identifier(column)
                )
                cursor.execute(query, [value])
                result = cursor.fetchone()

                if not result:
                    raise ValueError(f"Brak danych w tabeli forms dla {column} = '{value}'")

                return dict(result)

    except Exception as e:
        print(f"Błąd podczas pobierania danych z bazy: {e}")
        raise

def get_product_specification(type):
    spec_data = get_form_data('category', type.replace("_", "-"))

    return spec_data['form']

def filter_language(specification, language="PL"):

    filtered_sections = []
    for section in specification:
        section_name = section.get("section_name", {}).get(language, "")
        filtered_section = {"section_name": section_name, "attributes": []}
        attributes = section.get("attributes", [])
        for attribute_dict in attributes:
            attribute = attribute_dict.get(language, "")
            filtered_section["attributes"].append(attribute)
        filtered_sections.append(filtered_section)

    return filtered_sections