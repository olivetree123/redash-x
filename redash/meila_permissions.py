#coding:utf-8

from flask_login import current_user

from redash import models

def require_group_permission(func):
    def fun2(*args,**kwargs):
        if current_user.name == 'admin':
            return func(*args,**kwargs)
        dashboard_slug = kwargs.get('dashboard_slug','')
        ds = models.Dashboard.get_by_slug_group(dashboard_slug,current_user.groups)
        x = [d for d in ds]
        if x:
            return func(*args,**kwargs)
        else:
            return {}
    return fun2
