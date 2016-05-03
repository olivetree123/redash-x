import json
from unittest import TestCase
from flask import url_for
from flask_login import current_user
from mock import patch
from tests import BaseTestCase
from tests.handlers import authenticated_user, json_request
from redash import models, settings
from redash.wsgi import app


class AuthenticationTestMixin(object):
    def test_returns_404_when_not_unauthenticated(self):
        with app.test_client() as c:
            for path in self.paths:
                rv = c.get(path)
                self.assertEquals(404, rv.status_code)

    def test_returns_content_when_authenticated(self):
        for path in self.paths:
            rv = self.make_request('get', path, is_json=False)
            self.assertEquals(200, rv.status_code)


class TestAuthentication(BaseTestCase):
    def test_redirects_for_nonsigned_in_user(self):
        with app.test_client() as c:
            rv = c.get("/default/")
            self.assertEquals(302, rv.status_code)


class PingTest(TestCase):
    def test_ping(self):
        with app.test_client() as c:
            rv = c.get('/ping')
            self.assertEquals(200, rv.status_code)
            self.assertEquals('PONG.', rv.data)


class IndexTest(BaseTestCase):
    def setUp(self):
        self.paths = ['/default/', '/default/dashboard/example', '/default/queries/1', '/default/admin/status']
        super(IndexTest, self).setUp()

    def test_redirect_to_login_when_not_authenticated(self):
        with app.test_client() as c:
            for path in self.paths:
                rv = c.get(path)
                self.assertEquals(302, rv.status_code)

    def test_returns_content_when_authenticated(self):
        for path in self.paths:
            rv = self.make_request('get', path, org=False, is_json=False)
            self.assertEquals(200, rv.status_code)


class StatusTest(BaseTestCase):
    def test_returns_data_for_super_admin(self):
        admin = self.factory.create_admin()

        rv = self.make_request('get', '/status.json', org=False, user=admin, is_json=False)
        self.assertEqual(rv.status_code, 200)

    def test_returns_403_for_non_admin(self):
        rv = self.make_request('get', '/status.json', org=False, is_json=False)
        self.assertEqual(rv.status_code, 403)

    def test_redirects_non_authenticated_user(self):
        with app.test_client() as c:
            rv = c.get('/status.json')
            self.assertEqual(rv.status_code, 302)


class DashboardAPITest(BaseTestCase, AuthenticationTestMixin):
    def setUp(self):
        self.paths = ['/api/dashboards']
        super(DashboardAPITest, self).setUp()

    def test_get_dashboard(self):
        d1 = self.factory.create_dashboard()
        rv = self.make_request('get', '/api/dashboards/{0}'.format(d1.slug))
        self.assertEquals(rv.status_code, 200)

        expected = d1.to_dict(with_widgets=True)
        actual = json.loads(rv.data)

        self.assertResponseEqual(expected, actual)

    def test_get_dashboard_filters_unauthorized_widgets(self):
        dashboard = self.factory.create_dashboard()

        restricted_ds = self.factory.create_data_source(group=self.factory.create_group())
        query = self.factory.create_query(data_source=restricted_ds)
        vis = self.factory.create_visualization(query=query)
        restricted_widget = self.factory.create_widget(visualization=vis, dashboard=dashboard)
        widget = self.factory.create_widget(dashboard=dashboard)
        dashboard.layout = '[[{}, {}]]'.format(widget.id, restricted_widget.id)
        dashboard.save()

        rv = self.make_request('get', '/api/dashboards/{0}'.format(dashboard.slug))
        self.assertEquals(rv.status_code, 200)

        self.assertTrue(rv.json['widgets'][0][1]['restricted'])
        self.assertNotIn('restricted', rv.json['widgets'][0][0])

    def test_get_non_existing_dashboard(self):
        rv = self.make_request('get', '/api/dashboards/not_existing')
        self.assertEquals(rv.status_code, 404)

    def test_create_new_dashboard(self):
        dashboard_name = 'Test Dashboard'
        rv = self.make_request('post', '/api/dashboards', data={'name': dashboard_name})
        self.assertEquals(rv.status_code, 200)
        self.assertEquals(rv.json['name'], 'Test Dashboard')
        self.assertEquals(rv.json['user_id'], self.factory.user.id)
        self.assertEquals(rv.json['layout'], [])

    def test_update_dashboard(self):
        d = self.factory.create_dashboard()
        new_name = 'New Name'
        rv = self.make_request('post', '/api/dashboards/{0}'.format(d.id),
                               data={'name': new_name, 'layout': '[]'})
        self.assertEquals(rv.status_code, 200)
        self.assertEquals(rv.json['name'], new_name)

    def test_delete_dashboard(self):
        d = self.factory.create_dashboard()

        rv = self.make_request('delete', '/api/dashboards/{0}'.format(d.slug))
        self.assertEquals(rv.status_code, 200)

        d = models.Dashboard.get_by_slug_and_org(d.slug, d.org)
        self.assertTrue(d.is_archived)


class WidgetAPITest(BaseTestCase):
    def create_widget(self, dashboard, visualization, width=1):
        data = {
            'visualization_id': visualization.id,
            'dashboard_id': dashboard.id,
            'options': {},
            'width': width
        }

        rv = self.make_request('post', '/api/widgets', data=data)

        return rv

    def test_create_widget(self):
        dashboard = self.factory.create_dashboard()
        vis = self.factory.create_visualization()

        rv = self.create_widget(dashboard, vis)
        self.assertEquals(rv.status_code, 200)

        dashboard = models.Dashboard.get(models.Dashboard.id == dashboard.id)
        self.assertEquals(unicode(rv.json['layout']), dashboard.layout)

        self.assertEquals(dashboard.widgets, 1)
        self.assertEquals(rv.json['layout'], [[rv.json['widget']['id']]])
        self.assertEquals(rv.json['new_row'], True)

        rv2 = self.create_widget(dashboard, vis)
        self.assertEquals(dashboard.widgets, 2)
        self.assertEquals(rv2.json['layout'],
                          [[rv.json['widget']['id'], rv2.json['widget']['id']]])
        self.assertEquals(rv2.json['new_row'], False)

        rv3 = self.create_widget(dashboard, vis)
        self.assertEquals(rv3.json['new_row'], True)
        rv4 = self.create_widget(dashboard, vis, width=2)
        self.assertEquals(rv4.json['layout'],
                          [[rv.json['widget']['id'], rv2.json['widget']['id']],
                           [rv3.json['widget']['id']],
                           [rv4.json['widget']['id']]])
        self.assertEquals(rv4.json['new_row'], True)

    def test_create_text_widget(self):
        dashboard = self.factory.create_dashboard()

        data = {
            'visualization_id': None,
            'text': 'Sample text.',
            'dashboard_id': dashboard.id,
            'options': {},
            'width': 2
        }

        rv = self.make_request('post', '/api/widgets', data=data)

        self.assertEquals(rv.status_code, 200)
        self.assertEquals(rv.json['widget']['text'], 'Sample text.')

    def test_delete_widget(self):
        widget = self.factory.create_widget()

        rv = self.make_request('delete', '/api/widgets/{0}'.format(widget.id))

        self.assertEquals(rv.status_code, 200)
        dashboard = models.Dashboard.get_by_slug_and_org(widget.dashboard.slug, widget.dashboard.org)
        self.assertEquals(dashboard.widgets.count(), 0)
        self.assertEquals(dashboard.layout, '[]')

        # TODO: test how it updates the layout


class VisualizationResourceTest(BaseTestCase):
    def test_create_visualization(self):
        query = self.factory.create_query()
        data = {
            'query_id': query.id,
            'name': 'Chart',
            'description':'',
            'options': {},
            'type': 'CHART'
        }

        rv = self.make_request('post', '/api/visualizations', data=data)

        self.assertEquals(rv.status_code, 200)
        data.pop('query_id')
        self.assertDictContainsSubset(data, rv.json)

    def test_delete_visualization(self):
        visualization = self.factory.create_visualization()

        rv = self.make_request('delete', '/api/visualizations/{}'.format(visualization.id))

        self.assertEquals(rv.status_code, 200)
        # =1 because each query has a default table visualization.
        self.assertEquals(models.Visualization.select().count(), 1)

    def test_update_visualization(self):
        visualization = self.factory.create_visualization()

        rv = self.make_request('post', '/api/visualizations/{0}'.format(visualization.id), data={'name': 'After Update'})

        self.assertEquals(rv.status_code, 200)
        self.assertEquals(rv.json['name'], 'After Update')

    def test_only_owner_or_admin_can_create_visualization(self):
        query = self.factory.create_query()
        data = {
            'query_id': query.id,
            'name': 'Chart',
            'description':'',
            'options': {},
            'type': 'CHART'
        }

        other_user = self.factory.create_user()
        admin = self.factory.create_admin()
        admin_from_diff_org = self.factory.create_admin(org=self.factory.create_org())

        rv = self.make_request('post', '/api/visualizations', data=data, user=admin)
        self.assertEquals(rv.status_code, 200)

        rv = self.make_request('post', '/api/visualizations', data=data, user=other_user)
        self.assertEquals(rv.status_code, 403)

        rv = self.make_request('post', '/api/visualizations', data=data, user=admin_from_diff_org)
        self.assertEquals(rv.status_code, 404)

    def test_only_owner_or_admin_can_edit_visualization(self):
        vis = self.factory.create_visualization()
        path = '/api/visualizations/{}'.format(vis.id)
        data={'name': 'After Update'}

        other_user = self.factory.create_user()
        admin = self.factory.create_admin()
        admin_from_diff_org = self.factory.create_admin(org=self.factory.create_org())

        rv = self.make_request('post', path, user=admin, data=data)
        self.assertEquals(rv.status_code, 200)

        rv = self.make_request('post', path, user=other_user, data=data)
        self.assertEquals(rv.status_code, 403)

        rv = self.make_request('post', path, user=admin_from_diff_org, data=data)
        self.assertEquals(rv.status_code, 404)

    def test_only_owner_or_admin_can_delete_visualization(self):
        vis = self.factory.create_visualization()
        path = '/api/visualizations/{}'.format(vis.id)

        other_user = self.factory.create_user()
        admin = self.factory.create_admin()
        admin_from_diff_org = self.factory.create_admin(org=self.factory.create_org())

        rv = self.make_request('delete', path, user=admin)
        self.assertEquals(rv.status_code, 200)

        vis = self.factory.create_visualization()
        path = '/api/visualizations/{}'.format(vis.id)

        rv = self.make_request('delete', path, user=other_user)
        self.assertEquals(rv.status_code, 403)

        vis = self.factory.create_visualization()
        path = '/api/visualizations/{}'.format(vis.id)

        rv = self.make_request('delete', path, user=admin_from_diff_org)
        self.assertEquals(rv.status_code, 404)


class JobAPITest(BaseTestCase, AuthenticationTestMixin):
    def setUp(self):
        self.paths = []
        super(JobAPITest, self).setUp()


class TestLogin(BaseTestCase):
    def setUp(self):
        settings.PASSWORD_LOGIN_ENABLED = True
        super(TestLogin, self).setUp()

    @classmethod
    def setUpClass(cls):
        settings.ORG_RESOLVING = "single_org"

    @classmethod
    def tearDownClass(cls):
        settings.ORG_RESOLVING = "multi_org"

    def test_redirects_to_google_login_if_password_disabled(self):
        with app.test_client() as c, patch.object(settings, 'PASSWORD_LOGIN_ENABLED', False):
            rv = c.get('/default/login')
            self.assertEquals(rv.status_code, 302)
            self.assertTrue(rv.location.endswith(url_for('google_oauth.authorize', next='/default/')))

    def test_get_login_form(self):
        with app.test_client() as c:
            rv = c.get('/default/login')
            self.assertEquals(rv.status_code, 200)

    def test_submit_non_existing_user(self):
        with app.test_client() as c, patch('redash.handlers.authentication.login_user') as login_user_mock:
            rv = c.post('/default/login', data={'email': 'arik', 'password': 'password'})
            self.assertEquals(rv.status_code, 200)
            self.assertFalse(login_user_mock.called)

    def test_submit_correct_user_and_password(self):
        user = self.factory.user
        user.hash_password('password')
        user.save()

        with app.test_client() as c, patch('redash.handlers.authentication.login_user') as login_user_mock:
            rv = c.post('/default/login', data={'email': user.email, 'password': 'password'})
            self.assertEquals(rv.status_code, 302)
            login_user_mock.assert_called_with(user, remember=False)

    def test_submit_correct_user_and_password_and_remember_me(self):
        user = self.factory.user
        user.hash_password('password')
        user.save()

        with app.test_client() as c, patch('redash.handlers.authentication.login_user') as login_user_mock:
            rv = c.post('/default/login', data={'email': user.email, 'password': 'password', 'remember': True})
            self.assertEquals(rv.status_code, 302)
            login_user_mock.assert_called_with(user, remember=True)

    def test_submit_correct_user_and_password_with_next(self):
        user = self.factory.user
        user.hash_password('password')
        user.save()

        with app.test_client() as c, patch('redash.handlers.authentication.login_user') as login_user_mock:
            rv = c.post('/default/login?next=/test',
                        data={'email': user.email, 'password': 'password'})
            self.assertEquals(rv.status_code, 302)
            self.assertEquals(rv.location, 'http://localhost/test')
            login_user_mock.assert_called_with(user, remember=False)

    def test_submit_incorrect_user(self):
        with app.test_client() as c, patch('redash.handlers.authentication.login_user') as login_user_mock:
            rv = c.post('/default/login', data={'email': 'non-existing', 'password': 'password'})
            self.assertEquals(rv.status_code, 200)
            self.assertFalse(login_user_mock.called)

    def test_submit_incorrect_password(self):
        user = self.factory.user
        user.hash_password('password')
        user.save()

        with app.test_client() as c, patch('redash.handlers.authentication.login_user') as login_user_mock:
            rv = c.post('/default/login', data={'email': user.email, 'password': 'badbadpassword'})
            self.assertEquals(rv.status_code, 200)
            self.assertFalse(login_user_mock.called)

    def test_submit_incorrect_password(self):
        user = self.factory.user

        with app.test_client() as c, patch('redash.handlers.authentication.login_user') as login_user_mock:
            rv = c.post('/default/login', data={'email': user.email, 'password': ''})
            self.assertEquals(rv.status_code, 200)
            self.assertFalse(login_user_mock.called)

    def test_user_already_loggedin(self):
        with app.test_client() as c, authenticated_user(c), patch('redash.handlers.authentication.login_user') as login_user_mock:
            rv = c.get('/default/login')
            self.assertEquals(rv.status_code, 302)
            self.assertFalse(login_user_mock.called)

    # TODO: brute force protection?


class TestLogout(BaseTestCase):
    def test_logout_when_not_loggedin(self):
        with app.test_client() as c:
            rv = c.get('/default/logout')
            self.assertEquals(rv.status_code, 302)
            self.assertFalse(current_user.is_authenticated)

    def test_logout_when_loggedin(self):
        with app.test_client() as c, authenticated_user(c, user=self.factory.user):
            rv = c.get('/default/')
            self.assertTrue(current_user.is_authenticated)
            rv = c.get('/default/logout')
            self.assertEquals(rv.status_code, 302)
            self.assertFalse(current_user.is_authenticated)
