from flask import Flask, request, render_template
import boto3
import base64
import uuid
import threading
import time
lock= threading.Lock()

app = Flask(__name__)
sqs = boto3.client('sqs', region_name='us-east-1', aws_access_key_id='', aws_secret_access_key='') 
ec2_resource = boto3.resource('ec2', region_name='us-east-1', aws_access_key_id='', aws_secret_access_key='')
ec2_client = boto3.client('ec2', region_name='us-east-1',aws_access_key_id='', aws_secret_access_key='')

number_instances=19
request_hit = 0
apptier_ids=[]

user_data = """Content-Type: multipart/mixed; boundary="//"
MIME-Version: 1.0

--//
Content-Type: text/cloud-config; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="cloud-config.txt"

#cloud-config
cloud_final_modules:
- [scripts-user, always]

--//
Content-Type: text/x-shellscript; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="userdata.txt"

#!/bin/bash
python3 /home/ubuntu/Part2/appTier.py >> output.txt 2>&1
--//--
"""

dict1={}
reveiver_dict={}
sqs = boto3.client('sqs', region_name='us-east-1')
response_queue_url = 'https://sqs.us-east-1.amazonaws.com/521413094069/1229642936-resp-queue'

@app.route('/', methods=['POST'])
def upload_file():
    global response_queue_url
    global request_hit
    global number_instances
    global dict1
    global sqs
    global ec2_client
    global ec2_resource
    global apptier_ids
    if 'inputFile' not in request.files:
        return 'No file part', 400
    file = request.files['inputFile']

    fileName = file.filename
    image_string = encode_image_to_base64(file.filename)
    if file.filename == '':
        return 'No selected file', 400

    unique_id= uuid.uuid4().hex


    send_to_sqs(image_string,fileName,unique_id)
    
    with lock:
        request_hit+=1
        if request_hit <= number_instances:
            scale_out(request_hit)
            print("Request hit", request_hit)
    
    #print('File uploaded successfully and sent to SQS')
    while True:
        response = sqs.receive_message(QueueUrl=response_queue_url, MaxNumberOfMessages=1,MessageAttributeNames=['All'],VisibilityTimeout=20)
        messages=response.get('Messages',[])
        for msg in messages:
            # print("msg boy")
            # print(msg)
            unique_id_from_message = msg['MessageAttributes']['UniqueId'].get('StringValue')
            dict1[unique_id_from_message] = msg["Body"]
            output = msg['Body']
            sqs.delete_message(QueueUrl=response_queue_url,ReceiptHandle= msg['ReceiptHandle'])
           #  print(output)
        if unique_id in dict1:
            request_hit-=1
            if request_hit ==0:
                ec2_client.terminate_instances(InstanceIds=apptier_ids)
                apptier_ids=[]
            return dict1[unique_id],200


def encode_image_to_base64(image_path):
    with open("face_images_1000/"+image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
        return encoded_string.decode('utf-8')

def send_to_sqs(encrypted_file,name,unique_id):
    request_queue_url = 'https://sqs.us-east-1.amazonaws.com/521413094069/1229642936-req-queue'

    response = sqs.send_message(
        QueueUrl=request_queue_url,
        MessageBody=encrypted_file,  # Use file name as message body
        MessageAttributes={
            'Content': {
                'DataType': 'String',
                'StringValue': name 

            },
            
            'UniqueId': {
                'DataType': 'String',
                'StringValue' : unique_id
            }
            
        }
    )
    #print("Message sent to SQS queue:", response['MessageId'])

#to change
security_group_ids=['sg-001aecf0eb284d7c2']

def scale_out(instance_counts):

    global user_data

    ami_app_tier = 'ami-0b33d6283aeececf9'
    print("Creating instance", instance_counts)
    instance_id = ec2_resource.create_instances(
        InstanceType="t2.micro",
        MaxCount=1,
        MinCount=1,
        KeyName = 'keypair2',
        ImageId=ami_app_tier,
        SecurityGroupIds=security_group_ids,
        UserData=user_data,
        IamInstanceProfile={
                'Name': 'role1'
            },
        TagSpecifications=[
        {"ResourceType": "instance", 
         "Tags": [{"Key": "Name", "Value": "app-tier-instance-" + str(instance_counts)},]}
    ],
    )
    apptier_ids.append(instance_id[0].id)

if __name__ == '__main__':
    app.run(debug=True)
