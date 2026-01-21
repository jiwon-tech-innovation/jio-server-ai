
import boto3
import os
import sys
import base64
import json

def decode_jwt_payload(token):
    try:
        # JWT is header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload = parts[1]
        # Base64 padding if needed
        padding = len(payload) % 4
        if padding:
            payload += '=' * (4 - padding)
        decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
        return json.loads(decoded)
    except Exception as e:
        print(f"Error decoding JWT: {e}")
        return None

def debug_aws():
    print("--- START AWS DEBUG V2 ---")
    
    # 1. Check Env
    role_arn = os.environ.get('AWS_ROLE_ARN')
    token_file = os.environ.get('AWS_WEB_IDENTITY_TOKEN_FILE')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    print(f"Role ARN: {role_arn}")
    print(f"Token File: {token_file}")
    print(f"Region: {region}")
    
    if not role_arn or not token_file:
        print("ERROR: Missing AWS IRSA environment variables.")
        return

    # 2. Read Token
    try:
        with open(token_file, 'r') as f:
            web_id_token = f.read().strip()
        print(f"Token loaded. Length: {len(web_id_token)}")
        
        # DECODE AND PRINT CLAIMS
        claims = decode_jwt_payload(web_id_token)
        if claims:
            print("\n--- TOKEN CLAIMS (Ground Truth) ---")
            print(f"ISSUER (iss): {claims.get('iss')}")
            print(f"SUBJECT (sub): {claims.get('sub')}")
            print(f"AUDIENCE (aud): {claims.get('aud')}")
            print("-----------------------------------\n")
        else:
            print("WARNING: Could not decode token claims.")
            
    except Exception as e:
        print(f"ERROR: Could not read token file: {e}")
        return

    # 3. Explicit STS Assume Role
    print(f"Attempting STS AssumeRoleWithWebIdentity...")
    try:
        # Use ap-northeast-2 for STS as the cluster is there
        sts = boto3.client('sts', region_name='ap-northeast-2')
        response = sts.assume_role_with_web_identity(
            RoleArn=role_arn,
            RoleSessionName='DebugSession',
            WebIdentityToken=web_id_token
        )
        print("SUCCESS: STS AssumeRole succeeded! Credentials obtained.")
        creds = response['Credentials']
    except Exception as e:
        print(f"CRITICAL FAILURE at STS AssumeRole: {e}")
        print("Possible causes: Trust Policy mismatch, Wrong Role ARN, OIDC Provider mismatch.")
        return

    # 4. Explicit Bedrock Call with Temp Creds
    print(f"Attempting Bedrock ListFoundationModels in us-east-1...")
    try:
        bedrock = boto3.client(
            'bedrock',
            region_name='us-east-1',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )
        bedrock.list_foundation_models()
        print("SUCCESS: Bedrock is accessible!")
    except Exception as e:
        print(f"CRITICAL FAILURE at Bedrock: {e}")
        print("Possible causes: IAM Role Permission Policy missing 'bedrock:*', Region mismatch.")

if __name__ == "__main__":
    debug_aws()
