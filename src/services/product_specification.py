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


def get_form_data(column: str, value: str, table: str= 'forms') -> dict:
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
                host=os.environ.get("POSTGRES_HOST"),
                port=os.environ.get("POSTGRES_PORT"),
                database=os.environ.get("POSTGRES_DB"),
                user=os.environ.get("POSTGRES_USER"),
                password=os.environ.get("POSTGRES_PASSWORD")
        ) as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                query = sql.SQL("SELECT * FROM {table} WHERE {field} = %s LIMIT 1").format(
                    table=sql.Identifier(table),
                    field=sql.Identifier(column)
                )
                cursor.execute(query, [value])
                result = cursor.fetchone()

                if not result:
                    raise ValueError(f"Brak danych w tabeli {table} dla {column} = '{value}'")

                return dict(result)

    except Exception as e:
        print(f"Błąd podczas pobierania danych z bazy: {e}")
        raise

def get_product_specification(type):
    category = get_form_data('category', type, table='category_to_type')
    print(category)
    spec_data = get_form_data('category', category.get('type'), table='forms')

    return spec_data['form'][0]['value']
    # print("services product_specification get_product_specification")
    # return connector.get_value_from_data_store(os.environ.get("SPECIFICATION_DATASTORE"),
    #                                            "attributes",
    #                                            type.replace("_", "-"))

def filter_language(specification, language="PL"):
    print("services product_specification filter_language")

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