import openai
from sanic.log import logger
import os

from neo4j import GraphDatabase

from ..utils import UnitConverter


def find_similar_products(tx, query_vector):
    query = """
WITH $query_vector AS queryVector
MATCH (p:Product)-[:HAS]->(n:Name:Property_PL)
WITH p, n, gds.similarity.cosine(queryVector, n.embedding) AS similarity
RETURN n.value AS productName, p.EAN AS EAN, p.product_number AS PN, p.producer AS producer, similarity
ORDER BY similarity DESC
LIMIT 10
    """
    result = tx.run(query, query_vector=query_vector)
    return [{"EAN": record["EAN"], "productName": record["productName"], "similarity": record["similarity"],
             "PN": record["PN"], "producer": record["producer"]} for record in result]

def find_similar_pn(tx, query_vector):
    query = """
    WITH $query_vector AS queryVector
    MATCH (p:Product)
    WITH p, gds.similarity.cosine(queryVector, p.productNumberEmbedding) AS similarity
    RETURN p.name AS productName, p.EAN AS EAN, p.product_number AS PN, p.producer AS producer, similarity
    ORDER BY similarity DESC
    LIMIT 5
    """
    similarity_100 = False
    result = tx.run(query, query_vector=query_vector)
    formatted_results = []
    for record in result:
        if record["similarity"] >= 1.0:
            similarity_100 = True
        if similarity_100 and record["similarity"] < 1.0:
            break
        formatted_results.append({"EAN": record["EAN"], "productName": record["productName"], "similarity": record["similarity"],
             "PN": record["PN"], "producer": record["producer"]})
    return formatted_results

def find_similar_type(tx, query_vector, limit=5):
    query = f"""
    WITH $query_vector AS queryVector
    MATCH (t:Type)
    WITH t, gds.similarity.cosine(queryVector, t.nameEmbedding) AS similarity
    RETURN t.code AS type_code, t.name AS type_name, similarity
    ORDER BY similarity DESC
    LIMIT {limit}
    """

    result = tx.run(query, query_vector=query_vector)
    formatted_results = []
    for record in result:
        formatted_results.append({"type_code": record["type_code"], "type_name": record["type_name"], "similarity": record["similarity"]})
    return formatted_results

class Neo4jConnector:
    def __init__(self):
        uri = f'bolt://{os.environ.get("NEO4J_HOST")}:{os.environ.get("NEO4J_PORT")}'
        self.driver = GraphDatabase.driver(uri, auth=(os.environ.get("NEO4J_USER"), os.environ.get("NEO4J_PASSWORD")))
        self.units_converter = UnitConverter()
        self.client_gpt = openai.OpenAI(
            api_key="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")
        self.embeddings_model = "text-embedding-3-small"

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
            logger.info(query)
            result = session.execute_write(self._execute_query, query, properties)
            if result is not None:
                return self._serialize_node(result["n"])
            return None

    def add_property_node(self, product_node: dict, property_name: str, property_value, property_label: str, relationship_properties: dict = None):
        logger.info(f"Property type {type(property_value)}")
        property_label = f"`{property_label}`" if ' ' in property_label and "`" not in property_label else property_label
        if isinstance(property_value, dict):
            logger.warning(f"Adding unit property node: {property_value}")
            value = property_value.get("value")
            unit = property_value.get("unit")
            return self.add_unit_property_nodes(product_node, property_name, value, unit, property_label, relationship_properties)
        if isinstance(property_value, list):
            results = []
            for value in property_value:
                res = self.add_property_node(product_node, property_name, value, property_label, relationship_properties)
                results.append(res)
            return results
        property_data = {"property_value": property_value, "property_name": property_name}
        logger.info(f"Adding property node: {property_data}")
        try:
            with self.get_neo4j_session() as session:
                query = f"MATCH (n:{property_label} {{`name`: $property_name, `value`: $property_value}}) RETURN n"
                logger.info(query)
                result = session.execute_read(self._execute_query, query, property_data)

                if result is None:
                    logger.info(f"Creating node")
                    query = f"CREATE (n:{property_label} {{`name`: $property_name, `value`: $property_value}}) RETURN n"
                    logger.info(query)
                    result = session.execute_write(self._execute_query, query, property_data)
                    logger.info(result)
                else:
                    logger.info(f"Node exists")

                property_node = self._serialize_node(result["n"])

                # Create relationship
                relationship_query = f"MATCH (a) WHERE id(a) = $product_node_id MATCH (b) WHERE id(b) = $property_node_id "
                relationship_query += f"CREATE (a)-[r:HAS {{"
                if relationship_properties:
                    relationship_query += ", ".join(
                        [f"{key}: ${key}" for key in relationship_properties.keys()])
                relationship_query += "}]->(b) RETURN r"
                logger.info(relationship_query)

                parameters = {
                    "property_node_id": int(property_node["element_id"]),
                    "product_node_id": int(product_node["element_id"])
                }
                if relationship_properties:
                    parameters.update(relationship_properties)

                logger.info(parameters)

                relationship_result = session.execute_write(self._execute_query, relationship_query, parameters)
                logger.info("relationship_result")
                logger.info(relationship_result)
                if relationship_result is not None:
                    return self._serialize_relationship(relationship_result["r"])
        except Exception as e:
            logger.error(f"Error in add_property_node: {str(e)}")
        return None

    @staticmethod
    def _execute_query(tx, query, parameters):
        result = tx.run(query, parameters)
        return result.single()

    @staticmethod
    def _execute_query_multiple(tx, query, parameters):
        result = tx.run(query, parameters)
        return result.values()

    @staticmethod
    def _execute_query_records(tx, query, parameters):
        result = tx.run(query, parameters)
        values = [record.data() for record in result]
        return values

    @staticmethod
    def _serialize_node(node):
        return {
            "element_id": node.element_id,
            "labels": list(node.labels),
            "properties": dict(node)
        }
    @staticmethod
    def _serialize_relationship(relationship):
        return {
            "element_id": relationship.element_id,
            "properties": dict(relationship)
        }

    def add_unit_property_nodes(self, product_node: dict, property_name: str, property_value, property_unit: str, property_label: str, relationship_properties: dict = None):
        try:
            unit_variants = self.units_converter.convert_to_variants(property_value, property_unit)
            logger.info(f"Unit variants: {unit_variants}")
            with (self.get_neo4j_session() as session):
                property_nodes_ids = []
                for key, value in unit_variants.items():
                    property_data = {"property_name": property_name,
                                     "property_value": value,
                                     "property_unit": key}
                    query = f"MATCH (n:{property_label} {{`name`: $property_name, `value`: $property_value, `unit`: $property_unit}}) RETURN n"
                    logger.info(query)
                    result = session.execute_read(self._execute_query, query, property_data)

                    if result is None:
                            logger.info(f"Creating node")
                            query = f"CREATE (n:{property_label} {{`name`: $property_name, `value`: $property_value, `unit`: $property_unit}}) RETURN n"
                            logger.info(query)
                            result = session.execute_write(self._execute_query, query, property_data)
                            logger.info(result)
                    else:
                        logger.info(f"Nodes exist")

                    property_node = self._serialize_node(result["n"])
                    logger.info(property_node)
                    # Create relationship
                    relationship_query = f"MATCH (a) WHERE id(a) = $product_node_id MATCH (b) WHERE id(b) = $property_node_id "
                    relationship_query += f"CREATE (a)-[r:HAS {{"
                    if relationship_properties:
                        relationship_query += ", ".join(
                            [f"{key}: ${key}" for key in relationship_properties.keys()])
                    relationship_query += "}]->(b) RETURN r"
                    logger.info(relationship_query)

                    parameters = {
                        "property_node_id": int(property_node["element_id"]),
                        "product_node_id": int(product_node["element_id"])
                    }
                    property_nodes_ids.append(property_node["element_id"])
                    if relationship_properties:
                        parameters.update(relationship_properties)

                    logger.info(parameters)

                    relationship_result = session.execute_write(self._execute_query, relationship_query, parameters)
                    logger.info("relationship_result")
                    logger.info(relationship_result)

                for i in range(len(property_nodes_ids)):
                    for j in range(i+1, len(property_nodes_ids)):
                        query = "MATCH (a) WHERE id(a) = $property_node_id1 " + \
                                "MATCH (b) WHERE id(b) = $property_node_id2 " + \
                                "MERGE (a)-[r:IS_EQUAL]-(b) " + \
                                "RETURN r"
                        logger.info(query)
                        parameters = {
                            "property_node_id1": int(property_nodes_ids[i]),
                            "property_node_id2": int(property_nodes_ids[j])
                        }
                        session.execute_write(self._execute_query, query, parameters)


        except Exception as e:
            logger.error(f"Error in add_unit_property_node: {str(e)}")
        return None

    @staticmethod
    def _serialize_product(record):
        product = record[0]
        relationship = record[1]
        property_node = record[2]

        return {
            "product": {
                "element_id": product.element_id,
                "labels": list(product.labels),
                "properties": dict(product)
            },
            "relationship": {
                "element_id": relationship.element_id,
                "type": relationship.type,
                "properties": dict(relationship)
            },
            "property": {
                "element_id": property_node.element_id,
                "labels": list(property_node.labels),
                "properties": dict(property_node)
            }
        }

    @staticmethod
    def generate_ean_variants(ean):
        variants = [ean]
        if len(ean) == 13 and ean.startswith('0'):
            variants.append(ean[1:])
        if len(ean) == 13 and ean.startswith('00'):
            variants.append(ean[2:])
        if len(ean) == 12:
            variants.append('0' + ean)
        if len(ean) == 12 and ean.startswith('0'):
            variants.append(ean[1:])
        if len(ean) == 11:
            variants.append('00' + ean)
            variants.append('0' + ean)

        return variants

    def get_product(self, ean: str):
        variants = self.generate_ean_variants(ean)
        for ean_variant in variants:
            with self.get_neo4j_session() as session:
                query = "MATCH (product:Product {EAN: $ean})-[r:HAS]->(property) RETURN product, r, property"
                properties = {"ean": ean_variant}
                result = session.execute_read(self._execute_query_multiple, query, properties)
                logger.debug(result)
                if result:
                    return [self._serialize_product(record) for record in result]
        return None


    def get_product_by_pn(self, pn: str):
        response = self.client_gpt.embeddings.create(
            model=self.embeddings_model,
            input=pn
        )
        query_vector = response.data[0].embedding
        with self.driver.session() as session:
            results = session.read_transaction(find_similar_pn, query_vector)
            logger.debug(results)
        return results

    def get_product_by_name(self, name:str):
        response = self.client_gpt.embeddings.create(
            model=self.embeddings_model,
            input=name
        )
        query_vector = response.data[0].embedding
        with self.driver.session() as session:
            results = session.read_transaction(find_similar_products, query_vector)
            logger.debug(results)
        return results

    def get_similar_types(self, text:str):
        response = self.client_gpt.embeddings.create(
            model=self.embeddings_model,
            input=text
        )
        query_vector = response.data[0].embedding
        with self.driver.session() as session:
            results = session.read_transaction(find_similar_type, query_vector)
            logger.debug(results)
        return results

    def execute_query(self, query, properties={}):
        with self.get_neo4j_session() as session:
            result = session.execute_read(self._execute_query_records, query, properties)
            return result

    def add_bidirectional_relationship_with_properties(self, type1_code, type2_code, relationship_type, relationship_properties1={}, relationship_properties2={}):
        with self.driver.session() as session:
            result = session.write_transaction(
                self._create_bidirectional_relationship_with_properties,
                type1_code, type2_code, relationship_type, relationship_properties1, relationship_properties2
            )
            return result

    @staticmethod
    def _create_bidirectional_relationship_with_properties(tx, type1_code, type2_code, relationship_type,
                                                           relationship_properties1, relationship_properties2):
        query = (
            "MATCH (a:Type {code: $type1_code}), (b:Type {code: $type2_code}) "
            f"MERGE (a)-[r1:{relationship_type}]->(b) "
            "ON CREATE SET r1 += $props1 "
            f"MERGE (b)-[r2:{relationship_type}]->(a) "
            "ON CREATE SET r2 += $props2 "
            "RETURN a, b, r1, r2"
        )
        result = tx.run(query, type1_code=type1_code, type2_code=type2_code,
                        props1=relationship_properties1, props2=relationship_properties2)
        return result.single()