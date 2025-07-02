import json
import time

import psycopg2
from psycopg2.extras import Json

class SpiffConnector:
    def __init__(self, user, password, host, port, database):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.database = database

    def connect(self):
        return psycopg2.connect(
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database
        )

    def close_connection(self, connection):
        connection.close()

    def execute_query(self, connection, query):
        cursor = connection.cursor()
        cursor.execute(query)
        records = cursor.fetchall()
        cursor.close()
        return records

    def execute_insert(self, connection, query, values):
        cursor = connection.cursor()
        try:
            cursor.execute(query, values)
            connection.commit()
        except Exception as e:
            connection.rollback()
            print("Błąd podczas wstawiania:", e)
        finally:
            cursor.close()
            connection.close()
        return None


    def get_process_instances_ids_by_identifier(self, process_model_identifier, status=None):
        if status:
            query = f"SELECT id FROM public.process_instance WHERE process_model_identifier = '{process_model_identifier}' AND status = '{status}';"
        else:
            query = f"SELECT id FROM public.process_instance WHERE process_model_identifier = '{process_model_identifier}';"

        connection = self.connect()
        try:
            records = self.execute_query(connection, query)
            return [r[0] for r in records]
        finally:
            self.close_connection(connection)


    def get_tasks_with_max_end_in_seconds(self, process_instance_ids):
        ids = ', '.join(f"'{id}'" for id in process_instance_ids)
        query = f"""
        SELECT DISTINCT ON (process_instance_id) bpmn_process_id, process_instance_id, state, json_data_hash
        FROM public.task
        WHERE process_instance_id IN ({ids}) AND state = 'COMPLETED'
        ORDER BY process_instance_id, start_in_seconds DESC;
        """

        connection = self.connect()
        try:
            records = self.execute_query(connection, query)
            return records
        finally:
            self.close_connection(connection)


    def get_tasks_by_name(self, process_instance_ids, name):
        ids = ', '.join(f"'{id}'" for id in process_instance_ids)
        query = f"""
        SELECT DISTINCT ON (t.process_instance_id) t.bpmn_process_id, t.process_instance_id, t.task_definition_id, t.json_data_hash
        FROM public.task t
        JOIN public.task_definition td ON t.task_definition_id = td.id
        WHERE t.process_instance_id IN ({ids}) AND td.bpmn_name = '{name}' AND t.state = 'COMPLETED'
        ORDER BY t.process_instance_id DESC;
        """

        connection = self.connect()
        try:
            records = self.execute_query(connection, query)
            return records
        finally:
            self.close_connection(connection)

    def get_json_data_by_hash(self, json_data_hash):
        query = f"SELECT * FROM public.json_data WHERE hash = '{json_data_hash}';"

        connection = self.connect()
        try:
            records = self.execute_query(connection, query)
            return records[0][1] if records else None
        finally:
            self.close_connection(connection)

    def get_value_from_data_store(self, data_store_name, top_level_key, secondary_key):
        query = f"SELECT id FROM public.kkv_data_store WHERE identifier = '{data_store_name}';"

        connection = self.connect()
        try:
            records = self.execute_query(connection, query)
            kkv_data_store_id = records[0][0]
            query = f"""SELECT value FROM public.kkv_data_store_entry WHERE kkv_data_store_id = '{kkv_data_store_id}' 
            AND top_level_key = '{top_level_key}' AND secondary_key = '{secondary_key}';"""
            records = self.execute_query(connection, query)
            if not records:
                return None
            return records[0][0]

        finally:
            self.close_connection(connection)

    def get_values_from_data_store(self, data_store_name, top_level_key):
        query = f"SELECT id FROM public.kkv_data_store WHERE identifier = '{data_store_name}';"

        connection = self.connect()
        try:
            records = self.execute_query(connection, query)
            kkv_data_store_id = records[0][0]
            query = f"""SELECT secondary_key, value FROM public.kkv_data_store_entry WHERE kkv_data_store_id = '{kkv_data_store_id}' 
            AND top_level_key = '{top_level_key}';"""
            records = self.execute_query(connection, query)
            if not records:
                return None
            return records

        finally:
            self.close_connection(connection)


    def add_value_to_data_store(self, data_store_name, top_level_key, secondary_key, value):
        query = f"SELECT id FROM public.kkv_data_store WHERE identifier = '{data_store_name}';"

        connection = self.connect()
        try:
            records = self.execute_query(connection, query)
            kkv_data_store_id = records[0][0]
            query = """
        INSERT INTO public.kkv_data_store_entry (
            kkv_data_store_id, top_level_key, secondary_key, value, created_at_in_seconds, updated_at_in_seconds
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """
            now_seconds = int(time.time())
            values = (kkv_data_store_id, top_level_key, secondary_key, Json(value), now_seconds, now_seconds)
            self.execute_insert(connection, query, values)
        finally:
            self.close_connection(connection)

    def update_value_to_data_store(self, data_store_name, top_level_key, secondary_key, value):
        query = f"SELECT id FROM public.kkv_data_store WHERE identifier = '{data_store_name}';"

        connection = self.connect()
        try:
            records = self.execute_query(connection, query)
            kkv_data_store_id = records[0][0]
            query = """
        INSERT INTO public.kkv_data_store_entry (
            kkv_data_store_id, top_level_key, secondary_key, value, created_at_in_seconds, updated_at_in_seconds
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (kkv_data_store_id, top_level_key, secondary_key)
        DO UPDATE SET
            value = EXCLUDED.value,
            updated_at_in_seconds = EXCLUDED.updated_at_in_seconds
        """
            now_seconds = int(time.time())
            values = (kkv_data_store_id, top_level_key, secondary_key, Json(value), now_seconds, now_seconds)
            self.execute_insert(connection, query, values)
        finally:
            self.close_connection(connection)