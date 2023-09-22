import logger
import boto3
from abstract_classes.identity_provider_abstract_class import IdentityProviderAbstractClass

from authzero.auth0_utils import *

# TODO: removed import time when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
import time

ssm = boto3.client('ssm')

def ssm_get_value(key):
    return ssm.get_parameter(Name=key, WithDecryption=True)['Parameter']['Value']

def ssm_set_value(key, value):
    ssm.put_parameter(Name=key, Value=value, Type="String", Overwrite=True)

class Auth0IdentityProviderManagement (IdentityProviderAbstractClass):

    """
    Creates idp object for a given tenant during onboarding

    Parameters:
    - event: {
        'tenantName': '',
        'tenantEmail': '',
        'tenantTier': 'Basic',
        'tenantPhone': null,
        'tenantAddress': null,
        'dedicatedTenancy': 'true|false',
        'tenantId': 'aff89d5922a211eebc6e8bce2639e939',
        'apiKey': '',
        'pooledIdpDetails': {
            'idp': {
                'name': '',
                'attr1': 'value',
                'attr2': 'value'                    
            }
        },
        'callbackURL': 'https://d2gzytd4vp39pr.cloudfront.net/'
    }

    Returns:
    - The created (or pooled) identity provider details. 
    {
        'idp': {
            'name': '',
            'attr1': 'value',
            'attr2': 'value'
        }
    }
    """
    def create_tenant(self, event):

        logger.info (event)

        # Step 1: Get values from event and SSM
        logger.info("Step 1: Get values from event and SSM")
        tenantName = event['tenantName']
        tenantTier = event['tenantTier']
        tenant_id = event['tenantId']
        callback_url = event['callbackURL']

        auth0_domain = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_DOMAIN)
        auth0_client_id = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_CLIENT_ID)
        auth0_client_secret = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_CLIENT_SECRET)

        saas_app_client_id = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_SAAS_APP_CLIENT_ID)
        saas_app_database_id = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_SAAS_APP_DATABASE_ID)

        # Step 2: Get Access Token for Management API
        logger.info("Step 2: Get Access Token for Management API")
        auth0 = create_auth0(auth0_domain, auth0_client_id, auth0_client_secret)
        
        # Step 3: Create Auth0 Organization
        logger.info("Step 3: Create Auth0 Organization")
        organization = get_or_create_organization(auth0, tenantName, tenantTier, tenant_id, saas_app_database_id)
        organization_id = organization["id"]

        # Step 4: Update SaaS Application with new redirect URL?
        if (event['dedicatedTenancy'] == 'true'):
            # TODO: Update SaaS Application with new redirect URL?
            # callback URL will be different and must be added to Auth0 SaaS App
            pass
        
        # Step 5: Return Value
        logger.info("Step 5: Return Value")
        return {
            "idp": {
                "name": "Auth0",
                "domain": auth0_domain,
                "clientId": saas_app_client_id,
                "orgId": organization_id
            }
        }
        
    """
    Create the tenant application pooled identity provider.

    Parameters:
    - event: {
        'callbackURL': 'https://d2gzytd4vp39pr.cloudfront.net/'
    }
    """
    def create_pooled_idp(self,event):
        
        logger.info (event)

        # Step 1: Get values from event and SSM
        logger.info("Step 1: Get values from event and SSM")
        saas_app_callback_url = event['callbackURL']

        auth0_domain = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_DOMAIN)
        auth0_client_id = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_CLIENT_ID)
        auth0_client_secret = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_CLIENT_SECRET)
  
        logger.info ("Auth0 Domain:" + auth0_domain)
        logger.info ("Auth0 ClientID:" + auth0_client_id)

        # Step 2: Get Access Token for Management API
        logger.info("Step 2: Get Access Token for Management API")
        auth0 = create_auth0(auth0_domain, auth0_client_id, auth0_client_secret)

        # Step 3: Configure Auth0 Tenant Settings (run once during deployment)
        logger.info("Step 3: Configure Auth0 Tenant Settings (run once during deployment)")
        configure_auth0_tenant(auth0, saas_app_callback_url)

        # TODO: removed sleep when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
        time.sleep(1)

        # Step 4: Create SaaS Application
        logger.info("Step 4: Create SaaS Application")
        saas_app = create_or_update_auth0_client(auth0, AUTH0_SAAS_APP_NAME, saas_app_callback_url, True, "#/dashboard")
        saas_app_client_id = saas_app["client_id"]
        saas_app_client_secret = saas_app["client_secret"]
        ssm_set_value(SSM_SERVERLESS_SAAS_AUTH0_SAAS_APP_CLIENT_ID, saas_app_client_id)

        # TODO: removed sleep when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
        time.sleep(1)

        # Step 5: Create DB for SaaS Application
        logger.info("Step 5: Create DB for SaaS Application")
        saas_app_database_id = get_or_create_db_connection(auth0, AUTH0_SAAS_APP_DATABASE_NAME, saas_app_client_id, auth0_client_id)
        ssm_set_value(SSM_SERVERLESS_SAAS_AUTH0_SAAS_APP_DATABASE_ID, saas_app_database_id)

        # TODO: removed sleep when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
        time.sleep(1)

        # Step 6: Create TenantAdmin Role
        logger.info("Step 6: Create SystemAdmin Role")
        tenant_admin_role = get_or_create_role(auth0, SERVERLESS_SAAS_ROLE_TENANT_ADMIN)
        tenant_admin_role_id = tenant_admin_role["id"]
        ssm_set_value(SSM_SERVERLESS_SAAS_AUTH0_TENANT_ADMIN_ROLE_ID, tenant_admin_role_id)

        # Step 7: Return value
        logger.info("Step 7: Return value")
        return {
            "idp": {
                "name": "Auth0",
                "domain": auth0_domain,
                "clientId": saas_app_client_id
            }
        }
    
    """
    Creates the admin identity provider.

    Parameters:
    - event: {
        'AdminCallbackURL': 'https://d2gzytd4vp39pr.cloudfront.net/'
        'AdminEmail': ''
        'SystemAdminRoleName': ''
    }
    """
    def create_operational_idp(self,event):

        logger.info (event)
        
        # Step 1: Get values from event and SSM
        logger.info("Step 1: Get values from event and SSM")
        admin_callback_url = event['AdminCallbackURL']
        admin_email = event['AdminEmail']

        auth0_domain = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_DOMAIN)
        auth0_client_id = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_CLIENT_ID)
        auth0_client_secret = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_CLIENT_SECRET)
  
        logger.info ("Auth0 Domain:" + auth0_domain)
        logger.info ("Auth0 ClientID:" + auth0_client_id)
        
        # Step 2: Get Access Token for Management API
        logger.info("Step 2: Get Access Token for Management API")
        auth0 = create_auth0(auth0_domain, auth0_client_id, auth0_client_secret)

        # Step 3: Configure Auth0 Tenant Settings (run once during deployment)
        logger.info("Step 3: Configure Auth0 Tenant Settings (run once during deployment)")
        configure_auth0_tenant(auth0, admin_callback_url)

        # TODO: removed sleep when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
        time.sleep(1)

        # Step 4:  Create Admin Application
        logger.info("Step 4:  Create Admin Application")
        admin_app = create_or_update_auth0_client(auth0, AUTH0_ADMIN_APP_NAME, admin_callback_url, False, "#/dashboard")
        admin_app_client_id = admin_app["client_id"]
        admin_app_client_secret = admin_app["client_secret"]
        ssm_set_value(SSM_SERVERLESS_SAAS_AUTH0_ADMIN_APP_CLIENT_ID, admin_app_client_id)

        # TODO: removed sleep when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
        time.sleep(1)

        # Step 5: Create DB for Admin Application and create admin user
        logger.info("Step 5: Create DB for Admin Application and create admin user")
        admin_database_id = get_or_create_db_connection(auth0, AUTH0_ADMIN_DATABASE_NAME, admin_app_client_id, auth0_client_id)
        logger.info("Step 5.1")
        admin_user = get_or_create_user_for_database_connection(auth0, admin_email, AUTH0_ADMIN_DATABASE_NAME, auth0_domain, admin_app_client_id)
        logger.info("Step 5.2:" + str(admin_user))
        admin_user_id = admin_user["user_id"]
        logger.info("Step 5.3:" + admin_user_id)
        ssm_set_value(SSM_SERVERLESS_SAAS_AUTH0_ADMIN_APP_DATABASE_ID, admin_database_id)

        # TODO: removed sleep when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
        time.sleep(1)

        # Step 6: Create SystemAdmin Role and assign to admin user
        logger.info("Step 6: Create SystemAdmin Role and assign to admin user")
        system_admin_role = get_or_create_role(auth0, SERVERLESS_SAAS_ROLE_SYSTEM_ADMIN)
        system_admin_role_id = system_admin_role["id"]
        add_user_to_role(auth0, system_admin_role_id, admin_user_id)
        ssm_set_value(SSM_SERVERLESS_SAAS_AUTH0_SYSTEM_ADMIN_ROLE_ID, system_admin_role_id)

        # TODO: removed sleep when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
        time.sleep(1)

        # Step 7: Create API with Audience
        logger.info("Step 7: Create API with Audience")
        api = get_or_create_api(auth0, AUTH0_SAAS_APP_API_NAME, AUTH0_SAAS_APP_API_AUDIENCE)
        api_id = api["id"]
        ssm_set_value(SSM_SERVERLESS_SAAS_AUTH0_API_ID, api_id)

        # TODO: removed sleep when the following fix is merged to the Auth0 Python SDK: https://github.com/auth0/auth0-python/issues/513
        time.sleep(1)

        # Step 8: Create Auth0 Action to enrich token
        logger.info("Step 8: Create Auth0 Action to enrich token")
        action = create_or_update_action(auth0, AUTH0_ACTION_NAME_ERICH_SAAS_TOKEN, auth0_action_enrich_saas_token)
        action_id = action["id"]
        ssm_set_value(SSM_SERVERLESS_SAAS_AUTH0_ACTION_ID, action_id)

        # Step 9: Return value
        logger.info("Step 9: Return value")
        return {
            "idp": {
                "name": "Auth0",
                "domain": auth0_domain,
                "clientId": admin_app_client_id
            }
        }