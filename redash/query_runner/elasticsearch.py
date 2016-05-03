import json
import logging
import sys
import urllib
from requests.auth import HTTPBasicAuth

from redash.query_runner import *

import requests

try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client

logger = logging.getLogger(__name__)

ELASTICSEARCH_TYPES_MAPPING = {
    "integer" : TYPE_INTEGER,
    "long" : TYPE_INTEGER,
    "float" : TYPE_FLOAT,
    "double" : TYPE_FLOAT,
    "boolean" : TYPE_BOOLEAN,
    "string" : TYPE_STRING,
    "date" : TYPE_DATE,
    "object" : TYPE_STRING,
    # "geo_point" TODO: Need to split to 2 fields somehow
}

ELASTICSEARCH_BUILTIN_FIELDS_MAPPING = {
    "_id" : "Id",
    "_score" : "Score"
}

PYTHON_TYPES_MAPPING = {
    str: TYPE_STRING,
    unicode: TYPE_STRING,
    bool : TYPE_BOOLEAN,
    int : TYPE_INTEGER,
    long: TYPE_INTEGER,
    float: TYPE_FLOAT
}

class BaseElasticSearch(BaseQueryRunner):

    DEBUG_ENABLED = True

    @classmethod
    def configuration_schema(cls):
        return {
            'type': 'object',
            'properties': {
                'server': {
                    'type': 'string',
                    'title': 'Base URL'
                },
                'basic_auth_user': {
                    'type': 'string',
                    'title': 'Basic Auth User'
                },
                'basic_auth_password': {
                    'type': 'string',
                    'title': 'Basic Auth Password'
                }
            },
            "required" : ["server"]
        }

    @classmethod
    def enabled(cls):
        return False

    def __init__(self, configuration):
        super(BaseElasticSearch, self).__init__(configuration)

        self.syntax = "json"

        if self.DEBUG_ENABLED:
            http_client.HTTPConnection.debuglevel = 1

            # you need to initialize logging, otherwise you will not see anything from requests
            logging.basicConfig()
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True

            logger.setLevel(logging.DEBUG)

        self.server_url = self.configuration["server"]
        if self.server_url[-1] == "/":
            self.server_url = self.server_url[:-1]

        basic_auth_user = self.configuration.get("basic_auth_user", None)
        basic_auth_password = self.configuration.get("basic_auth_password", None)
        self.auth = None
        if basic_auth_user and basic_auth_password:
            self.auth = HTTPBasicAuth(basic_auth_user, basic_auth_password)

    def _get_mappings(self, url):
        mappings = {}

        r = requests.get(url, auth=self.auth)
        mappings_data = r.json()

        logger.debug(mappings_data)

        for index_name in mappings_data:
            index_mappings = mappings_data[index_name]
            for m in index_mappings.get("mappings", {}):
                for property_name in index_mappings["mappings"][m]["properties"]:
                    property_data = index_mappings["mappings"][m]["properties"][property_name]
                    if not property_name in mappings:
                        property_type = property_data.get("type", None)
                        if property_type:
                            if property_type in ELASTICSEARCH_TYPES_MAPPING:
                                mappings[property_name] = property_type
                            else:
                                mappings[property_name] = TYPE_STRING
                                #raise Exception("Unknown property type: {0}".format(property_type))

        return mappings

    def _parse_results(self, mappings, result_fields, raw_result, result_columns, result_rows):

        def add_column_if_needed(mappings, column_name, friendly_name, result_columns, result_columns_index):
            if friendly_name not in result_columns_index:
                result_columns.append({
                    "name" : friendly_name,
                    "friendly_name" : friendly_name,
                    "type" : mappings.get(column_name, "string")})
                result_columns_index[friendly_name] = result_columns[-1]

        result_columns_index = {c["name"] : c for c in result_columns}

        result_fields_index = {}
        if result_fields:
            for r in result_fields:
                result_fields_index[r] = None

        for h in raw_result["hits"]["hits"]:
            row = {}

            for field, column in ELASTICSEARCH_BUILTIN_FIELDS_MAPPING.iteritems():
                if field in h:
                    add_column_if_needed(mappings, field, column, result_columns, result_columns_index)
                    row[column] = h[field]

            column_name = "_source" if "_source" in h else "fields"
            for column in h[column_name]:
                if result_fields and column not in result_fields_index:
                    continue

                add_column_if_needed(mappings, column, column, result_columns, result_columns_index)

                value = h[column_name][column]
                row[column] = value[0] if isinstance(value, list) and len(value) == 1 else value


            if row and len(row) > 0:
                result_rows.append(row)


class Kibana(BaseElasticSearch):

    def __init__(self, configuration):
        super(Kibana, self).__init__(configuration)

    @classmethod
    def enabled(cls):
        return True

    @classmethod
    def annotate_query(cls):
        return False

    def _execute_simple_query(self, url, auth, _from, mappings, result_fields, result_columns, result_rows):
        url += "&from={0}".format(_from)
        r = requests.get(url, auth=self.auth)
        if r.status_code != 200:
            raise Exception("Failed to execute query. Return Code: {0}   Reason: {1}".format(r.status_code, r.text))

        raw_result = r.json()

        self._parse_results(mappings, result_fields, raw_result, result_columns, result_rows)

        total = raw_result["hits"]["total"]
        result_size = len(raw_result["hits"]["hits"])
        logger.debug("Result Size: {0}  Total: {1}".format(result_size, total))

        return raw_result["hits"]["total"]

    def run_query(self, query):
        try:
            error = None

            logger.debug(query)
            query_params = json.loads(query)

            index_name = query_params["index"]
            query_data = query_params["query"]
            size = int(query_params.get("size", 500))
            limit = int(query_params.get("limit", 500))
            result_fields = query_params.get("fields", None)
            sort = query_params.get("sort", None)

            if not self.server_url:
                error = "Missing configuration key 'server'"
                return None, error

            url = "{0}/{1}/_search?".format(self.server_url, index_name)
            mapping_url = "{0}/{1}/_mapping".format(self.server_url, index_name)

            mappings = self._get_mappings(mapping_url)

            logger.debug(json.dumps(mappings, indent=4))

            if sort:
                url += "&sort={0}".format(urllib.quote_plus(sort))

            url += "&q={0}".format(urllib.quote_plus(query_data))

            logger.debug("Using URL: {0}".format(url))
            logger.debug("Using Query: {0}".format(query_data))

            result_columns = []
            result_rows = []
            if isinstance(query_data, str) or isinstance(query_data, unicode):
                _from = 0
                while True:
                    query_size = size if limit >= (_from + size) else (limit - _from)
                    total = self._execute_simple_query(url + "&size={0}".format(query_size), self.auth, _from, mappings, result_fields, result_columns, result_rows)
                    _from += size
                    if _from >= limit:
                        break
            else:
                # TODO: Handle complete ElasticSearch queries (JSON based sent over HTTP POST)
                raise Exception("Advanced queries are not supported")

            json_data = json.dumps({
                "columns" : result_columns,
                "rows" : result_rows
            })
        except KeyboardInterrupt:
            error = "Query cancelled by user."
            json_data = None
        except Exception as e:
            raise sys.exc_info()[1], None, sys.exc_info()[2]

        return json_data, error


class ElasticSearch(BaseElasticSearch):

    def __init__(self, configuration):
        super(ElasticSearch, self).__init__(configuration)

    @classmethod
    def enabled(cls):
        return True

    @classmethod
    def annotate_query(cls):
        return False

    def run_query(self, query):
        try:
            error = None

            logger.debug(query)
            query_dict = json.loads(query)

            index_name = query_dict.pop("index", "")

            if not self.server_url:
                error = "Missing configuration key 'server'"
                return None, error

            url = "{0}/{1}/_search".format(self.server_url, index_name)
            mapping_url = "{0}/{1}/_mapping".format(self.server_url, index_name)

            mappings = self._get_mappings(mapping_url)

            logger.debug(json.dumps(mappings, indent=4))

            params = {"source": json.dumps(query_dict)}
            logger.debug("Using URL: %s", url)
            logger.debug("Using params : %s", params)
            r = requests.get(url, params=params, auth=self.auth)
            logger.debug("Result: %s", r.json())

            result_columns = []
            result_rows = []
            self._parse_results(mappings, None, r.json(), result_columns, result_rows)

            json_data = json.dumps({
                "columns" : result_columns,
                "rows" : result_rows
            })
        except KeyboardInterrupt:
            error = "Query cancelled by user."
            json_data = None
        except Exception as e:
            raise sys.exc_info()[1], None, sys.exc_info()[2]

        return json_data, error


register(Kibana)
register(ElasticSearch)
