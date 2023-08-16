# =========================================================
# STATIC NAMES
# =========================================================
AUTH0_MANAGEMENT_APP_NAME = "SaaS Management M2M"

AUTH0_ADMIN_APP_NAME = "SaaS Admin"
AUTH0_ADMIN_DATABASE_NAME = "SaaS-Admin-Username-Password-Authentication"

AUTH0_SAAS_APP_NAME = "SaaS Application"
AUTH0_SAAS_APP_DATABASE_NAME = "SaaS-App-Username-Password-Authentication"

AUTH0_SAAS_APP_API_NAME = "SaaS Management API"
AUTH0_SAAS_APP_API_AUDIENCE = "api://saas-management-api"

AUTH0_ACTION_NAME_ERICH_SAAS_TOKEN = "Enrich SaaS Token"

SSM_SERVERLESS_SAAS_AUTH0_DOMAIN = "Serverless-SaaS-Auth0-Domain"
SSM_SERVERLESS_SAAS_AUTH0_CLIENT_ID = "Serverless-SaaS-Auth0-ClientId"
SSM_SERVERLESS_SAAS_AUTH0_CLIENT_SECRET = "Serverless-SaaS-Auth0-ClientSecret"
SSM_SERVERLESS_SAAS_AUTH0_ADMIN_APP_CLIENT_ID = "Serverless-SaaS-Auth0-AdminApp-ClientId"
SSM_SERVERLESS_SAAS_AUTH0_ADMIN_APP_DATABASE_ID = "Serverless-SaaS-Auth0-AdminApp-DatabaseId"
SSM_SERVERLESS_SAAS_AUTH0_SAAS_APP_CLIENT_ID = "Serverless-SaaS-Auth0-SaaSApp-ClientId"
SSM_SERVERLESS_SAAS_AUTH0_SAAS_APP_DATABASE_ID = "Serverless-SaaS-Auth0-SaaSApp-DatabaseId"
SSM_SERVERLESS_SAAS_AUTH0_SYSTEM_ADMIN_ROLE_ID = "Serverless-SaaS-Auth0-SystemAdmin-RoleId"
SSM_SERVERLESS_SAAS_AUTH0_TENANT_ADMIN_ROLE_ID = "Serverless-SaaS-Auth0-TenantAdmin-RoleId"
SSM_SERVERLESS_SAAS_AUTH0_ACTION_ID = "Serverless-SaaS-Auth0-ActionId"
SSM_SERVERLESS_SAAS_AUTH0_API_ID = "Serverless-SaaS-Auth0-ApiId"

SERVERLESS_SAAS_ROLE_SYSTEM_ADMIN = "SystemAdmin"
SERVERLESS_SAAS_ROLE_TENANT_ADMIN = "TenantAdmin"

# =========================================================
# Get Access Token for Auth0 Management API
# =========================================================
from auth0.authentication import GetToken
from auth0.management import Auth0
from auth0.rest import RestClientOptions

def create_auth0(auth0_domain, auth0_client_id, auth0_client_secret):
    # get token (valid for 24h)
    get_token = GetToken(auth0_domain, auth0_client_id, client_secret=auth0_client_secret)
    token = get_token.client_credentials('https://{}/api/v2/'.format(auth0_domain))
    mgmt_api_token = token['access_token']

    # create Auth0
    rest_client_option = RestClientOptions(retries=10) # set max retries to maximum of 10, as free trials have a lower number of rate limits and we do a lot of Auth0 Management API requests during setup
    return Auth0(auth0_domain, mgmt_api_token, rest_client_option)

# =========================================================
# Auth0 Tenant Configuration
# =========================================================

def configure_auth0_tenant(auth0, default_callback_url):
    auth0.tenants.update({

        # disable advanced setting to automatically enable new connections for new applications
        "flags":{
            "enable_client_connections":False
        },

        # Set default redirect URI must be set to invite members to an Organization
        "default_redirection_uri": default_callback_url,
    })
    auth0.prompts.update({
        "identifier_first":True
    })

# =========================================================
# Create Application
# =========================================================

# get id of existing admin application or 0
def get_auth0_client_by_name(auth0, client_name):
    for client in auth0.clients.all():
        if client["name"] == client_name:
            return client
    return 0

# create a new auth0 client
def create_auth0_client(auth0, client_name, callback_url, enable_organization, login_url_postfix = ""):
    client_config = {
            "name":client_name,
            "app_type":"spa",
            "initiate_login_uri": callback_url + login_url_postfix,
            "callbacks": [callback_url],
            "allowed_logout_urls": [callback_url],
            "web_origins": [callback_url],

            # must be set to none to allow access from a SPA
            "token_endpoint_auth_method": "none",

            # per default, Auth0 also enabled "Client Credentials", which must be disabled for the Organization feature
            # so we only set the grant types that are required
            "grant_types": [
                "authorization_code",
                "implicit",
                "refresh_token"
            ],

            # required to use Auth0 Organization with "Promt for Credentials"
            "oidc_conformant": True,
        }
    
    if (enable_organization):
        client_config.update({
            # enable login with Auth0 Organizations
            "organization_usage": "require",
            "organization_require_behavior": "post_login_prompt" # pre_login_prompt = Prompt for Organization, post_login_prompt = Prompt for Credentials (requires oidc_conformant=true)
        })
    return auth0.clients.create(client_config)

# get an existing auth0 client or create a new
def create_or_update_auth0_client(auth0, client_name, callback_url, enable_organization, login_url_postfix = ""):
    client = get_auth0_client_by_name(auth0, client_name)
    # create admin application
    if client == 0:
        print("CREATE: Auth0 Application *" + client_name + "*")
        return create_auth0_client(auth0, client_name, callback_url, enable_organization, login_url_postfix)
    else:
        print("UPDATE: Auth0 Application *" + client_name+ "*")
        # update callback URL
        client_id = client["client_id"]
        auth0.clients.update(client_id, {
            "callbacks": [callback_url],
            "allowed_logout_urls": [callback_url],
            "web_origins": [callback_url],
            "initiate_login_uri": callback_url + login_url_postfix
        })
    return client

# =========================================================
# Create User in DB
# =========================================================
import random
import string
from auth0.authentication import Database
# generate a random password - maybe there is a better approach?
def generate_random_password(count):
    generated = ''.join(random.choice(string.printable) for i in range(count-4)) # include 4 basic characters that are required by the Auth0 password policy
    return "aZ0!" + generated

# get an existing user or create a new user for a database connection
def get_or_create_user_for_database_connection(auth0, email, connection_name, auth0_domain, client_id):
    users = auth0.users.list(search_engine='v3', q="email:"+email+" AND identities.connection:" + connection_name)
    if (users["length"] > 0):
        print("EXISTS: User *" + email + "* for database connection *" + connection_name + "*")
        return users["users"][0]
    else:
        print("CREATE: User *" + email + "* for database connection *" + connection_name + "*")
        # create user
        user = auth0.users.create(
            {
                "email":email,
                "password": generate_random_password(10),
                "connection":connection_name,
                "verify_email":False
            })
        # force passsword reset for newly created user
        database = Database(domain= auth0_domain, client_id=client_id)
        database.change_password(email=email, connection=connection_name)
        return user

# =========================================================
# Create Database Connection
# =========================================================

# get id of existing database connection
def get_connection_id_by_name(auth0, connection_name):
    for connection in auth0.connections.all(strategy="auth0"):
        if connection["name"] == connection_name:
            return connection["id"]
    return 0

def get_or_create_db_connection(auth0, connection_name, client_id, m2m_client_id):
    connection_id = get_connection_id_by_name(auth0, connection_name)
    # create DB connection and admin user
    if connection_id == 0:
        print("CREATE: Auth0 Database *" + connection_name + "*")
        # create DB connection
        connection = auth0.connections.create(
            {
                "name":connection_name,
                "strategy":"auth0",
                "options": {
                    "disable_signup":True
                },
                "enabled_clients": [
                    client_id,
                    m2m_client_id # the M2M application must be also assigned to the DB Connection, or creating users is not allowed via APIs
                ]
            })
        connection_id = connection["id"]
    else:
        print("EXISTS: Auth0 Database *" + connection_name + "*")
    return connection_id


# =========================================================
# Create Organization
# =========================================================
from auth0.exceptions import Auth0Error
    
def get_or_create_organization(auth0, org_name, org_tier, org_tenant_id, connection_id):

    # get existing organization
    try:
        org = auth0.organizations.get_organization_by_name(name=org_name)
        print("EXISTS: Organization *" + org_name + "*")
        return org
    except Auth0Error:
        print("CREATE: Organization *" + org_name + "*")
        return auth0.organizations.create_organization(
        {
            "name": org_name,
            "display_name": org_name,
            "metadata": {
                "tier" : org_tier,
                "tenant_id" : org_tenant_id
            },
            "enabled_connections": [
                {
                    "connection_id": connection_id,
                    "assign_membership_on_login": False, # assign user manually to enforce isolation between Auth0 Organizations
                }
            ]
        })
    
# =========================================================
# Invite User to Organization
# =========================================================
"""
def invite_user_to_organization(auth0, organizationId, email, clientId, connectionId):
    auth0.organizations.create_organization_invitation(organizationId,
        {
            "client_id":clientId,
            "inviter": {
                "name":"Admin"
            },
            "invitee":
                {
                    "email": email
                },
            "connection_id": connectionId
        }
    )
    print("INVITE: User *" + email + "* to Organization *" + organizationId + "*")
"""

def add_user_to_organization(auth0, organization_id, user_id):
    auth0.organizations.create_organization_members(organization_id, {"members":[user_id]})
    pass

# =========================================================
# Assign User to a Role for an Organization
# =========================================================
"""
def invite_user_to_organization(auth0, organizationId, email, clientId, connectionId):
    auth0.organizations.create_organization_invitation(organizationId,
        {
            "client_id":clientId,
            "inviter": {
                "name":"Admin"
            },
            "invitee":
                {
                    "email": email
                },
            "connection_id": connectionId
        }
    )
    print("INVITE: User *" + email + "* to Organization *" + organizationId + "*")
"""

def assign_user_to_role_for_organization(auth0, user_id, role_id, organization_id):
    return auth0.organizations.create_organization_member_roles(
        id=organization_id,
        user_id=user_id,
        body={
            "roles": [
                role_id
            ]
        }
)

# =========================================================
# Create Role
# =========================================================
def get_or_create_role(auth0, role_name):
    roles = auth0.roles.list(name_filter=role_name)
    if (roles["total"] > 0):
        print("EXISTS: Role *" + role_name + "*")
        return roles["roles"][0]
    else:
        print("CREATE: Role *" + role_name + "*")
        return auth0.roles.create({
            "name": role_name,
            "description": role_name
        })

def add_user_to_role(auth0, role_name, user_id):
    auth0.roles.add_users(role_name, [user_id])


# =========================================================
# Create SaaS App API
# =========================================================
from urllib.parse import quote # required to encode URL parameter

def get_or_create_api(auth0, api_name, api_audience):
    try:
        url_encoded_audience = quote(api_audience, safe="")
        api = auth0.resource_servers.get(url_encoded_audience)
        print("EXISTS: API *" + api_audience + "*")
        return api
    except Auth0Error:
        print("CREATE: API *" + api_audience)
        return auth0.resource_servers.create({
            "name":api_name,
            "identifier": api_audience,
            "skip_consent_for_verifiable_first_party_clients":True
        })

# =========================================================
# Get or update Action
# =========================================================
def create_or_update_action(auth0, action_name, action_code, trigger_id = "post-login", trigger_version = "v3"):

    actions = auth0.actions.get_actions(action_name=action_name)

    if (len(actions["actions"]) > 0):
        print("UPDATE: Action *" + action_name + "*")
        action = actions["actions"][0]
        action_id = action["id"]
        # 1. create action
        auth0.actions.update_action(id=action_id, body={ "code": action_code })
        # 2. deploy action
        auth0.actions.deploy_action(action_id)
        return action
    else:
        print("CREATE: Action *" + action_name + "*")

        # 1. create action
        action = auth0.actions.create_action(
        {
            "name": action_name,
            "supported_triggers": [
                {
                    "id": trigger_id,
                    "version": trigger_version,
                    "compatible_triggers": [
                        {"id": trigger_id, "version": trigger_version}
                    ],
                }
            ],
            "code": action_code,
        })
        
        # 2. deploy action
        action_id = action["id"]
        auth0.actions.deploy_action(action_id)

        # 3. create trigger binding
        auth0.actions.update_trigger_bindings(
            trigger_id,
            {
                "bindings": [
                    {
                        "ref": {"type": "action_name", "value": action_name},
                        "display_name": action_name,
                    }
                ]
            },
        )
        return action

# =========================================================
# Auth0 Action to enrich SaaS Token
# =========================================================
auth0_action_enrich_saas_token = """
// V1
exports.onExecutePostLogin = async (event, api) => {
     const saas_namespace = 'https://saas-serverless';
 
     const SYSTEM_ADMIN_ROLE = 'SystemAdmin'
     const CUSTOMER_SUPPORT_ROLE = 'CustomerSupport'
     const TENANT_ADMIN_ROLE = 'TenantAdmin'
     const TENANT_USER_ROLE = 'TenantUser'
 
     const AUTH0_ADMIN_APP_NAME = 'SaaS Admin'
     const AUTH0_SAAS_APP_NAME = 'SaaS Application'
     
     // Step 1: Include Email in Access Token
     api.accessToken.setCustomClaim(saas_namespace + '/email', event.user.email);
 
     // Step 2: Default Role for all Users is TenantUser
     var roles = TENANT_USER_ROLE
 
     // Step 3: User is Accessing the Admin Application
     if (event.client && event.client.name == AUTH0_ADMIN_APP_NAME)
     {
         // provide default CustomerSupportRole
         roles = CUSTOMER_SUPPORT_ROLE
         if (event.authorization.roles && event.authorization.roles.includes(SYSTEM_ADMIN_ROLE))
         {
           roles = SYSTEM_ADMIN_ROLE;
         }
     }
 
     // Step 4: User is Accessing the SaaS Application
     if (event.client && event.client.name == AUTH0_SAAS_APP_NAME)
     {
         if (event.authorization.roles && event.authorization.roles.includes(TENANT_ADMIN_ROLE))
         {
           roles = TENANT_ADMIN_ROLE;
         }
 
         // Include TenantID and Tier in ID and Acccess Token
         if(event.organization) {
           var tenantId = event.organization.metadata.tenant_id;
           api.idToken.setCustomClaim(saas_namespace + '/tenantId', tenantId);
           api.accessToken.setCustomClaim(saas_namespace + '/tenantId', tenantId);
 
           var tier = event.organization.metadata.tier;
           api.idToken.setCustomClaim(saas_namespace + '/tier', tier);
           api.accessToken.setCustomClaim(saas_namespace + '/tier', tier);
         }
     }
 
     // Step 5: Include Role in Access and ID Token
     api.idToken.setCustomClaim(saas_namespace + '/roles', roles);
     api.accessToken.setCustomClaim(saas_namespace + '/roles', roles);
 };
 """