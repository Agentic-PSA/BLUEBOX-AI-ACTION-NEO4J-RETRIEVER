import re

import openai
from sanic.log import logger
import os

from neo4j import GraphDatabase, Result

from ..utils import UnitConverter

def find_products_fulltext(tx, name, n = 10, similarity = None):
    query = f"CALL db.index.fulltext.queryNodes('product_name_text', $name) yield node as p, score AS similarity "
    if similarity:
        query += f"WITH p, similarity WHERE similarity >= {similarity} "
    query += "RETURN p.name AS name, p.EAN AS EAN, p.product_number AS PN, p.producer AS producer, p.action AS action, similarity "
    query += f"LIMIT {n}"
    name = re.sub(r'(?<!/)/(?!/)', '//', name)
    result = tx.run(query, name=name)
    return [{"EAN": record["EAN"], "name": record["name"], "similarity": record["similarity"],
             "PN": record["PN"], "action": record["action"], "producer": record["producer"]} for record in result]

def find_products_fulltext_by_pn(tx, pn, similarity = 0.98):
    query = f"CALL db.index.fulltext.queryNodes('product_number_text', $pn) yield node as p, score AS similarity "
    if similarity:
        query += f"WITH p, similarity WHERE similarity >= {similarity} "
    query += "RETURN p.name AS name, p.EAN AS EAN, p.product_number AS PN, p.producer AS producer, p.action AS action, similarity "
    query += f"LIMIT 1"
    pn = re.sub(r'(?<!/)/(?!/)', '//', pn)
    result = tx.run(query, pn=pn)
    return [{"EAN": record["EAN"], "name": record["name"], "similarity": record["similarity"],
             "PN": record["PN"], "action": record["action"], "producer": record["producer"]} for record in result]

def find_similar_products(tx, query_vector, n = 10, similarity = None):
    query = f"CALL db.index.vector.queryNodes('name', {n}, $query_vector) yield node as p, score AS similarity "
    if similarity:
        query += f"WITH p, similarity WHERE similarity >= {similarity} "
    query += "RETURN p.name AS name, p.EAN AS EAN, p.product_number AS PN, p.producer AS producer, p.action AS action, similarity"
    result = tx.run(query, query_vector=query_vector)
    return [{"EAN": record["EAN"], "name": record["name"], "similarity": record["similarity"],
             "PN": record["PN"], "action": record["action"], "producer": record["producer"]} for record in result]

def find_similar_pn(tx, query_vector):
    query = """
    CALL db.index.vector.queryNodes('product_number', 5, $query_vector) yield node as p, score AS similarity
    RETURN p.name AS name, p.EAN AS EAN, p.product_number AS PN, p.producer AS producer, p.action AS action, similarity
    """

    similarity_100 = False
    result = tx.run(query, query_vector=query_vector)
    formatted_results = []
    for record in result:
        if record["similarity"] >= 0.999:
            similarity_100 = True
        if similarity_100 and record["similarity"] < 0.999:
            break
        formatted_results.append({"EAN": record["EAN"], "name": record["name"], "similarity": record["similarity"],
             "PN": record["PN"], "action": record["action"], "producer": record["producer"]})
    return formatted_results

def find_similar_type(tx, query_vector, limit=20):
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
        self.client_gpt = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
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

    def add_value_node(self, properties: dict):
        correct_value = properties.pop("correct_value")
        with self.get_neo4j_session() as session:
            query = f"MERGE (n:Value {{"
            query += ", ".join([f"`{key}`: $`{key}`" for key in properties.keys()])
            query += "}) SET n.correct_value = $correct_value RETURN n"
            logger.info(query)
            properties["correct_value"] = correct_value
            result = session.execute_write(self._execute_query, query, properties)
            if result is not None:
                return self._serialize_node(result["n"])
            return None

    def add_relationship(self, from_node: dict, rel_type: str, to_node: dict, relationship_properties: dict = None):
        """
        Tworzy relację między dwoma istniejącymi węzłami.
        from_node, to_node: dict zawierający 'element_id'
        rel_type: string np. 'ENRICHED_BY'
        """
        relationship_query = f"""
        MATCH (a) WHERE elementId(a) = $from_id
        MATCH (b) WHERE elementId(b) = $to_id
        CREATE (a)-[r:{rel_type} {{
            {', '.join([f'{k}: ${k}' for k in relationship_properties.keys()]) if relationship_properties else ''}
        }}]->(b)
        RETURN r
        """
        parameters = {"from_id": from_node["element_id"], "to_id": to_node["element_id"]}
        if relationship_properties:
            parameters.update(relationship_properties)

        with self.get_neo4j_session() as session:
            result = session.execute_write(self._execute_query, relationship_query, parameters)
            if result:
                return self._serialize_relationship(result["r"])
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
                relationship_query = f"MATCH (a) WHERE elementId(a) = $product_node_id MATCH (b) WHERE elementId(b) = $property_node_id "
                relationship_query += f"CREATE (a)-[r:HAS {{"
                if relationship_properties:
                    relationship_query += ", ".join(
                        [f"{key}: ${key}" for key in relationship_properties.keys()])
                relationship_query += "}]->(b) RETURN r"
                logger.info(relationship_query)

                parameters = {
                    "property_node_id": property_node["element_id"],
                    "product_node_id": product_node["element_id"]
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
                                     "property_unit": key,
                                     "default_unit": key == property_unit
                                     }
                    query = f"MATCH (n:{property_label} {{`name`: $property_name, `value`: $property_value, `unit`: $property_unit}}) RETURN n"
                    logger.info(query)
                    result = session.execute_read(self._execute_query, query, property_data)

                    if result is None:
                            logger.info(f"Creating node")
                            query = f"CREATE (n:{property_label} {{`name`: $property_name, `value`: $property_value, `unit`: $property_unit, `default_unit`: $default_unit}}) RETURN n"
                            logger.info(query)
                            result = session.execute_write(self._execute_query, query, property_data)
                            logger.info(result)
                    else:
                        logger.info(f"Nodes exist")

                    property_node = self._serialize_node(result["n"])
                    logger.info(property_node)
                    # Create relationship
                    relationship_query = f"MATCH (a) WHERE elementId(a) = $product_node_id MATCH (b) WHERE elementId(b) = $property_node_id "
                    relationship_query += f"CREATE (a)-[r:HAS {{"
                    if relationship_properties:
                        relationship_query += ", ".join(
                            [f"{key}: ${key}" for key in relationship_properties.keys()])
                    relationship_query += "}]->(b) RETURN r"
                    logger.info(relationship_query)

                    parameters = {
                        "property_node_id": property_node["element_id"],
                        "product_node_id": product_node["element_id"]
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
                        query = "MATCH (a) WHERE elementId(a) = $property_node_id1 " + \
                                "MATCH (b) WHERE elementId(b) = $property_node_id2 " + \
                                "MERGE (a)-[r:IS_EQUAL]-(b) " + \
                                "RETURN r"
                        logger.info(query)
                        parameters = {
                            "property_node_id1": property_nodes_ids[i],
                            "property_node_id2": property_nodes_ids[j]
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
                # query = "MATCH (product:Product {EAN: $ean})-[r:HAS]->(property) " + \
                #         "RETURN apoc.map.submap(product, ['EAN', 'name', 'producer', 'product_number']) AS product, r, property"
                query = "MATCH (product:Product {EAN: $ean})" + \
                        "RETURN apoc.map.submap(product, ['EAN', 'name', 'producer', 'product_number', 'action']) AS product"
                properties = {"ean": ean_variant}
                result = session.execute_read(self._execute_query_multiple, query, properties)
                logger.debug(result)
                if result:
                    return result[0][0]
        return None

    def get_compatible_products(self, types=[], ean=None, pn=None, action=None):
        if not types:
            return []
        if ean:
            product_query = "{EAN: $ean}"
        elif action:
            product_query = "{action: $action}"
        elif pn:
            product_query = "{product_number: $pn}"
        else:
            return []

        labels = [type.replace("-", "_") for type in types]
        logger.debug(f"Labels: {labels}")
        variants = self.generate_ean_variants(ean) if ean else [pn]
        for ean_variant in variants:
            with self.get_neo4j_session() as session:
                query = "MATCH (product:Product" + product_query  + """)
OPTIONAL MATCH (product)-[:COMPATIBLE]-(other:Product)
WHERE any(label IN labels(other) WHERE label IN $labels)
RETURN 
  apoc.map.submap(product, ['EAN', 'name', 'producer', 'product_number', 'action']) AS product,
  collect(
    apoc.map.submap(other, ['EAN', 'name', 'producer', 'product_number', 'action'])
  ) AS compatible_products
  """
                properties = {"ean": ean_variant, "pn": pn, "action": action, "labels": labels}
                result = session.execute_read(self._execute_query_multiple, query, properties)
                logger.debug(result)
                if result:
                    return result[0][1]

    def get_compatible_products_filtered_by_price(self, types=[], params={}, ean=None, pn=None, action=None):
        if not types:
            return []
        if ean:
            product_query = "{EAN: $ean}"
        elif action:
            product_query = "{action: $action}"
        elif pn:
            product_query = "{product_number: $pn}"
        else:
            return []

        price_query = ""
        price_where = ""
        price = params.get("price")
        currency = params.get("currency", "PLN")
        if price:
            if price.get("equal") is not None:
                price_query = "MATCH (other)-[:HAS]->(price:Price)"
                price_where = "AND price.value = $equal AND price.currency = $currency"
            elif price.get("min") is not None and price.get("max") is not None:
                price_query = "MATCH (other)-[:HAS]->(price:Price)"
                price_where = "AND price.value >= $min AND price.value <= $max AND price.currency = $currency"
            elif price.get("min") is not None:
                price_query = "MATCH (other)-[:HAS]->(price:Price)"
                price_where = "AND price.value >= $min AND price.currency = $currency"
            elif price.get("max") is not None:
                price_query = "MATCH (other)-[:HAS]->(price:Price)"
                price_where = "AND price.value <= $max AND price.currency = $currency"

        labels = [type.replace("-", "_") for type in types]
        logger.debug(f"Labels: {labels}")
        variants = self.generate_ean_variants(ean) if ean else [pn]
        with self.get_neo4j_session() as session:
            for ean_variant in variants:
                query = (
                    f"MATCH (product:Product{product_query}) "
                    "OPTIONAL MATCH (product)-[:COMPATIBLE]-(other:Product) "
                )
                if price_query:
                    query += price_query + " "
                query += (
                    "WHERE other IS NOT NULL "
                )
                if price_where:
                    query += price_where + " "
                query += (
                    "AND any(label IN labels(other) WHERE label IN $labels) "
                    "RETURN "
                    "apoc.map.submap(product, ['EAN', 'name', 'producer', 'product_number', 'action']) AS product, "
                    "collect(apoc.map.submap(other, ['EAN', 'name', 'producer', 'product_number', 'action'])) AS compatible_products"
                )

                logger.info(query)
                properties = {
                    "ean": ean_variant,
                    "action": action,
                    "pn": pn,
                    "labels": labels,
                    "currency": currency,
                    "requiredProperties": params.get("requiredProperties")
                }
                if price:
                    if price.get("equal") is not None:
                        properties["equal"] = price["equal"]
                    if price.get("min") is not None:
                        properties["min"] = price["min"]
                    if price.get("max") is not None:
                        properties["max"] = price["max"]

                result = session.execute_read(self._execute_query_multiple, query, properties)
                logger.debug(result)
                if result:
                    return result[0][1]

        return None

    def filter_compatible_products(self, eans=[], params={}):
        logger.info(eans)
        logger.info(params)
        query = """
        MATCH (product:Product)
        WHERE product.EAN IN $eans 
        OPTIONAL MATCH (product)-[:HAS]->(prop:Property_PL) 
        WITH product, collect({
  name: prop.name,
  value: prop.value,
  unit: prop.unit
}) as properties
WHERE size([reqProp IN $requiredProperties WHERE
  size([prop IN properties WHERE
    prop.name = reqProp.name AND
    (
      (apoc.meta.cypher.type(reqProp.value) IN ["LIST OF ANY", "LIST OF STRING"] AND toLower(toString(prop.value)) IN reqProp.value) OR
      (reqProp.condition = '<>' AND apoc.meta.cypher.type(reqProp.value) = 'STRING' AND toLower(toString(prop.value)) <> toLower(toString(reqProp.value))) OR
      (reqProp.condition = '<>' AND apoc.meta.cypher.type(reqProp.value) <> 'STRING' AND prop.value <> reqProp.value) OR
      (reqProp.condition = '<' AND prop.value < reqProp.value) OR
      (reqProp.condition = '>' AND prop.value > reqProp.value) OR
      (reqProp.condition = '<=' AND prop.value <= reqProp.value) OR
      (reqProp.condition = '>=' AND prop.value >= reqProp.value) OR
      ((reqProp.condition IS NULL OR reqProp.condition = '=') AND apoc.meta.cypher.type(reqProp.value) = 'STRING' AND toLower(toString(prop.value)) = toLower(toString(reqProp.value))) OR
      ((reqProp.condition IS NULL OR reqProp.condition = '=') AND apoc.meta.cypher.type(reqProp.value) = 'INTEGER' AND apoc.meta.cypher.type(prop.value) = 'STRING' AND prop.value STARTS WITH toString(reqProp.value)) OR
      ((reqProp.condition IS NULL OR reqProp.condition = '=') AND (prop.value = reqProp.value))
    ) AND
    (reqProp.unit IS NULL OR prop.unit = reqProp.unit)
  ]) > 0
]) = size($requiredProperties)
RETURN product
                """
        properties = {
            "eans": eans,
            "requiredProperties": params.get("requiredProperties")
        }
        with self.get_neo4j_session() as session:
            filtered_nodes =  session.run(query, properties)
            logger.info("filtered_nodes")
            logger.info(filtered_nodes)
            records = list(filtered_nodes)
            filtered_nodes = [record.data().get("product", {}) for record in records]
            for record in filtered_nodes:
                if record.get("nameEmbedding"):
                    del record["nameEmbedding"]
                if record.get("productNumberEmbedding"):
                    del record["productNumberEmbedding"]
            return filtered_nodes

    def get_product_price(self, action_code: str, currency: str):
        with self.get_neo4j_session() as session:
            #query = "MATCH (product:Product {action: $action_code})-[:HAS]->(price:Price {currency: $currency}) RETURN price"
            query = """MATCH (product:Product {action: $action_code})
                OPTIONAL MATCH (product)-[:HAS]->(price:Price{currency: "PLN"})
                RETURN product.EAN AS EAN, product.action AS action, product.name AS name, price"""
            properties = {"action_code": action_code, "currency": currency}
            result = session.execute_read(self._execute_query_multiple, query, properties)
            logger.debug(result)
            if result:
                return result[0]
        return None

    def update_price_value(self, price_id, new_value):
        query = """
            MATCH (price:Price)
            WHERE elementId(price) = $price_id
            SET price.value = $new_value
            RETURN price
        """
        with self.get_neo4j_session() as session:
            return session.execute_write(lambda tx: tx.run(
                                                        query,
                                                        price_id=price_id,
                                                        new_value=new_value
                                                    ).single())

    def get_product_with_parameters(self, ean: str):
        variants = self.generate_ean_variants(ean)
        ean_in_db = None
        with self.get_neo4j_session() as session:
            for ean_variant in variants:
                query = "MATCH (product:Product {EAN: $ean})" + \
                        "RETURN apoc.map.clean(product, ['EAN', 'name', 'producer', 'product_number', 'action'], []) AS product;"
                properties = {"ean": ean_variant}
                result = session.execute_read(self._execute_query_multiple, query, properties)
                logger.debug(result)
                if result:
                    ean_in_db = ean_variant
                    break
            if not ean_in_db:
                return None

            query = """
                    MATCH (prod:Product {EAN: $ean})
                    OPTIONAL MATCH (prod)-[r:HAS]->(prop:Property_PL)
                    WHERE prop.default_unit IS NULL OR prop.default_unit = true
                    WITH prod, 
                         collect({
                           name: prop.name,
                           value: prop.value,
                           unit: prop.unit,
                           section: r.section_name,
                           section_sort: r.section_sort,
                           attribute_sort: r.attribute_sort
                         }) as properties
                    WITH prod, 
                         [x IN properties | x] AS props
                    UNWIND props AS p
                    WITH prod, p
                    ORDER BY p.section_sort ASC, p.attribute_sort ASC
                    WITH prod, collect(p) AS sorted_properties
                    RETURN {
                      EAN: prod.EAN,
                      name: prod.name,
                      producer: prod.producer,
                      action: prod.action,
                      product_number: prod.product_number,
                      properties: sorted_properties
                    } as product
                    """
            properties = {"ean": ean_in_db}
            logger.debug(properties)
            result = session.execute_read(self._execute_query, query, properties)
            logger.debug(result)
            return result

    def get_product_by_action_code(self, action_code: str, with_parameters=False):
        with self.get_neo4j_session() as session:
            query = "MATCH (product:Product {action: $action})" + \
                    "RETURN apoc.map.submap(product, ['EAN', 'name', 'producer', 'product_number', 'action']) AS product"
            properties = {"action": action_code}
            results = session.execute_read(self._execute_query_multiple, query, properties)

            if not results:
                return None
            logger.debug(results[0])
            if not with_parameters:
                return results[0]
            results_with_properties = []

            for result in results[0]:
                ean = result.get("EAN", "")
                logger.debug(f"ean: {ean}")
                query = """
                    MATCH (prod:Product {EAN: $ean})
                    OPTIONAL MATCH (prod)-[r:HAS]->(prop:Property_PL)
                    WHERE prop.default_unit IS NULL OR prop.default_unit = true
                    WITH prod, 
                         collect({
                           name: prop.name,
                           value: prop.value,
                           unit: prop.unit,
                           section: r.section_name,
                           section_sort: r.section_sort,
                           attribute_sort: r.attribute_sort
                         }) as properties
                    UNWIND properties AS p
                    WITH prod, p
                    ORDER BY p.section_sort ASC, p.attribute_sort ASC
                    WITH prod, collect({
                      name: p.name,
                      value: p.value,
                      unit: p.unit,
                      section: p.section
                    }) AS sorted_properties
                    RETURN {
                      EAN: prod.EAN,
                      name: prod.name,
                      producer: prod.producer,
                      action: prod.action,
                      product_number: prod.product_number,
                      properties: sorted_properties
                    } AS product
                                """
                properties = {"ean": ean}
                result_with_properties = session.execute_read(self._execute_query, query, properties)
                results_with_properties.append(result_with_properties[0])
            return results_with_properties

    def get_product_by_pn_vector(self, pn: str, with_parameters=False):
        response = self.client_gpt.embeddings.create(
            model=self.embeddings_model,
            input=pn
        )
        query_vector = response.data[0].embedding
        with self.driver.session() as session:
            results = session.read_transaction(find_similar_pn, query_vector)
            logger.debug(results)
            if not with_parameters:
                return results

            results_with_properties = []
            for result in results:
                ean = result.get("EAN", "")
                logger.debug(f"ean: {ean}")
                query = """
                    MATCH (prod:Product{EAN: $ean})
                    OPTIONAL MATCH (prod)-[r:HAS]->(prop:Property_PL)
                    WHERE prop.default_unit IS NULL OR prop.default_unit = true
                    WITH prod, 
                        collect({
                          name: prop.name,
                          value: prop.value,
                          unit: prop.unit,
                          section: r.section_name
                        }) as properties
                    RETURN {
                      EAN: prod.EAN,
                      name: prod.name,
                      producer: prod.producer,
                      action: prod.action,
                      product_number: prod.product_number,
                      properties: properties
                    } as product
                    """
                properties = {"ean": ean}
                result_with_properties = session.execute_read(self._execute_query, query, properties)
                results_with_properties.append(result_with_properties[0])
            return results_with_properties

    def get_product_by_pn(self, pn: str, with_parameters=False):
        pn = re.sub(r'(?<!\\)"', r'\"', pn)
        with self.driver.session() as session:
            results = session.read_transaction(find_products_fulltext_by_pn, pn)
            logger.debug(results)
            if not with_parameters:
                return results

            results_with_properties = []
            for result in results:
                ean = result.get("EAN", "")
                logger.debug(f"ean: {ean}")
                query = """
                    MATCH (prod:Product {EAN: $ean})
                    OPTIONAL MATCH (prod)-[r:HAS]->(prop:Property_PL)
                    WHERE prop.default_unit IS NULL OR prop.default_unit = true
                    WITH prod, 
                         collect({
                           name: prop.name,
                           value: prop.value,
                           unit: prop.unit,
                           section: r.section_name,
                           section_sort: r.section_sort,
                           attribute_sort: r.attribute_sort
                         }) as properties
                    WITH prod, 
                         [x IN properties | x] AS props
                    UNWIND props AS p
                    WITH prod, p
                    ORDER BY p.section_sort ASC, p.attribute_sort ASC
                    WITH prod, collect(p) AS sorted_properties
                    RETURN {
                      EAN: prod.EAN,
                      name: prod.name,
                      producer: prod.producer,
                      action: prod.action,
                      product_number: prod.product_number,
                      properties: sorted_properties
                    } as product
                    """
                properties = {"ean": ean}
                result_with_properties = session.execute_read(self._execute_query, query, properties)
                results_with_properties.append(result_with_properties[0])
            return results_with_properties


    def get_product_by_name_vector(self, name:str, n = 10, with_parameters=False, similarity = None):
        response = self.client_gpt.embeddings.create(
            model=self.embeddings_model,
            input=name
        )
        query_vector = response.data[0].embedding
        with self.driver.session() as session:
            results = session.read_transaction(find_similar_products, query_vector, n, similarity)
            logger.debug(results)
            if not with_parameters:
                return results
            results_with_properties = []
            for result in results:
                ean = result.get("EAN", "")
                logger.debug(f"ean: {ean}")
                query = """
                    MATCH (prod:Product {EAN: $ean})
                    OPTIONAL MATCH (prod)-[r:HAS]->(prop:Property_PL)
                    WHERE prop.default_unit IS NULL OR prop.default_unit = true
                    WITH prod, 
                         collect({
                           name: prop.name,
                           value: prop.value,
                           unit: prop.unit,
                           section: r.section_name,
                           section_sort: r.section_sort,
                           attribute_sort: r.attribute_sort
                         }) as properties
                    UNWIND properties AS p
                    WITH prod, p
                    ORDER BY p.section_sort ASC, p.attribute_sort ASC
                    WITH prod, collect({
                      name: p.name,
                      value: p.value,
                      unit: p.unit,
                      section: p.section
                    }) AS sorted_properties
                    RETURN {
                      EAN: prod.EAN,
                      name: prod.name,
                      producer: prod.producer,
                      action: prod.action,
                      product_number: prod.product_number,
                      properties: sorted_properties
                    } AS product
                    """
                properties = {"ean": ean}
                result_with_properties = session.execute_read(self._execute_query, query, properties)
                results_with_properties.append(result_with_properties[0])
            return results_with_properties

    def get_product_by_name(self, name:str, n = 10, with_parameters=False, similarity = None):
        # response = self.client_gpt.embeddings.create(
        #     model=self.embeddings_model,
        #     input=name
        # )
        # query_vector = response.data[0].embedding
        name = re.sub(r'(?<!\\)"', r'\"', name)
        with self.driver.session() as session:
            results = session.read_transaction(find_products_fulltext, name, n, similarity)
            logger.debug(results)
            if not with_parameters:
                return results

            results_with_properties = []
            for result in results:
                ean = result.get("EAN", "")
                logger.debug(f"ean: {ean}")
                query = """
                    MATCH (prod:Product {EAN: $ean})
                    OPTIONAL MATCH (prod)-[r:HAS]->(prop:Property_PL)
                    WHERE prop.default_unit IS NULL OR prop.default_unit = true
                    WITH prod, 
                         collect({
                           name: prop.name,
                           value: prop.value,
                           unit: prop.unit,
                           section: r.section_name,
                           section_sort: r.section_sort,
                           attribute_sort: r.attribute_sort
                         }) as properties
                    WITH prod, 
                         [x IN properties | x] AS props
                    UNWIND props AS p
                    WITH prod, p
                    ORDER BY p.section_sort ASC, p.attribute_sort ASC
                    WITH prod, collect(p) AS sorted_properties
                    RETURN {
                      EAN: prod.EAN,
                      name: prod.name,
                      producer: prod.producer,
                      action: prod.action,
                      product_number: prod.product_number,
                      properties: sorted_properties
                    } as product
                    """
                properties = {"ean": ean}
                result_with_properties = session.execute_read(self._execute_query, query, properties)
                results_with_properties.append(result_with_properties[0])
            return results_with_properties

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
            result = session.execute_write(self._execute_query_records, query, properties)
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

    def add_properties_to_bidirectional_relationship(self, type1_code, type2_code, relationship_properties1={}, relationship_properties2={}):
        with self.driver.session() as session:
            result = session.write_transaction(
                self._create_properties_to_bidirectional_relationship,
                type1_code, type2_code, relationship_properties1, relationship_properties2
            )
            return result

    @staticmethod
    def _create_properties_to_bidirectional_relationship(tx, type1_code, type2_code,
                                                           relationship_properties1, relationship_properties2):
        logger.info(relationship_properties1)
        logger.info(type(relationship_properties1))
        logger.info(relationship_properties2)
        logger.info(type(relationship_properties2))
        query = (
            """MATCH (a {code: $type1_code}), (b {code: $type2_code})
                MERGE (a)-[r1:TYPES_COMPATIBLE]->(b)
                SET r1 += $props1
                MERGE (b)-[r2:TYPES_COMPATIBLE]->(a)
                SET r2 += $props2
                RETURN r1, r2"""
        )
        result = tx.run(query, type1_code=type1_code, type2_code=type2_code,
                        props1=relationship_properties1, props2=relationship_properties2)
        return result.single()

    def add_products_bidirectional_relationship_with_properties(self, ean1, ean2, relationship_type, relationship_properties1={}, relationship_properties2={}):
        with self.driver.session() as session:
            result = session.write_transaction(
                self._create_products_bidirectional_relationship_with_properties,
                ean1, ean2, relationship_type, relationship_properties1, relationship_properties2
            )
            return result

    @staticmethod
    def _create_products_bidirectional_relationship_with_properties(tx, ean1, ean2, relationship_type,
                                                           relationship_properties1, relationship_properties2):
        query = (
            "MATCH (a:Product {EAN: $ean1}), (b:Product {EAN: $ean2}) "
            f"MERGE (a)-[r1:{relationship_type}]->(b) "
            "ON CREATE SET r1 += $props1 "
            f"MERGE (b)-[r2:{relationship_type}]->(a) "
            "ON CREATE SET r2 += $props2 "
            "RETURN a, b, r1, r2"
        )
        result = tx.run(query, ean1=ean1, ean2=ean2,
                        props1=relationship_properties1, props2=relationship_properties2)
        return result.single()


    def get_products(self, skip=0, limit=100):
        query = """MATCH (product:Product)
                    WITH product, apoc.map.setKey(product, 'action', coalesce(product.action, null)) as productWithAction
                    RETURN apoc.map.submap(productWithAction, ['EAN', 'name', 'producer', 'product_number', 'action']) AS product
                    SKIP $skip
                    LIMIT $limit;"""

        with self.driver.session() as session:
            result = session.run(query, skip=skip, limit=limit)
            logger.debug(result)
            nodes = [record["product"] for record in result]
            return nodes


    def get_products_with_parameters(self, skip=0, limit=100, type=None):
        label = type if type else "Product"
        query = f"""
            MATCH (prod:{label})
            OPTIONAL MATCH (prod)-[r:HAS]->(prop:Property_PL)
            WITH prod, 
                 collect({{
                   name: prop.name,
                   value: prop.value,
                   unit: prop.unit,
                   section_sort: r.section_sort,
                   attribute_sort: r.attribute_sort
                 }}) as properties
            UNWIND properties AS p
            WITH prod, p
            ORDER BY p.section_sort ASC, p.attribute_sort ASC
            WITH prod, collect({{
              name: p.name,
              value: p.value,
              unit: p.unit
            }}) AS sorted_properties
            RETURN {{
              EAN: prod.EAN,
              name: prod.name,
              producer: prod.producer,
              action: prod.action,
              product_number: prod.product_number,
              properties: sorted_properties
            }} AS product
            SKIP $skip
            LIMIT $limit
        """

        with self.driver.session() as session:
            result = session.run(query, skip=skip, limit=limit)
            nodes = [record["product"] for record in result]
            return nodes

    def create_product_price(self, action_code, price, currency, quantity):
        with self.driver.session() as session:
            query = """
            MATCH (product:Product {action: $action_code})
            CREATE (product)-[:HAS]->(price:Price {value: $price, currency: $currency, quantity: $quantity})
            RETURN price
            """
            properties = {
                "action_code": action_code,
                "price": price,
                "currency": currency,
                "quantity": quantity
            }
            result = session.execute_write(self._execute_query, query, properties)
            return result["price"] if result else None

    def get_params_values(self, names, types):
        cypher_query = '''
        MATCH (n)-[:HAS]->(p:Property_PL {name: $name})
        WHERE any(label in labels(n) WHERE label IN $labels)
        RETURN DISTINCT p.value
        '''

        params_values = {}
        with self.driver.session() as session:
            for name in names:
                name_params = {'name': name, 'labels': types}
                logger.debug(name_params)
                result: Result = session.run(cypher_query, name_params)
                name_values = [v[0] for v in result.values()]
                logger.debug(name_values)
                params_values[name] = name_values

        return params_values