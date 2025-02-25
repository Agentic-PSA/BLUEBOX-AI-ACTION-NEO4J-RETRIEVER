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

    def add_node(self, node_type, properties):
        with self.get_neo4j_session() as session:
            query = f"CREATE (n:{node_type} {{"
            query += ", ".join([f"{key}: ${key}" for key in properties.keys()])
            query += "}) RETURN n"
            logging.warning(query)
            result = session.execute_write(self._execute_query, query, properties)
            if result is not None:
                return self._serialize_node(result["n"])
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