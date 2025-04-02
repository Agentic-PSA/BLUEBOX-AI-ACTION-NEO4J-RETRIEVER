from src.services.spiff_connector import SpiffConnector

user = "spiffworkflow_backend"
password = "spiffworkflow_backend"
host = "172.19.3.220"
port = "30432"
database = "spiffworkflow_backend"
connector = SpiffConnector(user, password, host, port, database)


def get_product_specification(type):
    return connector.get_value_from_data_store("original_specifications", "attributes", type.replace("_", "-"))

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