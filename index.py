import json
import os
import boto3
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', 'default_spreadsheet_id')
PARAMETER_NAME = os.environ.get('SERVICE_ACCOUNT_PARAMETER_NAME', 'default_parameter_name')

def get_google_sheets_service():
    try:
        ssm_client = boto3.client('ssm')
        response = ssm_client.get_parameter(Name=PARAMETER_NAME, WithDecryption=True)
        service_account_info = json.loads(response['Parameter']['Value'])

        creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        return service
    except boto3.exceptions.Boto3Error as e:
        print(f"SSM error: {e}")
        raise RuntimeError("Failed to fetch service account credentials from SSM.") from e
    except Exception as e:
        print(f"Error initializing Google Sheets service: {e}")
        raise RuntimeError("Failed to initialize Google Sheets service.") from e

def append_to_google_sheet(sheet_range, data):
    try:
        service = get_google_sheets_service()
        value_range_body = {
            'values': [data]
        }
        request = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_range,
            valueInputOption='RAW',
            body=value_range_body
        )
        request.execute()
    except ValueError as e:
        print(f"ValueError while appending data: {e}")
        raise RuntimeError("Invalid data provided for appending to Google Sheets.") from e
    except Exception as e:
        print(f"Error appending data to Google Sheets: {e}")
        raise RuntimeError("Failed to append data to Google Sheets.") from e

def validate_event_body(body):
    required_fields = ['event_type', 'resource']
    for field in required_fields:
        if field not in body:
            raise ValueError(f"Missing required field: {field}")

    if body.get('event_type') == 'PAYMENT.SALE.COMPLETED':
        resource = body['resource']
        if 'amount' not in resource or 'total' not in resource['amount'] or 'currency' not in resource['amount']:
            raise ValueError("Invalid or incomplete payment resource data.")
        
def validate_content_type(headers):
    content_type = headers.get('Content-Type')
    if content_type != 'application/json':
        raise ValueError("Invalid Content-Type. Expected 'application/json'.")

def lambda_handler(event, context):
    try:
        headers = event.get('headers', {})
        body = event['body']
        if isinstance(body, str):
            body = json.loads(body)

        validate_content_type(headers)  
        validate_event_body(body)
        event_type = body['event_type']

        if event_type == 'PAYMENT.SALE.COMPLETED':
            resource = body['resource']
            purpose = resource.get('custom_id', 'Unknown')
            payer_info = resource.get('payer', {}).get('payer_info', {})
            payer_name = f"{payer_info.get('first_name', '').strip()} {payer_info.get('last_name', '').strip()}".strip() or "Anonymous Donor"
            payment_info = [
                resource['id'],
                purpose,
                payer_name,
                payer_info.get('email_address', 'N/A'),
                resource['amount']['total'],
                resource['amount']['currency'],
                resource['create_time']
            ]
            append_to_google_sheet('A1:E20', payment_info)
        else:
            print(f"Unhandled event type: {event_type}")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'Event type {event_type} not processed.'})
            }

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Event type {event_type} processed successfully.'})
        }

    except json.JSONDecodeError as e:
        print(f"Invalid JSON body: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid JSON format in request body.'})
        }
    except ValueError as e:
        print(f"Validation error: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': str(e)})
        }
    except RuntimeError as e:
        print(f"Runtime error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': str(e)})
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'An unexpected error occurred.'})
        }