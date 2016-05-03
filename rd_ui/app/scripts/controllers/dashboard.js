(function() {
  var DashboardCtrl = function($scope, Events, Widget, $routeParams, $location, $http, $timeout, $q, Dashboard) {
    $scope.refreshEnabled = false;
    $scope.isFullscreen = false;
    $scope.refreshRate = 60;

    var renderDashboard = function (dashboard) {
      $scope.$parent.pageTitle = dashboard.name;

      var promises = [];

      _.each($scope.dashboard.widgets, function (row) {
        return _.each(row, function (widget) {
          if (widget.visualization) {
            var queryResult = widget.getQuery().getQueryResult();
            if (angular.isDefined(queryResult))
              promises.push(queryResult.toPromise());
          }
        });
      });

      $q.all(promises).then(function(queryResults) {
        var filters = {};
        _.each(queryResults, function(queryResult) {
          var queryFilters = queryResult.getFilters();
          _.each(queryFilters, function (queryFilter) {
            var hasQueryStringValue = _.has($location.search(), queryFilter.name);

            if (!(hasQueryStringValue || dashboard.dashboard_filters_enabled)) {
              // If dashboard filters not enabled, or no query string value given, skip filters linking.
              return;
            }

            if (!_.has(filters, queryFilter.name)) {
              var filter = _.extend({}, queryFilter);
              filters[filter.name] = filter;
              filters[filter.name].originFilters = [];
              if (hasQueryStringValue) {
                filter.current = $location.search()[filter.name];
              }

              $scope.$watch(function () { return filter.current }, function (value) {
                _.each(filter.originFilters, function (originFilter) {
                  originFilter.current = value;
                });
              });
            }

            // TODO: merge values.
            filters[queryFilter.name].originFilters.push(queryFilter);
          });
        });

        $scope.filters = _.values(filters);
      });
    }

    var loadDashboard = _.throttle(function () {
      $scope.dashboard = Dashboard.get({slug: $routeParams.dashboardSlug}, function (dashboard) {
          Events.record(currentUser, "view", "dashboard", dashboard.id);
          renderDashboard(dashboard);
        }, function () {
          // error...
          // try again. we wrap loadDashboard with throttle so it doesn't happen too often.\
          // we might want to consider exponential backoff and also move this as a general solution in $http/$resource for
          // all AJAX calls.
          loadDashboard();
        }
      );
    }, 1000);

    loadDashboard();

    var autoRefresh = function() {
      if ($scope.refreshEnabled) {
        $timeout(function() {
          Dashboard.get({
            slug: $routeParams.dashboardSlug
          }, function(dashboard) {
            var newWidgets = _.groupBy(_.flatten(dashboard.widgets), 'id');

            _.each($scope.dashboard.widgets, function(row) {
              _.each(row, function(widget, i) {
                var newWidget = newWidgets[widget.id];
                if (newWidget && newWidget[0].visualization.query.latest_query_data_id != widget.visualization.query.latest_query_data_id) {
                  row[i] = new Widget(newWidget[0]);
                }
              });
            });

            autoRefresh();
          });

        }, $scope.refreshRate);
      }
    };

    $scope.archiveDashboard = function () {
      if (confirm('Are you sure you want to archive the "' + $scope.dashboard.name + '" dashboard?')) {
        Events.record(currentUser, "archive", "dashboard", $scope.dashboard.id);
        $scope.dashboard.$delete(function () {
          $scope.$parent.reloadDashboards();
        });
      }
    }

    $scope.toggleFullscreen = function() {
      $scope.isFullscreen = !$scope.isFullscreen;
    };

    $scope.triggerRefresh = function() {
      $scope.refreshEnabled = !$scope.refreshEnabled;

      Events.record(currentUser, "autorefresh", "dashboard", dashboard.id, {'enable': $scope.refreshEnabled});

      if ($scope.refreshEnabled) {
        var refreshRate = _.min(_.map(_.flatten($scope.dashboard.widgets), function(widget) {
          var schedule = widget.visualization.query.schedule;
          if (schedule === null || schedule.match(/\d\d:\d\d/) !== null) {
            return 60;
          }
          return widget.visualization.query.schedule;
        }));

        $scope.refreshRate = _.max([120, refreshRate * 2]) * 1000;

        autoRefresh();
      }
    };
  };

  var WidgetCtrl = function($scope, $location, Events, Query) {
    $scope.deleteWidget = function() {
      if (!confirm('Are you sure you want to remove "' + $scope.widget.getName() + '" from the dashboard?')) {
        return;
      }

      Events.record(currentUser, "delete", "widget", $scope.widget.id);

      $scope.widget.$delete(function(response) {
        $scope.dashboard.widgets = _.map($scope.dashboard.widgets, function(row) {
          return _.filter(row, function(widget) {
            return widget.id != undefined;
          })
        });

        $scope.dashboard.widgets = _.filter($scope.dashboard.widgets, function(row) { return row.length > 0 });

        $scope.dashboard.layout = response.layout;
      });
    };

    Events.record(currentUser, "view", "widget", $scope.widget.id);

    if ($scope.widget.visualization) {
      Events.record(currentUser, "view", "query", $scope.widget.visualization.query.id);
      Events.record(currentUser, "view", "visualization", $scope.widget.visualization.id);

      $scope.query = $scope.widget.getQuery();
      var parameters = Query.collectParamsFromQueryString($location, $scope.query);
      var maxAge = $location.search()['maxAge'];
      $scope.queryResult = $scope.query.getQueryResult(maxAge, parameters);

      $scope.type = 'visualization';
    } else if ($scope.widget.restricted) {
      $scope.type = 'restricted';
    } else {
      $scope.type = 'textbox';
    }
  };

  angular.module('redash.controllers')
    .controller('DashboardCtrl', ['$scope', 'Events', 'Widget', '$routeParams', '$location', '$http', '$timeout', '$q', 'Dashboard', DashboardCtrl])
    .controller('WidgetCtrl', ['$scope', '$location', 'Events', 'Query', WidgetCtrl])

})();
