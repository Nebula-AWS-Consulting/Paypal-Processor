import json
import os
import boto3
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', 'default_spreadsheet_id')
PARAMETER_NAME = os.environ.get('SERVICE_ACCOUNT_PARAMETER_NAME', 'default_parameter_name')

cached_google_sheets_service = None

def get_google_sheets_service():
    global cached_google_sheets_service
    if cached_google_sheets_service is not None:
        return cached_google_sheets_service

    try:
        ssm_client = boto3.client('ssm')
        response = ssm_client.get_parameter(Name=PARAMETER_NAME, WithDecryption=True)
        service_account_info = json.loads(response['Parameter']['Value'])

        creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        cached_google_sheets_service = build('sheets', 'v4', credentials=creds)
        return cached_google_sheets_service
    except boto3.exceptions.Boto3Error as e:
        print(f"SSM error: {e}")
        raise RuntimeError("Failed to fetch service account credentials from SSM.") from e
    except Exception as e:
        print(f"Error initializing Google Sheets service: {e}")
        raise RuntimeError("Failed to initialize Google Sheets service.") from e

def append_to_google_sheet(data):
    try:
        service = get_google_sheets_service()
        value_range_body = {
            'values': [data]
        }
        request = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"A:E",
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

def validate_content_type(headers):
    content_type = headers.get('Content-Type')
    if content_type != 'application/json':
        raise ValueError("Invalid Content-Type. Expected 'application/json'.")

def save_record(billing_agreement_id, data_type, record_data):
    """
    :param billing_agreement_id: Unique ID for the subscription or payment
    :param data_type: Type of data being saved ('subscription' or 'payment')
    :param record_data: The data to save
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('SubscriptionsAndPayments')
    
    item = {
        'billing_agreement_id': billing_agreement_id,
        'data_type': data_type,
        **record_data
    }
    
    table.put_item(Item=item)

def process_subscription_created(resource):
    """
    :param resource: Subscription resource data from PayPal
    """
    subscription_id = resource.get('id')
    billing_agreement_id = resource.get('id')
    custom_id = resource.get('custom_id', '')

    # Extract last payment details
    billing_info = resource.get('billing_info', {})
    last_payment = billing_info.get('last_payment', {})
    amount = last_payment.get('amount', {}).get('value', '0.00')
    currency = last_payment.get('amount', {}).get('currency_code', 'USD')

    user_id, user_email = None, None
    if '|' in custom_id:
        parts = dict(part.split(':') for part in custom_id.split('|') if ':' in part)
        user_id = parts.get('user_id')
        user_email = parts.get('email')

    subscriber_info = {
        'subscription_id': subscription_id,
        'user_id': user_id,
        'user_email': user_email
    }

    save_record(billing_agreement_id, 'subscription', subscriber_info)

def process_subscription_payment(resource):
    """
    :param resource: Payment resource data from PayPal
    """
    transaction_id = resource.get('id')
    billing_agreement_id = resource.get('billing_agreement_id')
    payment_time = resource.get('create_time')
    amount_value = resource['amount']['total']
    amount_currency = resource['amount']['currency']
    transaction_fee = resource.get('transaction_fee', {}).get('value', '0.00')
    transaction_fee_currency = resource.get('transaction_fee', {}).get('currency_code', 'USD')

    payment_info = {
        'transaction_id': transaction_id,
        'payment_time': payment_time,
        'amount_value': amount_value,
        'amount_currency': amount_currency,
        'transaction_fee': transaction_fee,
        'transaction_fee_currency': transaction_fee_currency
    }

    save_record(billing_agreement_id, 'payment', payment_info)

def process_order_approved(resource):
    purchase_unit = resource['purchase_units'][0]
    amount_value = purchase_unit['amount']['value']
    amount_currency = purchase_unit['amount']['currency_code']

    payer_email = resource['payer']['email_address']
    payer_given_name = resource['payer']['name']['given_name']
    payer_surname = resource['payer']['name']['surname']
    payer_name = f"{payer_given_name} {payer_surname}".strip()

    purpose = purchase_unit.get('custom_id', 'Unknown')

    payment_info = [
        "order",
        resource['id'],  
        purpose,
        payer_name,
        payer_email,
        amount_value, 
        amount_currency, 
        resource['create_time'], 
    ]
    append_to_google_sheet(payment_info)

def lambda_handler(event, context):
    try:
        headers = event.get('headers', {})
        body = event['body']
        if isinstance(body, str):
            body = json.loads(body)

        validate_content_type(headers)
        validate_event_body(body)

        event_type = body.get('event_type')
        resource = body.get('resource')

        if event_type == 'BILLING.SUBSCRIPTION.CREATED':
            process_subscription_created(resource)
            print(resource)
        elif event_type == 'PAYMENT.SALE.COMPLETED':
            process_subscription_payment(resource)
            print(resource)
        elif event_type == 'CHECKOUT.ORDER.APPROVED':
            process_order_approved(resource)
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

    except ValueError as e:
        print(f"ValueError: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'An unexpected error occurred.'})
        }