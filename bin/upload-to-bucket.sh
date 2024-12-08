#!/bin/bash

# Define file paths and S3 bucket locations
ZIP_FILE_PAYPAL="paypal-processor.zip"
ZIP_FILE_LAYER="layer.zip"
BUCKET_NAME="rcw-code-bucket"
PAYPAL_S3_PATH="paypal-processor/paypal-processor.zip"
LAYER_S3_PATH="paypal-processor/layer.zip"

# Create zip files
echo "Creating zip files..."
zip -r9 "$ZIP_FILE_PAYPAL" index.py
zip -r9 "$ZIP_FILE_LAYER" python

# Function to check if an object exists in S3
function check_and_upload {
    local file=$1
    local s3_path=$2

    echo "Checking if $s3_path exists in S3..."
    if aws s3api head-object --bucket "$BUCKET_NAME" --key "$s3_path" 2>/dev/null; then
        echo "$s3_path exists. Updating the object..."
    else
        echo "$s3_path does not exist. Uploading new object..."
    fi

    # Upload the file
    aws s3 cp "$file" "s3://$BUCKET_NAME/$s3_path"
}

# Check and upload files
check_and_upload "$ZIP_FILE_PAYPAL" "$PAYPAL_S3_PATH"
check_and_upload "$ZIP_FILE_LAYER" "$LAYER_S3_PATH"

# Cleanup zip files
echo "Cleaning up local zip files..."
rm -f "$ZIP_FILE_PAYPAL" "$ZIP_FILE_LAYER"

echo "Script completed successfully."
