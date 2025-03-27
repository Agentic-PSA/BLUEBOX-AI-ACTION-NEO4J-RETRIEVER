from src.services.spiff_connector import SpiffConnector

user = "spiffworkflow_backend"
password = "spiffworkflow_backend"
host = "172.19.3.220"
port = "30432"
database = "spiffworkflow_backend"
connector = SpiffConnector(user, password, host, port, database)


def get_product_specification(type):
    return connector.get_value_from_data_store("original_specifications", "attributes", type.replace("_", "-"))