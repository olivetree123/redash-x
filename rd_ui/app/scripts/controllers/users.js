(function () {
  var GroupsCtrl = function ($scope, $location, $modal, growl, Events, Group) {
    Events.record(currentUser, "view", "page", "groups");
    $scope.$parent.pageTitle = "Groups";

    $scope.gridConfig = {
      isPaginationEnabled: true,
      itemsByPage: 20,
      maxSize: 8,
    };

    $scope.gridColumns = [
      {
        "label": "Name",
        "map": "name",
        "cellTemplate": '<a href="groups/{{dataRow.id}}">{{dataRow.name}}</a>'
      }
    ];

    $scope.groups = [];
    Group.query(function(groups) {
      $scope.groups = groups;
    });

    $scope.newGroup = function() {
      $modal.open({
        templateUrl: '/views/groups/edit_group_form.html',
        size: 'sm',
        resolve: {
          group: function() { return new Group({}); }
        },
        controller: ['$scope', '$modalInstance', 'group', function($scope, $modalInstance, group) {
          $scope.group = group;
          var newGroup = group.id === undefined;

          if (newGroup) {
            $scope.saveButtonText = "Create";
            $scope.title = "Create a New Group";
          } else {
            $scope.saveButtonText = "Save";
            $scope.title = "Edit Group";
          }

          $scope.ok = function() {
            $scope.group.$save(function(group) {
              if (newGroup) {
                $location.path('/groups/' + group.id).replace();
                $modalInstance.close();
              } else {
                $modalInstance.close();
              }
            });
          }

          $scope.cancel = function() {
            $modalInstance.close();
          }
        }]
      });
    }
  };

  var usersNav = function($location) {
    return {
      restrict: 'E',
      replace: true,
      template:
        '<ul class="nav nav-tabs">' +
          '<li role="presentation" ng-class="{\'active\': usersPage }"><a href="users">Users</a></li>' +
          '<li role="presentation" ng-class="{\'active\': groupsPage }" ng-if="showGroupsLink"><a href="groups">Groups</a></li>' +
        '</ul>',
      controller: ['$scope', function ($scope) {
        $scope.usersPage = _.string.startsWith($location.path(), '/users');
        $scope.groupsPage = _.string.startsWith($location.path(), '/groups');
        $scope.showGroupsLink = currentUser.hasPermission('list_users');
      }]
    }
  }

  var groupName = function ($location, growl) {
    return {
      restrict: 'E',
      scope: {
        'group': '='
      },
      transclude: true,
      template:
        '<h2>'+
          '<edit-in-place editable="canEdit()" done="saveName" ignore-blanks=\'true\' value="group.name"></edit-in-place>&nbsp;' +
          '<button class="btn btn-xs btn-danger" ng-if="canEdit()" ng-click="deleteGroup()">Delete this group</button>' +
        '</h2>',
      replace: true,
      controller: ['$scope', function ($scope) {
        $scope.canEdit = function() {
          return currentUser.isAdmin && $scope.group.type != 'builtin';
        };

        $scope.saveName = function() {
          $scope.group.$save();
        };

        $scope.deleteGroup = function() {
          if (confirm("Are you sure you want to delete this group?")) {
            $scope.group.$delete(function() {
              $location.path('/groups').replace();
              growl.addSuccessMessage("Group deleted successfully.");
            })
          }
        }
      }]
    }
  };

  var GroupDataSourcesCtrl = function($scope, $routeParams, $http, $location, growl, Events, Group, DataSource) {
    Events.record(currentUser, "view", "group_data_sources", $scope.groupId);
    $scope.group = Group.get({id: $routeParams.groupId});
    $scope.dataSources = Group.dataSources({id: $routeParams.groupId});
    $scope.newDataSource = {};

    $scope.findDataSource = function(search) {
      if ($scope.foundDataSources === undefined) {
        DataSource.query(function(dataSources) {
          var existingIds = _.map($scope.dataSources, function(m) { return m.id; });
          $scope.foundDataSources = _.filter(dataSources, function(ds) { return !_.contains(existingIds, ds.id); });
        });
      }
    };

    $scope.addDataSource = function(dataSource) {
      // Clear selection, to clear up the input control.
      $scope.newDataSource.selected = undefined;

      $http.post('api/groups/' + $routeParams.groupId + '/data_sources', {'data_source_id': dataSource.id}).success(function(user) {
        dataSource.view_only = false;
        $scope.dataSources.unshift(dataSource);

        if ($scope.foundDataSources) {
          $scope.foundDataSources = _.filter($scope.foundDataSources, function(ds) { return ds != dataSource; });
        }
      });
    };

    $scope.changePermission = function(dataSource, viewOnly) {
      $http.post('api/groups/' + $routeParams.groupId + '/data_sources/' + dataSource.id, {view_only: viewOnly}).success(function() {
        dataSource.view_only = viewOnly;
      });
    };

    $scope.removeDataSource = function(dataSource) {
      $http.delete('api/groups/' + $routeParams.groupId + '/data_sources/' + dataSource.id).success(function() {
        $scope.dataSources = _.filter($scope.dataSources, function(ds) { return dataSource != ds; });
      });
    };
  }

  var GroupCtrl = function($scope, $routeParams, $http, $location, growl, Events, Group, User) {
    Events.record(currentUser, "view", "group", $scope.groupId);
    $scope.group = Group.get({id: $routeParams.groupId});
    $scope.members = Group.members({id: $routeParams.groupId});
    $scope.newMember = {};

    $scope.findUser = function(search) {
      if (search == "") {
        return;
      }

      if ($scope.foundUsers === undefined) {
        User.query(function(users) {
          var existingIds = _.map($scope.members, function(m) { return m.id; });
          _.each(users, function(user) { user.alreadyMember = _.contains(existingIds, user.id); });
          $scope.foundUsers = users;
        });
      }
    };

    $scope.addMember = function(user) {
      // Clear selection, to clear up the input control.
      $scope.newMember.selected = undefined;

      $http.post('api/groups/' + $routeParams.groupId + '/members', {'user_id': user.id}).success(function() {
        $scope.members.unshift(user);
        user.alreadyMember = true;
      });
    };

    $scope.removeMember = function(member) {
      $http.delete('api/groups/' + $routeParams.groupId + '/members/' + member.id).success(function() {
        $scope.members = _.filter($scope.members, function(m) {  return m != member });

        if ($scope.foundUsers) {
          _.each($scope.foundUsers, function(user) { if (user.id == member.id) { user.alreadyMember = false }; });
        }
      });
    };
  }

  var UsersCtrl = function ($scope, $location, growl, Events, User) {
    Events.record(currentUser, "view", "page", "users");
    $scope.$parent.pageTitle = "Users";

    $scope.gridConfig = {
      isPaginationEnabled: true,
      itemsByPage: 20,
      maxSize: 8,
    };

    $scope.gridColumns = [
      {
        "label": "Name",
        "map": "name",
        "cellTemplate": '<img src="{{dataRow.gravatar_url}}" height="40px"/> <a href="users/{{dataRow.id}}">{{dataRow.name}}</a>'
      },
      {
        'label': 'Joined',
        'cellTemplate': '<span am-time-ago="dataRow.created_at"></span>'
      }
    ];

    $scope.users = [];
    User.query(function(users) {
      $scope.users = users;
    });
  };

  var UserCtrl = function ($scope, $routeParams, $http, $location, growl, Events, User) {
    $scope.$parent.pageTitle = "Users";

    $scope.userId = $routeParams.userId;

    if ($scope.userId === 'me') {
      $scope.userId = currentUser.id;
    }
    Events.record(currentUser, "view", "user", $scope.userId);
    $scope.canEdit = currentUser.hasPermission("admin") || currentUser.id === parseInt($scope.userId);
    $scope.showSettings =  false;
    $scope.showPasswordSettings = false;

    $scope.selectTab = function(tab) {
      _.each($scope.tabs, function(v, k) {
        $scope.tabs[k] = (k === tab);
      });
    };

    $scope.setTab = function(tab) {
      $location.hash(tab);
    }

    $scope.tabs = {
      profile: false,
      apiKey: false,
      settings: false,
      password: false
    };

    $scope.selectTab($location.hash() || 'profile');

    $scope.user = User.get({id: $scope.userId}, function(user) {
      if (user.auth_type == 'password') {
        $scope.showSettings = $scope.canEdit;
        $scope.showPasswordSettings = $scope.canEdit;
      }
    });

    $scope.password = {
      current: '',
      new: '',
      newRepeat: ''
    };

    $scope.savePassword = function(form) {
      $scope.$broadcast('show-errors-check-validity');

      if (!form.$valid) {
        return;
      }

      var data = {
        id: $scope.user.id,
        password: $scope.password.new,
        old_password: $scope.password.current
      };

      User.save(data, function() {
        growl.addSuccessMessage("Password Saved.")
        $scope.password = {
          current: '',
          new: '',
          newRepeat: ''
        };
      }, function(error) {
        var message = error.data.message || "Failed saving password.";
        growl.addErrorMessage(message);
      });
    };

    $scope.updateUser = function(form) {
      $scope.$broadcast('show-errors-check-validity');

      if (!form.$valid) {
        return;
      }

      var data = {
        id: $scope.user.id,
        name: $scope.user.name,
        email: $scope.user.email
      };

      User.save(data, function(user) {
        growl.addSuccessMessage("Saved.")
        $scope.user = user;
      }, function(error) {
        var message = error.data.message || "Failed saving.";
        growl.addErrorMessage(message);
      });
    };
  };

  var NewUserCtrl = function ($scope, $location, growl, Events, User) {
    Events.record(currentUser, "view", "page", "users/new");

    $scope.user = new User({});
    $scope.saveUser = function() {
      $scope.$broadcast('show-errors-check-validity');

      if (!$scope.userForm.$valid) {
        return;
      }

      $scope.user.$save(function(user) {
        growl.addSuccessMessage("Saved.")
        $location.path('/users/' + user.id).replace();
      }, function(error) {
        var message = error.data.message || "Failed saving.";
        growl.addErrorMessage(message);
      });
    }
  };

  angular.module('redash.controllers')
    .controller('GroupsCtrl', ['$scope', '$location', '$modal', 'growl', 'Events', 'Group', GroupsCtrl])
    .directive('groupName', ['$location', 'growl', groupName])
    .directive('usersNav', ['$location', usersNav])
    .controller('GroupCtrl', ['$scope', '$routeParams', '$http', '$location', 'growl', 'Events', 'Group', 'User', GroupCtrl])
    .controller('GroupDataSourcesCtrl', ['$scope', '$routeParams', '$http', '$location', 'growl', 'Events', 'Group', 'DataSource', GroupDataSourcesCtrl])
    .controller('UsersCtrl', ['$scope', '$location', 'growl', 'Events', 'User', UsersCtrl])
    .controller('UserCtrl', ['$scope', '$routeParams', '$http', '$location', 'growl', 'Events', 'User', UserCtrl])
    .controller('NewUserCtrl', ['$scope', '$location', 'growl', 'Events', 'User', NewUserCtrl])
})();
