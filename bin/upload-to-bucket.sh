zip -r9 paypal-processor.zip index.py
zip -r9 layer.zip python

aws s3 cp paypal-processor.zip s3://rcw-code-bucket/paypal-processor/paypal-processor.zip
aws s3 cp layer.zip s3://rcw-code-bucket/paypal-processor/layer.zip

rm rf paypal-processor.zip
rm rf layer.zip