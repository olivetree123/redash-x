from flask import request

from funcy import distinct, take
from itertools import chain

from redash import models
from redash.wsgi import api
from redash.permissions import require_permission
from redash.meila_permissions import require_group_permission
from redash.handlers.base import BaseResource, get_object_or_404


class DashboardRecentAPI(BaseResource):
    def get(self):
        recent = [d.to_dict() for d in models.Dashboard.recent(self.current_org, self.current_user.id)]

        global_recent = []
        if len(recent) < 10:
            global_recent = [d.to_dict() for d in models.Dashboard.recent(self.current_org)]

        return take(20, distinct(chain(recent, global_recent), key=lambda d: d['id']))


class DashboardListAPI(BaseResource):
    def get(self):
        if self.current_user.name != 'admin':
            dashboards = [d.to_dict() for d in models.Dashboard.get_by_groups(self.current_user.groups)]
        else:
            dashboards = [d.to_dict() for d in models.Dashboard.all()]
        #dashboards = [d.to_dict() for d in models.Dashboard.all(self.current_org)]

        return dashboards

    @require_permission('create_dashboard')
    def post(self):
        dashboard_properties = request.get_json(force=True)
        dashboard = models.Dashboard(name=dashboard_properties['name'],
                                     org=self.current_org,
                                     user=self.current_user,
                                     layout='[]')
        dashboard.save()
        return dashboard.to_dict()


class DashboardAPI(BaseResource):
    @require_group_permission
    def get(self, dashboard_slug=None):
        dashboard = get_object_or_404(models.Dashboard.get_by_slug_and_org, dashboard_slug, self.current_org)

        return dashboard.to_dict(with_widgets=True, user=self.current_user)

    @require_permission('edit_dashboard')
    def post(self, dashboard_slug):
        dashboard_properties = request.get_json(force=True)
        # TODO: either convert all requests to use slugs or ids
        dashboard = models.Dashboard.get_by_id_and_org(dashboard_slug, self.current_org)
        dashboard.layout = dashboard_properties['layout']
        dashboard.name = dashboard_properties['name']
        dashboard.save()

        return dashboard.to_dict(with_widgets=True, user=self.current_user)

    @require_permission('edit_dashboard')
    def delete(self, dashboard_slug):
        dashboard = models.Dashboard.get_by_slug_and_org(dashboard_slug, self.current_org)
        dashboard.is_archived = True
        dashboard.save()

        return dashboard.to_dict(with_widgets=True, user=self.current_user)

class DashboardGroupAPI(BaseResource):
    def post(self):
        print '----- add group ------'
        args = request.get_json(force=True)
        print 'args : ',args
        dashboard_id = int(args.get('dashboard_id',0))
        group_id = int(args.get('group_id',0))
        if not (dashboard_id and group_id):
            return 'failed'
        dashboard = models.Dashboard.get_by_id(dashboard_id)
        if not dashboard.groups:
            dashboard.groups = [group_id]
        elif not group_id in dashboard.groups:
            dashboard.groups.append(group_id)
        dashboard.save()
        group = models.Group.get_by_id(group_id)
        return {'name':group.name,'id':str(group.id)}

class DashboardDelGroupAPI(BaseResource):

    @require_permission('edit_dashboard')
    def post(self):
        args = request.get_json(force=True)
        dashboard_id = args['dashboard_id']
        group_id = args['group_id']
        dashboard = models.Dashboard.get_by_id(dashboard_id)
        groups = set(dashboard.groups)
        groups = groups - set([group_id])
        dashboard.groups = list(groups)
        dashboard.save()
        return {'group_id':group_id}


api.add_org_resource(DashboardListAPI, '/api/dashboards', endpoint='dashboards')
api.add_org_resource(DashboardRecentAPI, '/api/dashboards/recent', endpoint='recent_dashboards')
api.add_org_resource(DashboardAPI, '/api/dashboards/<dashboard_slug>', endpoint='dashboard')
api.add_org_resource(DashboardGroupAPI, '/api/dashboards/group', endpoint='dashboard_group')
api.add_org_resource(DashboardDelGroupAPI, '/api/dashboards/delgroup', endpoint='dashboard_del_group')
