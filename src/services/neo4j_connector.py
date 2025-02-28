import logging
import os

from neo4j import GraphDatabase


class Neo4jConnector:
    def __init__(self):
        uri = f'bolt://{os.environ.get("NEO4J_HOST")}:{os.environ.get("NEO4J_PORT")}'
        self.driver = GraphDatabase.driver(uri, auth=(os.environ.get("NEO4J_USER"), os.environ.get("NEO4J_PASSWORD")))

    def close(self):
        self.driver.close()

    def get_neo4j_session(self):
        return self.driver.session()

    def add_node(self, labels: list, properties: dict):
        labels = [f"`{label}`" if ' ' in label else label for label in labels]
        with self.get_neo4j_session() as session:
            query = f"CREATE (n:{':'.join(labels)} {{"
            query += ", ".join([f"`{key}`: $`{key}`" for key in properties.keys()])
            query += "}) RETURN n"
            logging.warning(query)
            result = session.execute_write(self._execute_query, query, properties)
            if result is not None:
                return self._serialize_node(result["n"])
            return None

    def add_property_node(self, product_node: dict, property_name: str, property_value, relationship_properties: dict = None):
        PROPERTY_LABEL = "Property"
        try:
            with self.get_neo4j_session() as session:
                query = f"MATCH (n:{PROPERTY_LABEL} {{`{property_name}`: $property_value}}) RETURN n"
                logging.warning(query)
                result = session.execute_read(self._execute_query, query, {"property_value": property_value})

                if result is None:
                    logging.warning(f"Creating node")
                    query = f"CREATE (n:{PROPERTY_LABEL} {{`{property_name}`: $property_value}}) RETURN n"
                    logging.warning(query)
                    result = session.execute_write(self._execute_query, query, {"property_value": property_value})
                    logging.warning(result)
                else:
                    logging.warning(f"Node exists")

                property_node = self._serialize_node(result["n"])

                # Create relationship
                relationship_query = f"MATCH (a) WHERE id(a) = $product_node_id MATCH (b) WHERE id(b) = $property_node_id "
                relationship_query += f"CREATE (a)-[r:HAS {{"
                if relationship_properties:
                    relationship_query += ", ".join(
                        [f"{key}: ${key}" for key in relationship_properties.keys()])
                relationship_query += "}]->(b) RETURN r"
                logging.warning(relationship_query)

                parameters = {
                    "property_node_id": int(property_node["element_id"]),
                    "product_node_id": int(product_node["element_id"])
                }
                if relationship_properties:
                    parameters.update(relationship_properties)

                logging.warning(parameters)

                relationship_result = session.execute_write(self._execute_query, relationship_query, parameters)
                logging.warning("relationship_result")
                logging.warning(relationship_result)
                if relationship_result is not None:
                    return self._serialize_node(relationship_result["r"])
        except Exception as e:
            logging.error(f"Error in add_property_node: {str(e)}")
        return None

    @staticmethod
    def _execute_query(tx, query, parameters):
        result = tx.run(query, parameters)
        return result.single()

    @staticmethod
    def _serialize_node(node):
        return {
            "element_id": node.element_id,
            "labels": list(node.labels),
            "properties": dict(node)
        }