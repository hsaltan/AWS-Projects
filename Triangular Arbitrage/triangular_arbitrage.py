import boto3
import time
import json
import os

region = 'eu-west-1' # +1

### Create boto clients
s3_client = boto3.client('s3')
kds_client = boto3.client('kinesis')
s3 = boto3.resource('s3')
ssm_client = boto3.client('ssm')
ec2_client = boto3.client('ec2', region_name=region)
iam_client = boto3.client('iam')
sns_client = boto3.client('sns')
lambda_client = boto3.client('lambda', region_name=region)

### Create an SNS topic
response = sns_client.create_topic(
    Name='TriangularArbitrageNotification-Topic', # +1  
    Attributes={
        'DisplayName': 'Triangular Arbitrage Opportunity'
    },
    Tags=[
        {
            'Key': 'NAME', 
            'Value': 'Demo'
        },
    ]
)

topic_arn = response['TopicArn']

### Subscribe to the topic
sns_client.subscribe(
    TopicArn=topic_arn,
    Protocol='email',
    Endpoint='YOUR_EMAIL',
    ReturnSubscriptionArn=True
)

# >>> Confirm the subscription in 15 seconds>>>
time.sleep(15)

### Create an S3 bucket
bucket_name = "triangular-arbitrage-bucket" # +2

### Repository bucket for codes
s3_client.create_bucket(
    Bucket=bucket_name,
    CreateBucketConfiguration={
        'LocationConstraint': region, 
    },
)

### Block public access to the bucket 
s3_client.put_public_access_block(
    PublicAccessBlockConfiguration={
        'BlockPublicAcls': True,
        'IgnorePublicAcls': True,
        'BlockPublicPolicy': True,
        'RestrictPublicBuckets': True   
    },
    Bucket=bucket_name
)

### Create a folder
folder_name = "codes" # +3
s3_client.put_object(
    Bucket=bucket_name, 
    Key=(folder_name+'/')
)

folder_arn = "arn:aws:s3:::"+bucket_name+"/"+folder_name+"/*"

### Create a Kinesis data stream
stream_name = 'ExchangeRate-Stream' # +4
kds_client.create_stream(
    StreamName=stream_name,  
    ShardCount=1
)

time.sleep(5)

### Describe the data stream
response = kds_client.describe_stream(
    StreamName=stream_name
)

kinesis_info = response
kinesis_arn = kinesis_info['StreamDescription']['StreamARN']

### Define the parameters
var_currency = 'currency' # +5
var_investment = 'investmentAmount' # +6
var_commission = 'transactionCommission' # +7
var_kinesis = 'kinesisDataStream' # +8

# Define the currency parameter
ssm_client.put_parameter(
    Name=var_currency,    
    Description='currency of the investment funds',    
    Value='USD',    
    Type='String',   
    AllowedPattern='[A-Z]{3,3}',  
    Tags=[    
        {
            'Key': 'NAME',    
            'Value': 'currency'
        },
    ]
)

# Define the amount of investment
ssm_client.put_parameter(
    Name=var_investment,
    Description='investment amount',
    Value='1000000',
    Type='String',
    AllowedPattern='[1-9]{1,1}[0-9]{1,18}',
    Tags=[
        {
            'Key': 'NAME',
            'Value': 'amount'
        },
    ]
)

# Define the transaction commission
response = ssm_client.put_parameter(
    Name=var_commission,
    Description='transaction commission', 
    Value='0.0', 
    Type='String',
    AllowedPattern='[0-9]{1,3}[.][0-9]{1,5}',
    Tags=[
        {
            'Key': 'NAME',
            'Value': 'commission'
        },
    ]
)

# Define the Kinesis resource
response = ssm_client.put_parameter(
    Name=var_kinesis,
    Description='kinesis data stream for the project',
    Value=stream_name,
    Type='String',
    Tags=[
        {
            'Key': 'NAME',  
            'Value': 'kinesis data stream'
        },
    ]
)

### Get and assign the parameters
currency = ssm_client.get_parameter(Name=var_currency)['Parameter']['Value']
kinesisDataStream = ssm_client.get_parameter(Name=var_kinesis)['Parameter']['Value']
response = ssm_client.get_parameters(
    Names=[var_currency, var_kinesis, var_investment, var_commission]
)

set_of_parameters = response

print(set_of_parameters)

### Upload the data stream producer script to S3
path_1 = '/YOUR_PATH_TO_FILE/' # +9
file_1 = 'data_stream_producer.py' # +10
Key = folder_name + "/" + file_1
Body = path_1 + file_1
s3.meta.client.upload_file(Body, bucket_name, Key)

s3_client.put_object_tagging(
    Bucket=bucket_name,
    Key=Key,
    Tagging={
        'TagSet': [
            {
                'Key': 'NAME',   
                'Value': 'EC2 script'
            },
        ]
    },
)

### Create a key pair (if one doesn't exist) 
response = ec2_client.create_key_pair(
    KeyName='eu-west-1-KP',
)

key_info = response

### Saving the key pair to local disk
path_2 = '/YOUR_PATH_TO_KEY_PAIR/' # +11
key_name = key_info['KeyName']
fullName = os.path.join(path_2, key_name + ".pem")         
key_file = open(fullName, "w")
toFile = key_info['KeyMaterial']
key_file.write(toFile)
key_file.close()

# Change permission of the key file
os.chmod(fullName, 0o400)

### Create a security group (if one doesn't exist) 
response = ec2_client.create_security_group(
    Description='security group for the web scraper server',
    GroupName='ireland-sg-2',
    VpcId='YOUR_VPC_ID',
    TagSpecifications=[
        {
            'ResourceType': 'security-group',
            'Tags': [
                {
                    'Key': 'Name',       
                    'Value': 'ireland-sg-2'
                },
            ]
        }
    ]
)

group_id = response['GroupId']

### Modify the security group and add inbound rules
ec2_client.authorize_security_group_ingress(
    GroupId=group_id,
    IpPermissions=[  
        {'IpProtocol': 'tcp',
         'FromPort': 80,    
         'ToPort': 80,
         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        {'IpProtocol': 'tcp',
         'FromPort': 443,
         'ToPort': 443,
         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        {'IpProtocol': 'tcp',
         'FromPort': 22,
         'ToPort': 22,
         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
    ])

### Create a policy document for data stream producer
dict_producer_policy_document = { 
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "ec2i01",
          "Effect": "Allow",
          "Action": [
            "kinesis:DescribeStream",
            "kinesis:PutRecord",
            "kinesis:PutRecords",
            "kinesis:SubscribeToShard",
            "kinesis:DescribeStreamSummary",
            "kinesis:DescribeStreamConsumer",  
            "kinesis:RegisterStreamConsumer"
          ],
          "Resource": kinesis_arn
        },
        {
          "Sid": "ec2i02",
          "Effect": "Allow",
          "Action": [
            "s3:Get*",
            "s3:List*"
            ],
            "Resource": folder_arn
        },
        {
            "Sid": "ec2i03",
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:CancelCommand",
                "ssm:GetCommandInvocation",
                "ssm:ListCommandInvocations",
                "ssm:ListCommands",
                "ssm:SendCommand",
                "ssm:GetAutomationExecution",
                "ssm:GetParameters",
                "ssm:StartAutomationExecution",
                "ssm:ListTagsForResource",
                "ssm:GetCalendarState"                    
            ],
            "Resource": [set_of_parameters['Parameters'][0]['ARN'], set_of_parameters['Parameters'][2]['ARN'],
                        set_of_parameters['Parameters'][3]['ARN']]
        },      
    ]        
}

producer_policy_document = json.dumps(dict_producer_policy_document, indent = 4)

### Create a policy for the data stream producer role
response = iam_client.create_policy(
    PolicyName='DataStreamProducer-Policy', # +12
    PolicyDocument=producer_policy_document,
    Description="policy for sending stream data to Kinesis and uploading file from S3",
)

producer_policy_arn = response['Policy']['Arn']

### Create an assume role policy document for the producer (EC2)
dict_assume_role_policy_document={
    'Version': '2012-10-17',
    'Statement': [
        {
            'Effect': 'Allow',
            'Action': [
                'sts:AssumeRole'
            ],
            'Principal': {
                'Service': [
                    'ec2.amazonaws.com'
                ]
            }
        }
    ]
}

assume_role_policy_document = json.dumps(dict_assume_role_policy_document, indent = 4)

### Create a role for the producer
response = iam_client.create_role(
    Path='/',
    RoleName="EC2AccessKinesisAndS3-Role", # +13
    AssumeRolePolicyDocument = assume_role_policy_document,
    Description="EC2 access to Kinesis for sending stream data and to S3 for uploading file",
    Tags=[
        {
            'Key': 'NAME', 
            'Value': 'Kinesis-S3'
        },
    ]
)

producer_role_name = response['Role']['RoleName']

time.sleep(10)

### Attach the policy to the producer role
iam_client.attach_role_policy(
    PolicyArn=producer_policy_arn,
    RoleName=producer_role_name
)

### Create an instance profile
instance_profile_name = 'ExchangeRateProducerServer' # +14
response = iam_client.create_instance_profile(   
    InstanceProfileName=instance_profile_name,
)
instance_profile_arn = response['InstanceProfile']['Arn']

### Attach the producer role to the instance profile
iam_client.add_role_to_instance_profile(
    InstanceProfileName=instance_profile_name,
    RoleName=producer_role_name
)

### Create a policy document for data stream consumer - Lambda evaluator
dict_consumer_policy_document = {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "lmbd11",
          "Effect": "Allow",
          "Action": [
            "kinesis:DescribeStream",
            "kinesis:GetRecords",
            "kinesis:GetShardIterator"
          ],
          "Resource": kinesis_arn
        },    
        {
            "Sid": "lmbd12",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetObject"
            ],
            "Resource": folder_arn
        },
        {
            "Sid": "lmbd13",
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData"
            ],
            "Resource": [
                "*"
            ]        
        },
        {
            "Sid": "lmbd14",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": [
                "*"
            ]
        },
        {
            "Sid":"lmbd15",
            "Effect":"Allow",
            "Action":"sns:Publish",
            "Resource":topic_arn
        },
        {
            "Sid": "lmbd16",
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:CancelCommand",
                "ssm:GetCommandInvocation",
                "ssm:ListCommandInvocations",
                "ssm:ListCommands",
                "ssm:SendCommand",
                "ssm:GetAutomationExecution",
                "ssm:GetParameters",
                "ssm:StartAutomationExecution",
                "ssm:ListTagsForResource",
                "ssm:GetCalendarState"                    
            ],
            "Resource": [set_of_parameters['Parameters'][0]['ARN'], set_of_parameters['Parameters'][1]['ARN'],
                        set_of_parameters['Parameters'][3]['ARN']]
        },         
        {
            "Sid": "lmbd17",
            "Effect": "Allow",
            "Action": [
                "kms:Decrypt"
            ],
            "Resource": "*"
        }          
      ]
}
          
consumer_policy_document = json.dumps(dict_consumer_policy_document, indent = 4)

### Create a policy for the data stream consumer role
response = iam_client.create_policy( 
    PolicyName='DataStreamConsumer-Policy', # +15
    PolicyDocument=consumer_policy_document,
    Description="policy for receiving stream data from kinesis, accessing S3 and publishing to SNS",
)

consumer_policy_arn = response['Policy']['Arn']

time.sleep(10)

### Create an assume role policy document for the consumer (Lambda)
dict_assume_role_policy_document_for_lambda={
    'Version': '2012-10-17',
    'Statement': [
        {
            'Effect': 'Allow',
            'Action': [
                'sts:AssumeRole'
            ],
            'Principal': {
                'Service': [
                    'lambda.amazonaws.com'
                ]
            }
        }
    ]
}

assume_role_policy_document_for_lambda = json.dumps(dict_assume_role_policy_document_for_lambda, indent = 4)

### Create a role for the consumer
response = iam_client.create_role(
    RoleName="LambdaAccessKinesisAndS3-Role", # +16
    AssumeRolePolicyDocument = assume_role_policy_document_for_lambda,
    Description="Lambda access to Kinesis for receiving stream data, to S3 for deploying file, and to SNS for publishing messages",
    Tags=[
        {
            'Key': 'NAME',    
            'Value': 'Kinesis-S3-SNS'
        },
    ]
)

consumer_role_name = response['Role']['RoleName']
consumer_role_arn = response['Role']['Arn']

time.sleep(10)

### Attach the policy to the consumer role
response = iam_client.attach_role_policy(
    PolicyArn=consumer_policy_arn,
    RoleName=consumer_role_name
)

### Zip the lambda_function.py file
command = "zip my-deployment-package.zip lambda_function.py" # +17
os.system(command)

### Upload the data stream consumer script (lambda_function) to S3
file_lambda_upload = "my-deployment-package.zip" # +18
Key = folder_name + "/" + file_lambda_upload
Body = path_1 + file_lambda_upload
s3.meta.client.upload_file(Body, bucket_name, Key)

s3_client.put_object_tagging(
    Bucket=bucket_name,
    Key=Key,
    Tagging={ 
        'TagSet': [
            {
                'Key': 'NAME',          
                'Value': 'Lambda script'
            },
        ]
    },
)

### Create Lambda function
s3_key = folder_name + "/" + file_lambda_upload
function_name = 'triangular_arbitrage_lambda_function' # +19

response = lambda_client.create_function(
    Code={
        'S3Bucket': bucket_name,
        'S3Key': s3_key,
    },
    Description='Evaluate exchange rates anomalies for triangular arbitrage',
    Environment={ 
        'Variables': { 
            'topicArn': topic_arn
        },
    },
    FunctionName=function_name,
    Handler='lambda_function.calculate_arbitrage',
    MemorySize=128,
    Publish=True,
    Role=consumer_role_arn,
    Runtime='python3.7',
    Tags={
        'NAME': 'lambda evaluator',
    },
    Timeout=15,
    TracingConfig={
        'Mode': 'PassThrough',
    },
)

function_arn = response['FunctionArn']

### Launch an EC2 instance

userDataScript = """#!/bin/bash
sudo su
yum install python3-pip -y
pip3 install boto3
pip3 install beautifulsoup4
pip3 install selenium
cd /tmp/
wget https://chromedriver.storage.googleapis.com/87.0.4280.88/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
mv chromedriver /usr/bin/chromedriver
curl https://intoli.com/install-google-chrome.sh | bash
mv /usr/bin/google-chrome-stable /usr/bin/google-chrome
cd /
mkdir scripts
cd scripts
aws s3 cp s3://triangular-arbitrage-bucket/codes/data_stream_producer.py /scripts/data_stream_producer.py
python3 data_stream_producer.py"""

response = ec2_client.run_instances(
    BlockDeviceMappings=[
        {
            'DeviceName': '/dev/sdh',
            'Ebs': {
                'VolumeSize': 8,
                'DeleteOnTermination': True,
                'VolumeType': 'gp2',
            },
        },
    ],
    
    ImageId='ami-01720b5f421cf0179',
    InstanceType='t2.micro',
    KeyName=key_info['KeyName'],
    MaxCount=1,
    MinCount=1,
    SecurityGroupIds=[
        group_id,
    ],
    Placement={
        'Tenancy': 'default'
    },
    UserData = userDataScript,
    Monitoring={
        'Enabled': False
    },    
    DisableApiTermination=False,
    InstanceInitiatedShutdownBehavior='stop',
    CreditSpecification={
        'CpuCredits': 'standard'
    },
    EbsOptimized=False,
    IamInstanceProfile={
        'Name': instance_profile_name
    },
    CapacityReservationSpecification={
        'CapacityReservationPreference': 'open'
    },
    TagSpecifications=[
        {
            'ResourceType': 'instance',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': 'data-stream-producer-server',
                },
            ],
        },
    ],
)

time.sleep(60)

### Create a trigger
lambda_client.create_event_source_mapping(
    EventSourceArn=kinesis_arn,
    FunctionName=function_arn,
    Enabled=True,
    BatchSize=100,
    StartingPosition='LATEST'
)
