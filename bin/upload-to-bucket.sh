zip -r paypal-processor.zip index.py .

aws s3 cp paypal-processor.zip s3://rcw-code-bucket/paypal-processor/paypal-processor.zip