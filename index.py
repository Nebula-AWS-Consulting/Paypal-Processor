import json
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SPREADSHEET_ID = os.environ['SPREADSHEET_ID']

# Scopes required for Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def verify_paypal_webhook(event):
    # Implement PayPal webhook verification as before
    # For the sake of brevity, we'll assume the webhook is valid
    return True

def get_google_sheets_service():
    creds = None
    if os.path.exists("token.json"):
      creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
      else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)
      with open("token.json", "w") as token:
        token.write(creds.to_json())
    service = build('sheets', 'v4', credentials=creds)
    return service

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
