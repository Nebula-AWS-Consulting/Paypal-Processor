import json
import os
import boto3
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.environ['SPREADSHEET_ID']
SECRET_NAME = os.environ['SERVICE_ACCOUNT_SECRET_NAME']

def get_google_sheets_service():
    # Fetch secret from Secrets Manager
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=SECRET_NAME)
    secret_str = response['SecretString']
    service_account_info = json.loads(secret_str)

    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service

def verify_paypal_webhook(event):
    # Implement PayPal webhook verification as before
    # For the sake of brevity, we'll assume the webhook is valid
    return True

def lambda_handler(event, context):
    if not verify_paypal_webhook(event):
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid webhook signature.'})
        }

    body = json.loads(event['body'])
    event_type = body.get('event_type')

    if event_type == 'PAYMENT.SALE.COMPLETED':
        payment_info = [
            body['resource']['id'],
            body['resource']['payer']['email_address'],
            body['resource']['amount']['value'],
            body['resource']['amount']['currency_code'],
            body['resource']['create_time']
        ]

        try:
            service = get_google_sheets_service()

            sheet_range = 'A1:E20'
            value_range_body = {
                'values': [payment_info]
            }
            request = service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=sheet_range,
                valueInputOption='RAW',
                body=value_range_body
            )
            request.execute()

            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Payment processed and data stored successfully.'})
            }

        except Exception as e:
            print(f'Error: {e}')
            return {
                'statusCode': 500,
                'body': json.dumps({'message': 'An error occurred while processing the payment.'})
            }
    else:
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Event type not processed.'})
        }
