#!/bin/bash -e

echo "$(date) cleaning up Auth0 resources..."

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-Domain"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-ClientId"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-ClientSecret"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-AdminApp-ClientId"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-AdminApp-DatabaseId"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-SaaSApp-ClientId"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-SaaSApp-DatabaseId"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-SystemAdmin-RoleId"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-TenantAdmin-RoleId"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-ActionId"

aws ssm delete-parameter \
    --name "Serverless-SaaS-Auth0-ApiId"