# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import boto3
import os
import logger 
from aws_lambda_powertools import Tracer

import cognito.user_management_util as user_management_util
from abstract_classes.idp_user_management_abstract_class import IdpUserManagementAbstractClass
from cognito.cognito_identity_provider_management import CognitoIdentityProviderManagement

tracer = Tracer()
region = os.environ['AWS_REGION']
client = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')
table_tenant_user_map = dynamodb.Table('ServerlessSaaS-TenantUserMapping')
table_tenant_details = dynamodb.Table('ServerlessSaaS-TenantDetails')
idp_mgmt = CognitoIdentityProviderManagement()

from authzero.auth0_utils import *

def ssm_get_value(key):
    return ssm.get_parameter(Name=key, WithDecryption=True)['Parameter']['Value']

class Auth0IdpUserManagementService(IdpUserManagementAbstractClass):
    def create_tenant_admin_user(self, event):
        logger.info(event)

        # Step 1: Get values from event and SSM
        logger.info("Step 1: Get values from event and SSM")
        tenant_id = event['tenantId']
        tenant_name = event['tenantName']
        organization_id = event['idpDetails']['idp']['orgId']
        user_email = event['tenantEmail']

        auth0_domain = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_DOMAIN)
        auth0_client_id = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_CLIENT_ID)
        auth0_client_secret = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_CLIENT_SECRET)

        saas_app_client_id = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_SAAS_APP_CLIENT_ID)
        tenant_admin_role_id = ssm_get_value(SSM_SERVERLESS_SAAS_AUTH0_TENANT_ADMIN_ROLE_ID)

        # Step 2: Get Access Token for Management API
        logger.info("Step 2: Get Access Token for Management API")
        auth0 = create_auth0(auth0_domain, auth0_client_id, auth0_client_secret)

        # Step 3: Create User in SaaS App Database
        logger.info("Step 3: Create User in SaaS App Database")
        user = get_or_create_user_for_database_connection(auth0, user_email, AUTH0_SAAS_APP_DATABASE_NAME, auth0_domain, saas_app_client_id)
        user_id = user["user_id"]

        # Step 4: Invite created User to Organization
        logger.info("Step 4: Invite created User to Organization")
        add_user_to_organization(auth0, organization_id, user_id)

        # Step 5: Assign User to TenantAdmin Role of the Organization
        logger.info("Step 5: Assign User to TenantAdmin Role of the Organization")
        assign_user_to_role_for_organization(auth0, user_id, tenant_admin_role_id, organization_id)

        # Step 6: Return Values
        logger.info("Step 6: Return Values")

        return { 'tenantAdminUserName': user_email }

    def create_user(self, event):
        # TODO: Implement Auth0 create_user
        user_details = event
        user_pool_id = user_details['idpDetails']['idp']['userPoolId']
        response = client.admin_create_user(
            Username=user_details['userName'],
            UserPoolId=user_pool_id,
            ForceAliasCreation=True,
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': user_details['userEmail']
                },
                {
                    'Name': 'email_verified',
                    'Value': 'true'
                },
                {
                    'Name': 'custom:userRole',
                    'Value': user_details['userRole'] 
                },            
                {
                    'Name': 'custom:tenantId',
                    'Value': user_details['userTenantId']
                }
            ]
        )
        user_management_util.add_user_to_group(user_pool_id, user_details['userName'], user_details['userTenantId'])
        return response

    def get_users(self, event):
         # TODO: Implement Auth0 get_users
        user_details = event
        user_pool_id = user_details['idpDetails']['idp']['userPoolId']
        tenant_id = user_details['tenantId']  
        users = []
        response = client.list_users(
            UserPoolId=user_pool_id
        )
        num_of_users = len(response['Users'])
        if (num_of_users > 0):
            for user in response['Users']:
                is_same_tenant_user = False
                user_info = UserInfo()
                for attr in user["Attributes"]:
                    if(attr["Name"] == "custom:tenantId" and attr["Value"] == tenant_id):
                        is_same_tenant_user = True
                        user_info.tenant_id = attr["Value"]
                    if(attr["Name"] == "custom:userRole"):
                        user_info.user_role = attr["Value"]
                    if(attr["Name"] == "email"):
                        user_info.email = attr["Value"] 
                if(is_same_tenant_user):
                    user_info.enabled = user["Enabled"]
                    user_info.created = user["UserCreateDate"]
                    user_info.modified = user["UserLastModifiedDate"]
                    user_info.status = user["UserStatus"] 
                    user_info.user_name = user["Username"]
                    users.append(user_info)                    
        return users

    def get_user(self, event):
         # TODO: Implement Auth0 get_user
        return self.get_user_info(event)

    def update_user(self, event):
         # TODO: Implement Auth0 update_user
        user_details = event
        user_pool_id = user_details['idpDetails']['idp']['userPoolId']
        user_name = user_details['userName']
        return client.admin_update_user_attributes(
            Username=user_name,
            UserPoolId=user_pool_id,
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': user_details['userEmail']
                },
                {
                    'Name': 'custom:userRole',
                    'Value': user_details['userRole'] 
                }
            ]
        )

    def disable_user(self, event):
         # TODO: Implement Auth0 disable_user
        user_details = event
        user_pool_id = user_details['idpDetails']['idp']['userPoolId']
        user_name = user_details['userName']
        response = client.admin_disable_user(
            Username=user_name,
            UserPoolId=user_pool_id
        )
        return response

    def enable_user(self, event):
         # TODO: Implement Auth0 enable_user
        user_details = event
        user_pool_id = user_details['idpDetails']['idp']['userPoolId']
        user_name = user_details['userName']
        return client.admin_enable_user(
            Username=user_name,
            UserPoolId=user_pool_id
        )    

    def get_user_info(self, event):
         # TODO: Implement Auth0 get_user_info
        user_details = event
        user_pool_id = user_details['idpDetails']['idp']['userPoolId']
        user_name = user_details['userName']          
        response = client.admin_get_user(
            UserPoolId=user_pool_id,
            Username=user_name
        )
        user_info =  UserInfo()
        user_info.user_name = response["Username"]
        for attr in response["UserAttributes"]:
            if(attr["Name"] == "custom:tenantId"):
                user_info.tenant_id = attr["Value"]
            if(attr["Name"] == "custom:userRole"):
                user_info.user_role = attr["Value"]    
            if(attr["Name"] == "email"):
                user_info.email = attr["Value"] 
        return user_info    

class UserInfo:
    def __init__(self, user_name=None, tenant_id=None, user_role=None, 
    email=None, status=None, enabled=None, created=None, modified=None):
        self.user_name = user_name
        self.tenant_id = tenant_id
        self.user_role = user_role
        self.email = email
        self.status = status
        self.enabled = enabled
        self.created = created
        self.modified = modified