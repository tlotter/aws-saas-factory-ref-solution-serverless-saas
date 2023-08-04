from abstract_classes.idp_authorizer_abstract_class import IdpAuthorizerAbstractClass
import logger
import boto3
import json
import time
import urllib.request
from jose import jwk, jwt
from jose.utils import base64url_decode

region = boto3.session.Session().region_name
class Auth0IdpAuthorizer(IdpAuthorizerAbstractClass):
    def validateJWT(self,event):
        logger.info(event)

        # Step 1: Get values from event
        logger.info("Step 1: Get values from event")
        tenant_details = event
        token = tenant_details['jwtToken']
        idp_details = tenant_details['idpDetails']
        auth0_domain = idp_details['idp']['domain']
        #tenant_app_client_id = idp_details['idp']['clientId']
        audience = "https://" + auth0_domain + "/userinfo"
        keys_url = "https://" + auth0_domain + '/.well-known/jwks.json'
      
        # Step 2: Get jwks.json from Auth0
        logger.info("# Step 2: Get jwks.json from Auth0")
        with urllib.request.urlopen(keys_url) as f:
            response = f.read()
        keys = json.loads(response.decode('utf-8'))['keys']

        # Step 3: Validate JWT
        logger.info("# Step 3: Validate JWT")
        return self.__validateJWT(token, audience, keys)
    
    def getClaims(self,event):
        claims = {}
        claims['username'] = event.get('https://saas-serverless/email')
        claims['tenantId'] = event.get('https://saas-serverless/tenantId')
        claims['userRole'] = event.get('https://saas-serverless/roles')
        return claims
    
    def __validateJWT(self, token, audience, keys):
        # get the kid from the headers prior to verification
        headers = jwt.get_unverified_headers(token)
        kid = headers['kid']
        # search for the kid in the downloaded public keys
        key_index = -1
        for i in range(len(keys)):
            if kid == keys[i]['kid']:
                key_index = i
                break
        if key_index == -1:
            logger.info('Public key not found in jwks.json')
            return False
        # construct the public key
        public_key = jwk.construct(keys[key_index])
        # get the last two sections of the token,
        # message and signature (encoded in base64)
        message, encoded_signature = str(token).rsplit('.', 1)
        # decode the signature
        decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
        # verify the signature
        if not public_key.verify(message.encode("utf8"), decoded_signature):
            logger.info('Signature verification failed')
            return False
        logger.info('Signature successfully verified')
        # since we passed the verification, we can now safely
        # use the unverified claims
        claims = jwt.get_unverified_claims(token)
        # additionally we can verify the token expiration
        if time.time() > claims['exp']:
            logger.info('Token is expired')
            return False
        # and the Audience  (use claims['client_id'] if verifying an access token)
        if audience not in claims['aud']: #Auth0 returns an array of all audiences
            logger.info('Token was not issued for this audience')
            return False
        # now we can use the claims
        logger.info(claims)
        return claims    
