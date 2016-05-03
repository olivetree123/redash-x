from flask import request
from flask_restful import abort
from flask_login import login_required
import sqlparse

from funcy import distinct, take
from itertools import chain

from redash.handlers.query_results import run_query
from redash import models
from redash.wsgi import app, api
from redash.permissions import require_permission, require_access, require_admin_or_owner, not_view_only, view_only
from redash.handlers.base import BaseResource, get_object_or_404
from redash.utils import collect_parameters_from_request


@app.route('/api/queries/format', methods=['POST'])
@login_required
def format_sql_query():
    arguments = request.get_json(force=True)
    query = arguments.get("query", "")

    return sqlparse.format(query, reindent=True, keyword_case='upper')


class QuerySearchAPI(BaseResource):
    @require_permission('view_query')
    def get(self):
        term = request.args.get('q', '')

        return [q.to_dict() for q in models.Query.search(term, self.current_user.groups)]


class QueryRecentAPI(BaseResource):
    @require_permission('view_query')
    def get(self):
        queries = models.Query.recent(self.current_user.groups, self.current_user.id)
        recent = [d.to_dict(with_last_modified_by=False) for d in queries]

        global_recent = []
        if len(recent) < 10:
            global_recent = [d.to_dict(with_last_modified_by=False) for d in models.Query.recent(self.current_user.groups)]

        return take(20, distinct(chain(recent, global_recent), key=lambda d: d['id']))


class QueryListAPI(BaseResource):
    @require_permission('create_query')
    def post(self):
        query_def = request.get_json(force=True)
        data_source = models.DataSource.get_by_id_and_org(query_def.pop('data_source_id'), self.current_org)
        require_access(data_source.groups, self.current_user, not_view_only)

        for field in ['id', 'created_at', 'api_key', 'visualizations', 'latest_query_data', 'last_modified_by']:
            query_def.pop(field, None)

        query_def['user'] = self.current_user
        query_def['data_source'] = data_source
        query_def['org'] = self.current_org
        query = models.Query.create(**query_def)

        return query.to_dict()

    @require_permission('view_query')
    def get(self):
        return [q.to_dict(with_stats=True) for q in models.Query.all_queries(self.current_user.groups)]


class QueryAPI(BaseResource):
    @require_permission('edit_query')
    def post(self, query_id):
        query = get_object_or_404(models.Query.get_by_id_and_org, query_id, self.current_org)
        require_admin_or_owner(query.user_id)

        query_def = request.get_json(force=True)
        for field in ['id', 'created_at', 'api_key', 'visualizations', 'latest_query_data', 'user', 'last_modified_by', 'org']:
            query_def.pop(field, None)

        # TODO(@arikfr): after running a query it updates all relevant queries with the new result. So is this really
        # needed?
        if 'latest_query_data_id' in query_def:
            query_def['latest_query_data'] = query_def.pop('latest_query_data_id')

        if 'data_source_id' in query_def:
            query_def['data_source'] = query_def.pop('data_source_id')

        query_def['last_modified_by'] = self.current_user

        query.update_instance(**query_def)

        return query.to_dict(with_visualizations=True)

    @require_permission('view_query')
    def get(self, query_id):
        q = get_object_or_404(models.Query.get_by_id_and_org, query_id, self.current_org)
        require_access(q.groups, self.current_user, view_only)

        if q:
            return q.to_dict(with_visualizations=True)
        else:
            abort(404, message="Query not found.")

    # TODO: move to resource of its own? (POST /queries/{id}/archive)
    def delete(self, query_id):
        query = get_object_or_404(models.Query.get_by_id_and_org, query_id, self.current_org)
        require_admin_or_owner(query.user_id)
        query.archive()


class QueryRefreshResource(BaseResource):
    def post(self, query_id):
        query = get_object_or_404(models.Query.get_by_id_and_org, query_id, self.current_org)
        require_access(query.groups, self.current_user, not_view_only)

        parameter_values = collect_parameters_from_request(request.args)

        return run_query(query.data_source, parameter_values, query.query, query.id)


api.add_org_resource(QuerySearchAPI, '/api/queries/search', endpoint='queries_search')
api.add_org_resource(QueryRecentAPI, '/api/queries/recent', endpoint='recent_queries')
api.add_org_resource(QueryListAPI, '/api/queries', endpoint='queries')
api.add_org_resource(QueryRefreshResource, '/api/queries/<query_id>/refresh', endpoint='query_refresh')
api.add_org_resource(QueryAPI, '/api/queries/<query_id>', endpoint='query')
