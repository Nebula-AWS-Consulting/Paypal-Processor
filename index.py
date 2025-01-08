import json
import boto3

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
        'id': billing_agreement_id,
        'data_type': data_type,
        **record_data
    }
    
    table.put_item(Item=item)

def process_subscription_created(resource):
    """
    :param resource: Subscription resource data from PayPal
    """
    billing_agreement_id = resource.get('id')

    subscription_create_time = resource.get('create_time')

    custom_id = resource.get("custom_id", "")

    parts = {}
    for segment in custom_id.split('|'):
        subparts = segment.split(':', 1)
        if len(subparts) == 2:
            key, value = subparts
            parts[key] = value
        else:
            print(f"Skipping invalid segment: '{segment}' - expected format key:value")

    purpose = parts.get('purpose', 'Unknown_Purpose')
    user_email = parts.get('email', 'Unknown_Email')
    user_name = parts.get('user_name', 'Unknown_Name')

    subscriber_info = {
        'user_name': user_name,
        'purpose': purpose,
        'user_email': user_email,
        'create_time': subscription_create_time
    }

    save_record(billing_agreement_id, 'subscription', subscriber_info)

def process_subscription_payment(resource):
    """
    :param resource: Payment resource data from PayPal
    """
    billing_agreement_id = resource.get('billing_agreement_id')
    amount_value = resource['amount']['total']
    amount_currency = resource['amount']['currency']
    transaction_fee = resource.get('transaction_fee', {}).get('value', '0.00')
    net_amount = float(amount_value) - float(transaction_fee)

    custom_id = resource.get("custom", "")

    parts = {}
    for segment in custom_id.split('|'):
        subparts = segment.split(':', 1)
        if len(subparts) == 2:
            key, value = subparts
            parts[key] = value
        else:
            print(f"Skipping invalid segment: '{segment}' - expected format key:value")

    purpose = parts.get('purpose', 'Unknown_Purpose')
    user_email = parts.get('email', 'Unknown_Email')
    user_name = parts.get('user_name', 'Unknown_Name')

    payment_info = {
        'purpose': purpose,
        'user_name': user_name,
        'user_email': user_email,
        'amount_value': amount_value,
        'amount_currency': amount_currency,
        'transaction_fee': transaction_fee,
        'net_amount': str(net_amount),
        'create_time': resource.get('create_time', 'Unknown_Time')
    }

    save_record(billing_agreement_id, 'payment', payment_info)

def process_order_approved(resource):
    try:
        id = resource.get('id', 'Unknown_ID')
        purchase_units = resource.get('purchase_units', [])
        if not purchase_units:
            raise ValueError("Missing purchase_units in resource.")

        purchase_unit = purchase_units[0]
        amount = purchase_unit.get('amount', {})
        amount_value = amount.get('value', '0.00')
        amount_currency = amount.get('currency_code', 'USD')

        payer = resource.get('payer', {})
        payer_email = payer.get('email_address', 'Unknown_Email')
        name_dict = payer.get('name', {})
        payer_name = (name_dict.get('given_name', 'Unknown_Name') + ' ' + name_dict.get('surname', 'Unknown_Surname'))
        
        captures = purchase_unit.get('payments', {}).get('captures', [])
        first_capture = captures[0] if captures else {}

        seller_breakdown = first_capture.get('seller_receivable_breakdown', {})
        payment_fee = seller_breakdown.get('paypal_fee', {}).get('value', '0.00')
        net_amount = seller_breakdown.get('net_amount', {}).get('value', '0.00')

        custom_id = purchase_unit.get("custom_id", "")

        parts = {}
        for segment in custom_id.split('|'):
            subparts = segment.split(':', 1)
            if len(subparts) == 2:
                key, value = subparts
                parts[key] = value
            else:
                print(f"Skipping invalid segment: '{segment}' - expected format key:value")

        purpose = parts.get('purpose', 'Unknown_Purpose')
        user_email = parts.get('email', 'Unknown_Email')
        user_name = parts.get('user_name', 'Unknown_Name')

        payment_info_db = {
            'purpose': purpose,
            'user_name': user_name,
            'payer_name': payer_name,
            'user_email': user_email,
            'payer_email': payer_email,
            'amount_value': amount_value,
            'amount_currency': amount_currency,
            'transaction_fee': payment_fee,
            'net_amount': net_amount,
            'create_time': resource.get('create_time', 'Unknown_Time')
        }

        save_record(id, 'payment', payment_info_db)

    except Exception as e:
        print(f"Error processing order approved: {e}")
        raise

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
        elif event_type == 'PAYMENT.SALE.COMPLETED':
            process_subscription_payment(resource)
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