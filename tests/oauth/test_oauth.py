"""
This module tests oauth
"""
from unittest.mock import MagicMock, patch

from superset import app

from superset_patchup.oauth import AuthOAuthView, CustomSecurityManager


class TestOauth:
    """
    Class to test the oauth module
    """

    def test_get_oauth_redirect_url_when_not_set(self):
        """
        Test that when custom_redirect_url key is not set in the provider
        None is returned
        """
        appbuilder = MagicMock()
        CustomSecurityManager.oauth_providers = [{"name": "onadata"}]
        csm = CustomSecurityManager(appbuilder=appbuilder)
        redirect_url = csm.get_oauth_redirect_url(provider="onadata")
        assert redirect_url is None

    def test_get_oauth_redirect_url_when_set(self):
        """
        Test that when custom_redirect_url key is set in the provider
        it returns the right value
        """
        appbuilder = MagicMock()
        CustomSecurityManager.oauth_providers = [{
            "name":
            "onadata",
            "custom_redirect_url":
            "http://google.com"
        }]
        csm = CustomSecurityManager(appbuilder=appbuilder)
        redirect_url = csm.get_oauth_redirect_url(provider="onadata")
        assert redirect_url == "http://google.com"

    def test_oauth_user_info_onadata_provider(self):
        """
        Test that we get the right user information
        with the onadata provider
        """
        # Sample data returned from endpoints
        user_endpoint = {"username": "testauth", "name": "test"}
        profiles_endpoint = {
            "id": 58863,
            "is_org": False,
            "first_name": "test",
            "name": "test auth",
            "last_name": "auth",
            "email": "testauth@ona.io",
        }

        # Expected result
        result_info = {
            "name": "test auth",
            "email": "testauth@ona.io",
            "id": 58863,
            "username": "testauth",
            "first_name": "test",
            "last_name": "auth",
        }

        appbuilder = MagicMock()
        user_mock = MagicMock()
        user_mock.data = user_endpoint
        profile_mock = MagicMock()
        profile_mock.data = profiles_endpoint
        appbuilder.sm.oauth_remotes["onadata"].get = MagicMock(
            side_effect=[user_mock, profile_mock])
        csm = CustomSecurityManager(appbuilder=appbuilder)
        user_info = csm.oauth_user_info(provider="onadata")
        assert user_info == result_info

    def test_oauth_user_info_openlmis_provider(self):
        """
        Test that we get the right user information
        with the openlmis provider
        """
        # Data returned from userContactDetails endpoint
        contacts_endpoint = {
            "emailDetails": {
                "email": "testauth@openlmis.org"
            }
        }

        # Data returned from users endpoint in openlmis
        users_endpoint = {
            "username": "testauth",
            "firstName": "test",
            "lastName": "auth",
            "active": True,
            "id": "a337ec45-31a0-4f2b-9b2e-a105c4b669bb",
        }

        # Result expected
        result_info = {
            "name": "testauth",
            "email": "testauth@openlmis.org",
            "id": "a337ec45-31a0-4f2b-9b2e-a105c4b669bb",
            "username": "testauth",
            "first_name": "test",
            "last_name": "auth",
        }

        appbuilder = MagicMock()
        reference_user = MagicMock()
        reference_user.data = {
            "referenceDataUserId": "a337ec45-31a0-4f2b-9b2e-a105c4b669bb"
        }

        user_data = MagicMock()
        user_data.data = users_endpoint

        user_email = MagicMock()
        user_email.data = contacts_endpoint

        appbuilder.sm.oauth_remotes["openlmis"].get = MagicMock(
            side_effect=[reference_user, user_data, user_email])
        csm = CustomSecurityManager(appbuilder=appbuilder)
        csm.oauth_tokengetter = MagicMock(
            return_value=["a337ec45-31a0-4f2b-9b2e-a105c4b669bb"])
        user_info = csm.oauth_user_info(provider="openlmis")
        assert user_info == result_info

    def test_oauth_user_info_no_provider(self):
        """
        Test that when no provider is provided
        None is returned
        """
        appbuilder = MagicMock()
        csm = CustomSecurityManager(appbuilder=appbuilder)
        user_info = csm.oauth_user_info(provider=None)
        assert user_info is None

    @patch("superset_patchup.oauth.SupersetSecurityManager.clean_perms")
    @patch("superset_patchup.oauth.SupersetSecurityManager.get_session")
    @patch(
        "superset_patchup.oauth.SupersetSecurityManager.create_missing_perms")
    @patch("superset_patchup.oauth.CustomSecurityManager.is_custom_pvm")
    @patch("superset_patchup.oauth.CustomSecurityManager.set_custom_role")
    @patch(
        "superset_patchup.oauth.SupersetSecurityManager.sync_role_definitions")
    def test_custom_roles(
            self,
            mock_sync_role_definitions,
            mock_set_custom_role,
            mock_is_custom_pvm,
            mock_create_missing_perms, # pylint: disable=unused-argument
            mock_get_session, # pylint: disable=unused-argument
            mock_clean_perms,
    ):
        """
        Test that when add custom roles is set to true, the roles specified
        in the configs are created
        """
        # set test configs
        app.config['ADD_CUSTOM_ROLES'] = True
        app.config['CUSTOM_ROLES'] = {'Test_role': {'all_datasource_access'}}

        appbuilder = MagicMock()
        csm = CustomSecurityManager(appbuilder=appbuilder)
        csm.sync_role_definitions()
        assert mock_sync_role_definitions.call_count == 1
        assert mock_set_custom_role.call_count == 1

        mock_args = mock_set_custom_role.call_args_list[0]
        assert mock_args[0][0] == 'Test_role'
        assert mock_args[0][1] == mock_is_custom_pvm
        assert mock_args[0][2] == {'all_datasource_access'}
        assert mock_clean_perms.call_count == 1

    @patch("superset_patchup.oauth.redirect")
    @patch("superset_patchup.oauth.is_safe_url")
    @patch("superset_patchup.oauth.request.args.get")
    @patch("superset_patchup.oauth.login_user")
    @patch("superset_patchup.oauth.request")
    def test_oauth_authorized(
            self,
            mock_request,
            mock_login,
            mock_request_redirect,
            mock_safe_url,
            mock_redirect,
    ):
        """
        This test checks that
        1. The access token is used when passed in the request header
        2. Redirect is called with the url passed in the request args
        """
        # Sample authorized response
        mock_authorized_response = {
            "access_token": "cZpwCzYjpzuSqzekM",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "Sui6j4nQtbmU9P",
            "scope": "read write",
        }

        # Sample user info from onadata
        mock_user_info = {
            "name": "test auth",
            "email": "testauth@ona.io",
            "id": 58863,
            "username": "testauth",
            "first_name": "test",
            "last_name": "auth",
            "is_active": True,
        }

        oauth_view = AuthOAuthView()
        oauth_view.appbuilder = MagicMock()
        oauth_view.appbuilder.sm.oauth_remotes[
            "onadata"].authorized_response = MagicMock(
                return_value=mock_authorized_response)
        mock_request.headers = {"Custom-Api-Token": "cZpwCzYjpzuSqzekM"}
        auth_session_mock = MagicMock()
        oauth_view.appbuilder.sm.set_oauth_session = auth_session_mock
        oauth_view.appbuilder.sm.oauth_user_info = MagicMock(
            return_value=mock_user_info)
        oauth_view.appbuilder.sm.oauth_whitelists = MagicMock()
        oauth_view.appbuilder.sm.auth_user_oauth = MagicMock(
            return_value=mock_user_info)
        oauth_view.appbuilder.sm.get_oauth_redirect_url = MagicMock()
        mock_request_redirect.return_value = "http://example.com"
        mock_safe_url.return_value = True
        oauth_view.oauth_authorized(provider="onadata")
        auth_session_mock.assert_called_with("onadata",
                                  {"access_token": "cZpwCzYjpzuSqzekM"})
        mock_login.assert_call_count = 1
            {"access_token": "cZpwCzYjpzuSqzekM"})
        assert mock_login.call_count == 1
        mock_redirect.assert_called_once_with("http://example.com")
