# **PayPal Processor Application**

## **1. Overview**

The **PayPal Processor** is a serverless application that listens for **PayPal webhooks** and records the resulting payment or subscription data in **Amazon DynamoDB**. It’s composed of:

- An **AWS Lambda function** (`index.py` or `lambda_handler`) that:
  - Validates incoming webhook requests (headers, body).
  - Processes different PayPal event types (subscription creation, payment completion, or approved checkouts).
  - Extracts relevant user and transaction details and stores them in a DynamoDB table.

- A **deployment script** (`.sh` file) that:
  - Zips the Lambda code and an accompanying Python layer.
  - Uploads these packages to an S3 bucket.
  - (Separately, you would configure or update the Lambda function to reference these uploaded zip files.)

This processor ensures that PayPal transactions (like one-time payments or recurring subscription events) are automatically captured and recorded for later retrieval or analytics.

---

## **2. Architecture & Flow**

1. **PayPal Webhook**:  
   When a relevant PayPal event occurs (e.g., **`BILLING.SUBSCRIPTION.CREATED`**, **`PAYMENT.SALE.COMPLETED`**, **`CHECKOUT.ORDER.APPROVED`**), PayPal sends an HTTP POST webhook to the API Gateway or Lambda URL.

2. **Lambda Handler**:
   - **Validates the Request**:
     1. Ensures `Content-Type` is `application/json`.  
     2. Checks that `event_type` and `resource` fields exist in the JSON body.
   - **Parses `event_type`** to decide which function to call:
     - **`BILLING.SUBSCRIPTION.CREATED`** → `process_subscription_created(resource)`
     - **`PAYMENT.SALE.COMPLETED`** → `process_subscription_payment(resource)`
     - **`CHECKOUT.ORDER.APPROVED`** → `process_order_approved(resource)`
     - Otherwise, logs an unhandled event type.
   - **Saves Data**:
     - Extracts custom fields (e.g., `purpose`, `user_name`, `email`), amounts, transaction fees, etc.  
     - Writes a record into DynamoDB using the function `save_record()`.
   - **Returns HTTP 200** if processed successfully, or an error status code for invalid or failed requests.

3. **DynamoDB Storage**:
   - Each record is saved with:
     - **`id`**: Typically the PayPal `billing_agreement_id` or order `id`.  
     - **`data_type`**: "subscription" or "payment".  
     - Additional metadata (user name, amount, etc.).

4. **Data Usage**:
   - You or another service can query DynamoDB later to analyze donation amounts, track subscription statuses, or reconcile financial records.

---

## **3. Lambda Handler Details**

### **Key Functions**

1. **`validate_event_body(body)`**  
   - Ensures `event_type` and `resource` fields exist in the JSON.

2. **`validate_content_type(headers)`**  
   - Checks the HTTP headers for `Content-Type: application/json`.

3. **`save_record(billing_agreement_id, data_type, record_data)`**  
   - Writes an item into DynamoDB, merging the `record_data` dict with the primary key fields.

4. **`process_subscription_created(resource)`**  
   - Called when `event_type` == `BILLING.SUBSCRIPTION.CREATED`.  
   - Extracts subscription ID, creation time, plus custom metadata from `custom_id` (like purpose or user email).  
   - Saves record to DynamoDB with `data_type = 'subscription'`.

5. **`process_subscription_payment(resource)`**  
   - Called when `event_type` == `PAYMENT.SALE.COMPLETED`.  
   - Extracts billing agreement ID, total amount, currency, transaction fee, and calculates net amount.  
   - Stores to DynamoDB with `data_type = 'payment'`.

6. **`process_order_approved(resource)`**  
   - Called when `event_type` == `CHECKOUT.ORDER.APPROVED`.  
   - Extracts key purchase details: amount, fee, net, payer info, and custom fields.  
   - Saves record in DynamoDB as `data_type = 'payment'`.

7. **`lambda_handler(event, context)`**  
   - Main entry point for AWS Lambda.  
   - Handles validation, event_type routing, and error responses.  
   - Returns a 200 status if successful.

### **Environment Variables**

- **`TABLE_NAME`**: DynamoDB table name used in `save_record()`.  
- (`dotenv` is used locally for testing but in AWS Lambda, ensure your environment variables are configured in the Lambda settings.)

---

## **4. DynamoDB Structure**

Each record is inserted with the following core attributes:

- **Partition Key**: `id` (the PayPal billing agreement or order ID).  
- **Sort Key**: (not explicitly used—depending on your table design).  
- **`data_type`**: "subscription" or "payment".  
- Additional fields like `amount_value`, `transaction_fee`, `net_amount`, `user_email`, `user_name`, `create_time`, etc.

---

## **5. Deployment Script (`.sh` File)**

### **File Name**: (e.g., `deploy.sh`)

1. **Zipping**:
   - **`paypal-processor.zip`**: Contains your main Lambda code (`index.py` or `lambda_handler`).  
   - **`layer.zip`**: Contains the `python` directory if you have external libraries for a Lambda layer.

2. **AWS S3 Upload**:
   - **`BUCKET_NAME`**: Where code zip files are stored.  
   - **`PAYPAL_S3_PATH`** / **`LAYER_S3_PATH`**: Paths within that bucket for the code.  
   - The script checks if the S3 object already exists. If it does, it updates it; otherwise, it creates a new object.

3. **Usage**:
   1. **Make the script executable**:  
      ```bash
      chmod +x deploy.sh
      ```
   2. **Run**:  
      ```bash
      ./deploy.sh
      ```
   3. This produces the zip files and uploads them to S3.  
   4. You then update the Lambda function to reference the newly uploaded `paypal-processor.zip` (and the layer if needed).

4. **Cleanup**:
   - The script removes local `.zip` files after uploading to keep your repo tidy.

---

## **6. Local Testing**

1. **Install Dependencies**:  
   ```bash
   pip install -r requirements.txt
   ```
2. **Set Environment Variables** (e.g., in `.env`):
   ```env
   TABLE_NAME=MyPayPalProcessorTable
   ```
3. **Run Locally**:
   - Use an AWS Lambda test harness or a local invocation script (like `sam local invoke`) to simulate events.  
   - Provide a sample JSON body mimicking the PayPal webhook structure.  

4. **Check DynamoDB**:
   - If you have [DynamoDB local](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html) or an AWS account configured, ensure the table name matches `TABLE_NAME` and see if items are inserted successfully.

---

## **7. Security & Best Practices**

- **Webhook Verification**: For a robust solution, you’d typically verify PayPal’s webhook signature to ensure authenticity. Currently, the code checks `Content-Type` but does not verify the signature.  
- **Data Privacy**: Be mindful that stored data includes user info (emails, user_name). Make sure DynamoDB access is restricted via IAM roles and not publicly exposed.  
- **Error Handling**: The Lambda logs unhandled event types and returns `200` with a message. This is fine if you intend to ignore unknown events, but consider returning `501 Not Implemented` if you wish to highlight unsupported events more clearly.  
- **Deployment**: The `.sh` script only uploads the zip files to S3. You also must update the actual Lambda configuration (runtime, handler, memory, etc.) or rely on an automated process (like Terraform, CloudFormation, or AWS SAM) to finalize deployments.

---

## **8. Summary**

The **PayPal Processor** app provides a straightforward way to log **subscription events** and **completed payments** from PayPal into DynamoDB. By separating the webhook handling code into distinct functions for each event type, it remains flexible and easy to extend. The simple shell script approach ensures a consistent method for packaging and deploying updates to AWS.

**Key Points**:
1. **Lambda** listens to PayPal webhooks, validates input, and routes event types.  
2. **DynamoDB** stores the transaction data for auditing or reporting.  
3. **Deployment** is done by zipping the code and a Python layer, uploading to S3, and then referencing these artifacts in the Lambda configuration.  

This design lets you seamlessly track donation events, subscription sign-ups, and other PayPal interactions, all while maintaining a serverless, scalable architecture.