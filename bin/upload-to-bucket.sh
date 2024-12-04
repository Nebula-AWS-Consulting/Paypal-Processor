## zip -r paypal-processor.zip index.py .
## zip -r9 layer.zip layer   

aws s3 cp paypal-processor.zip s3://rcw-code-bucket/paypal-processor/paypal-processor.zip
aws s3 cp layer.zip s3://rcw-code-bucket/paypal-processor/layer.zip