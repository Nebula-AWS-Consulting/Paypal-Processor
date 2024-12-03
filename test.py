import json
import unittest
from unittest.mock import patch, MagicMock
from index import lambda_handler

class TestLambdaHandler(unittest.TestCase):

    @patch('index.get_google_sheets_service')
    @patch('index.verify_paypal_webhook')
    def test_lambda_handler_payment_sale_completed(self, mock_verify_webhook, mock_google_sheets_service):
        # Mock webhook verification to always return True
        mock_verify_webhook.return_value = True

        # Mock Google Sheets API service
        mock_append = MagicMock()
        mock_google_sheets_service.return_value.spreadsheets.return_value.values.return_value.append.return_value.execute = mock_append

        # Simulate Lambda event for PAYMENT.SALE.COMPLETED
        event = {
            'body': json.dumps({
                'event_type': 'PAYMENT.SALE.COMPLETED',
                'resource': {
                    'id': 'PAYMENT_ID',
                    'payer': {'email_address': 'payer@example.com'},
                    'amount': {'value': '50.00', 'currency_code': 'USD'},
                    'create_time': '2024-12-01T00:00:00Z'
                }
            })
        }
        context = {}  # Lambda context can be left empty for this test

        # Call the lambda_handler
        response = lambda_handler(event, context)

        # Assertions
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('Payment processed and data stored successfully', response['body'])

        # Verify the Google Sheets API was called with correct data
        mock_append.assert_called_once_with()
        mock_google_sheets_service.return_value.spreadsheets.return_value.values.return_value.append.assert_called_once_with(
            spreadsheetId='1Jpicnmuuuy7aS__mGb-3sLgED9vxvELrvffrDtOHWjo',
            range='A1:E20',
            valueInputOption='RAW',
            body={
                'values': [['PAYMENT_ID', 'payer@example.com', '50.00', 'USD', '2024-12-01T00:00:00Z']]
            }
        )

    @patch('index.verify_paypal_webhook')
    def test_lambda_handler_invalid_webhook(self, mock_verify_webhook):
        # Mock webhook verification to return False
        mock_verify_webhook.return_value = False

        # Simulate Lambda event
        event = {'body': json.dumps({})}
        context = {}

        # Call the lambda_handler
        response = lambda_handler(event, context)

        # Assertions
        self.assertEqual(response['statusCode'], 400)
        self.assertIn('Invalid webhook signature', response['body'])

    @patch('index.get_google_sheets_service')
    @patch('index.verify_paypal_webhook')
    def test_lambda_handler_unknown_event_type(self, mock_verify_webhook, mock_google_sheets_service):
        # Mock webhook verification to always return True
        mock_verify_webhook.return_value = True

        # Simulate Lambda event with unknown event type
        event = {
            'body': json.dumps({
                'event_type': 'UNKNOWN_EVENT_TYPE'
            })
        }
        context = {}

        # Call the lambda_handler
        response = lambda_handler(event, context)

        # Assertions
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('Event type not processed', response['body'])

if __name__ == '__main__':
    unittest.main()

## To run test
## python -m unittest test.py
