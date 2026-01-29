import psycopg2
from psycopg2 import extras, sql
import os

def get_form_data_many(column: str, labels: list, table: str= 'forms') -> dict:
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
                placeholders = sql.SQL(',').join(sql.Placeholder() * len(labels))
                query = sql.SQL("SELECT * FROM {table} WHERE {field} IN ({values})").format(
                    table=sql.Identifier(table),
                    field=sql.Identifier(column),
                    values=placeholders
                )
                cursor.execute(query, labels)
                result = cursor.fetchone()

                if not result:
                    raise ValueError(f"Brak danych w tabeli {table} dla {column} = '{labels}'")

                return dict(result)

    except Exception as e:
        print(f"Błąd podczas pobierania danych z bazy: {e}")
        raise



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
    print("services product_specification get_product_specification", type)
    category = get_form_data('category', type, table='category_to_type')
    spec_data = get_form_data('category', category.get('type'), table='forms')
    return [spec_data['form_with_values'][0]['value'], spec_data['values_map'], spec_data['categories'], category['search_excludes'], category.get('type')]
    #return spec_data['form'][0]['value']

    # print("services product_specification get_product_specification")
    # return connector.get_value_from_data_store(os.environ.get("SPECIFICATION_DATASTORE"),
    #                                            "attributes",
    #                                            type.replace("_", "-"))

def filter_language(specification, language="PL", mapping={}, categories={}, excludes={}, category_in='', category_type=''):
    category = category_in
    if "/" in category:
        category = category.split("/", 1)[1].strip()
    print('----->filter_language', 'type=',category_type, 'in=',category_in, 'cat=',category)

    filtered_sections = []
    for section in specification:
        section_name = section.get("section_name", {}).get(language, "")
        if section_name == 'Dane podstawowe':
            continue
        filtered_section = {"section_name": section_name, "attributes": []}
        attributes = section.get("attributes", [])
        for attribute_dict in attributes:
            attribute = attribute_dict.get(language, "")
            #print("MAM",section_name,attribute)
            #tylko liscie wybranej kategorii
            if categories.get(section_name, {}).get(attribute):
                if categories[section_name][attribute]:
                    if category not in categories[section_name][attribute]:
                        if category_type != category_in:
                            #print("USUWAM 1",section_name,attribute)
                            continue
            #usun nieistotne parametry
            if section_name in excludes:
                if attribute in excludes[section_name]:
                    exclude_value = excludes[section_name][attribute]
                    if exclude_value:
                        if category_type != category_in:
                            #print("USUWAM 2",section_name,attribute)
                            continue

            mapping_section = mapping.get(section_name, {})
            mapping_attr = mapping_section.get(attribute, {})
            unit = mapping_attr.get("unit", "")

            if unit and unit != 'dimensionless':
                struct = {attribute: {"unit": unit}}
            else:
                values = attribute_dict.get("values", [])
                struct = {attribute: {"values": values}}
            filtered_section["attributes"].append(struct)

        if filtered_section["attributes"]:
            filtered_sections.append(filtered_section)

    return filtered_sections
