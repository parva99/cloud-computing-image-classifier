import os
import time
import boto3
import base64
import subprocess
sqs = boto3.client('sqs', region_name='us-east-1', aws_access_key_id='', aws_secret_access_key='') 
request_queue_url= 'https://sqs.us-east-1.amazonaws.com/521413094069/1229642936-req-queue'
response_queue_url = 'https://sqs.us-east-1.amazonaws.com/521413094069/1229642936-resp-queue'

def run_face_recognition(image_path):
    command = ['python3', '/home/ubuntu/Part2/face_recognition.py', image_path]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    else:
        print("Command execution failed")
        print("Error:\n", result.stderr)

def decode_base64_image(encoded_string):
    return base64.b64decode(encoded_string)
    
def send_to_sqs(output_string, name,unique_id):
    response = sqs.send_message(
        QueueUrl=response_queue_url,
        MessageBody=output_string,  # Use output string as message body
        MessageAttributes={
            'Content': 
            {'StringValue': name,
             'DataType': 'String'
             },
            'UniqueId':{
                'DataType':'String',
                'StringValue': unique_id
        }
    }
    )
    print("Message sent to SQS queue:", response['MessageId'])

def upload_to_s3(value, bucket_name, object_key):
    s3 = boto3.client('s3',region_name='us-east-1', aws_access_key_id='', aws_secret_access_key='')
    response = s3.put_object(Bucket=bucket_name, Key=object_key, Body=value)
    return response

while(1):
    response = sqs.receive_message(QueueUrl=request_queue_url, MaxNumberOfMessages=1,MessageAttributeNames=['All'])
    message=response.get('Messages',[])
    if message:
        message=message[0]
        EncodedImage = message['Body']
        image_data = decode_base64_image(EncodedImage)
        file_name = message['MessageAttributes']['Content']['StringValue']
        unique_id = message['MessageAttributes']['UniqueId']['StringValue']
        upload_to_s3(image_data,"1229642936-in-bucket", file_name)
        base_path = "/home/ubuntu/Part2/face_images_1000"
        final_image_path = os.path.join(base_path, file_name)
        output=run_face_recognition(final_image_path)
        file_name_without_extension=file_name.split('.')[0]
        upload_to_s3(output, "1229642936-out-bucket", file_name_without_extension)
        file_name_output = file_name_without_extension +":"+output
        send_to_sqs(file_name_output,"Output",unique_id)
        receipt_handle = message['ReceiptHandle']
        sqs.delete_message(QueueUrl=request_queue_url,ReceiptHandle=receipt_handle)
        print('1 request processed')
        
