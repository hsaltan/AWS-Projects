import sys
sys.path.insert(1, '/scripts')
import os
import boto3
from colorama import Fore, Back, Style
import inquire as inq
import time
import base64
import snoop



s3 = boto3.resource('s3')


# Get the list of enabled regions and their long names
def describe_regions():
    response = boto3.client('ec2').describe_regions()
    enabled_regions = response['Regions']
    regions = []
    for enabled_region in enabled_regions:
        regions.append(enabled_region['RegionName'])
    return regions


# Create an S3 bucket
def create_bucket(bucketName, region, blockPublicAcls=True, ignorePublicAcls=True,
                    blockPublicPolicy=True, restrictPublicBuckets=True):

    # Repository bucket for codes and files
    boto3.client('s3', region_name=region).create_bucket(
        ACL='private',
        Bucket=bucketName,
        CreateBucketConfiguration={
            'LocationConstraint': region, 
        },
    )

    # Block public access to the bucket 
    boto3.client('s3', region_name=region).put_public_access_block(
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': blockPublicAcls,
            'IgnorePublicAcls': ignorePublicAcls,
            'BlockPublicPolicy': blockPublicPolicy,
            'RestrictPublicBuckets': restrictPublicBuckets
        },
        Bucket=bucketName
    )
    print(f"{Fore.MAGENTA}Bucket{Style.RESET_ALL} {Fore.CYAN}{bucketName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')

# List objects in a bucket
def list_objects(bucketName, region):
    response = boto3.client('s3', region_name=region).list_objects(
        Bucket=bucketName,
    )
    contents = response['Contents']
    return contents


# Delete objects in a bucket
def delete_objects(bucketName, objectToDelete, region):
    response = boto3.client('s3', region_name=region).delete_objects(
        Bucket=bucketName,
        Delete={
            'Objects': [
                {
                    'Key': objectToDelete,
                },
            ],
        },
    )
    deletedObject = response['Deleted'][0]['Key']
    print(f"{Fore.MAGENTA}Object{Style.RESET_ALL} {Fore.CYAN}{deletedObject}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Delete an S3 bucket
def delete_bucket(bucketName, region):
    try: 
        contents = list_objects(bucketName, region)
    except:
        contents = None
    if contents:
        for content in contents:
            objectToDelete = content['Key']
            delete_objects(bucketName, objectToDelete, region)
    boto3.client('s3', region_name=region).delete_bucket(
        Bucket=bucketName,
    )
    print(f"{Fore.MAGENTA}Bucket and objects inside the bucket{Style.RESET_ALL} {Fore.CYAN}{bucketName}{Style.RESET_ALL} {Fore.MAGENTA}have been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a policy
def create_policy(policyName, policyDocument, policyDescription, region):
    response = boto3.client('iam', region_name=region).create_policy(
        PolicyName=policyName,
        PolicyDocument=policyDocument,
        Description=policyDescription,
    )
    policyARN = response['Policy']['Arn']
    return policyARN


# Delete a role
def delete_policy(policyARN, policyName, region):
    boto3.client('iam', region_name=region).delete_policy(
        PolicyArn=policyARN
    )
    print(f"{Fore.MAGENTA}IAM policy{Style.RESET_ALL} {Fore.CYAN}{policyName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a role
def create_role(roleName, rolePolicyDocument, roleDescription, key, value, region):
    response = boto3.client('iam', region_name=region).create_role(
    RoleName=roleName,
    AssumeRolePolicyDocument = rolePolicyDocument,
    Description=roleDescription,
    Tags=[
        {
            'Key': key,
            'Value': value
        },
    ]
)
    roleName = response['Role']['RoleName']
    roleARN = response['Role']['Arn']
    print(f"{Fore.MAGENTA}Role{Style.RESET_ALL} {Fore.CYAN}{roleName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    time.sleep(10)
    return roleName, roleARN


# Delete a role
def delete_role(roleName, region):
    boto3.client('iam', region_name=region).delete_role(
        RoleName=roleName
    )
    print(f"{Fore.MAGENTA}IAM role{Style.RESET_ALL} {Fore.CYAN}{roleName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Attach a policy to a role
def attach_policy(policyARN, roleName, region):
    boto3.client('iam', region_name=region).attach_role_policy(
        PolicyArn=policyARN,
        RoleName=roleName
    )
    time.sleep(5)


# Create a ECS service-linked role
def create_service_linked_role(awsServiceName, serviceRoleDescription, region):
    response = boto3.client('iam', region_name=region).create_service_linked_role(
        AWSServiceName=awsServiceName,
        Description=serviceRoleDescription,
        # CustomSuffix=customSuffix
    )
    serviceLinkedRoleARN = response['Role']['Arn']
    print(f"{Fore.MAGENTA}A service-linked role as{Style.RESET_ALL} {Fore.CYAN}{awsServiceName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    time.sleep(10)
    return serviceLinkedRoleARN


# Get the account ID of a user
def get_account_auth_details(userName, region):
    response = boto3.client('iam', region_name=region).get_account_authorization_details(
        Filter=[
            'User',
        ],
    )
    userARN = [x for x in response['UserDetailList'] if x['UserName'] == userName][0]['Arn']
    accountID = userARN[13:25]
    return userARN, accountID


# Put an object in S3 bucket
def put_object(body, bucketName, fileName, key, value, region):
    s3.meta.client.upload_file(body, bucketName, fileName)
    boto3.client('s3', region_name=region).put_object_tagging(
        Bucket=bucketName,
        Key=fileName,
        Tagging={
            'TagSet': [
                {
                    'Key': key,
                    'Value': value
                },
            ]
        },
    )
    print(f"{Fore.MAGENTA}File(s) has/have been uploaded to bucket{Style.RESET_ALL} {Fore.CYAN}{bucketName}{Style.RESET_ALL}")
    print('\n')


# Enable static web hosting of S3 bucket
def configure_bucket_website(bucketName, indexDocument, region):
    boto3.client('s3', region_name = region).put_bucket_website(
        Bucket=bucketName,
        WebsiteConfiguration={
            'IndexDocument': {
                'Suffix': indexDocument
            },
        }
    )


# Redirect request to another bucket
def redirect_request(bucketName, hostName, protocol, region):
    boto3.client('s3', region_name = region).put_bucket_website(
        Bucket=bucketName,
        WebsiteConfiguration={
            'RedirectAllRequestsTo': {
                'HostName': hostName,
                'Protocol': protocol
            }
        }
    )


# Put a bucket policy to a bucket
def put_bucket_policy(bucketName, s3BucketPolicyDocument, region):
    boto3.client('s3', region_name = region).put_bucket_policy(
        Bucket=bucketName,
        ConfirmRemoveSelfBucketAccess=True,
        Policy=s3BucketPolicyDocument,
    )


# Describe the existing security groups based on filter values
def describe_security_groups(filterName, filterValue, region):
    response = boto3.client('ec2', region_name = region).describe_security_groups(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterValue
                ]
            },
        ],
    )
    security_groups = response['SecurityGroups']
    defaultSecurityGroupID = [x['GroupId'] for x in security_groups if x['GroupName'] == 'default'][0]
    return security_groups, defaultSecurityGroupID


# Create a security group
def create_sg(description, sgName, vpcID, resourceSG, sgKey, sgValue, region):
    response = boto3.client('ec2', region_name = region).create_security_group(
        Description=description,
        GroupName=sgName,
        VpcId=vpcID,
        TagSpecifications=[
            {
                'ResourceType': resourceSG,
                'Tags': [
                    {
                        'Key': sgKey,
                        'Value': sgValue
                    },
                ]
            },
        ],
    )
    sgID = response['GroupId']
    return sgID


# Delete a security group
def delete_sg(sgID, region):
    boto3.client('ec2', region_name = region).delete_security_group(
        GroupId=sgID,
    )
    print(f"{Fore.MAGENTA}Security group{Style.RESET_ALL} {Fore.CYAN}{sgID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a security group ingress rule
def create_sg_ingress_rule_1(sgID, port, ipProtocol, cidrIP, sgDescription, region):
    boto3.client('ec2', region_name = region).authorize_security_group_ingress(
        GroupId=sgID,
        IpPermissions=[
            {
                'FromPort': port,
                'IpProtocol': ipProtocol,
                'IpRanges': [
                    {
                        'CidrIp': cidrIP,
                        'Description': sgDescription,
                    },
                ],
                'ToPort': port,
            },
        ],
    )


# Create a security group ingress rule from another security group
def create_sg_ingress_rule_2(privateSgID, defaultSgID, port, ipProtocol, cidrIP, sgDescription, region):
    boto3.client('ec2', region_name = region).authorize_security_group_ingress(
        GroupId=privateSgID, 
        IpPermissions=[
            {
                'IpProtocol': ipProtocol, 
                'FromPort': port, 
                'ToPort': port, 
                'UserIdGroupPairs': [
                    {
                        'Description': sgDescription,
                        'GroupId': defaultSgID 
                    }
                ]
            }
        ],
    )


# Create a security group egress rule
def create_sg_egress_rule_1(sgID, port, ipProtocol, cidrIP, sgDescription, region):
    boto3.client('ec2', region_name = region).authorize_security_group_egress(
    GroupId=sgID,
    IpPermissions=[
        {
            'FromPort': port,
            'IpProtocol': ipProtocol,
            'IpRanges': [
                {
                    'CidrIp': cidrIP,
                    'Description': sgDescription,
                },
            ],
            'ToPort': port,
        },
    ],
)


# Create a security group egress rule from prefix list
def create_sg_egress_rule_2(sgID, port, ipProtocol, sgDescription, prefixListID, region):
    boto3.client('ec2', region_name = region).authorize_security_group_egress(
        GroupId=sgID,
        IpPermissions=[
            {
                'FromPort': port,
                'IpProtocol': ipProtocol,
                'PrefixListIds': [
                    {
                        'Description': sgDescription,
                        'PrefixListId': prefixListID
                    },
                ],
                'ToPort': port,
            },
        ],
    )


# Create an instance profile
def create_instance_profile(instanceProfileName, region):
    response = boto3.client('iam', region_name=region).create_instance_profile(
        InstanceProfileName=instanceProfileName,
    )
    instanceProfileARN = response['InstanceProfile']['Arn']
    return instanceProfileARN


# Attach a role to the instance profile
def attach_role_to_instance_profile(roleName, instanceProfileName, region):
    boto3.client('iam', region_name=region).add_role_to_instance_profile(
        InstanceProfileName=instanceProfileName,
        RoleName=roleName
    )


# Delete instance profile
def delete_instance_profile(instanceProfileName, roleName, region):
    try:
        boto3.client('iam', region_name=region).remove_role_from_instance_profile(
            InstanceProfileName=instanceProfileName,
            RoleName=roleName
        )
    except:
        pass
    boto3.client('iam', region_name=region).delete_instance_profile(
        InstanceProfileName=instanceProfileName
    )
    print(f"{Fore.MAGENTA}Instance profile{Style.RESET_ALL} {Fore.CYAN}{instanceProfileName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Launch an EC2 instance
def launch_ec2_instance(volumeSize, volumeType, ami, instanceType, keyName, maxCount,
                        minCount, sgID, subnetID, userDataScript, instanceName,
                        instanceProfileName, key, value, region):
    response = boto3.client('ec2', region_name = region).run_instances(
        BlockDeviceMappings=[
            {
                'DeviceName': '/dev/xvda',
                'Ebs': {
                    'VolumeSize': volumeSize,
                    'DeleteOnTermination': True,
                    'VolumeType': volumeType,
                },
            },
        ],
        ImageId=ami,
        InstanceType=instanceType,
        KeyName=keyName,
        MaxCount=maxCount,
        MinCount=minCount,
        Placement={
            'Tenancy': 'default'
        },
        UserData=userDataScript,
        Monitoring={
            'Enabled': False
        },

        DisableApiTermination=False,
        InstanceInitiatedShutdownBehavior='stop',
        NetworkInterfaces=[
        {
            'AssociatePublicIpAddress': True,
            'DeviceIndex': 0,
            'Groups': [
                sgID
            ],
            'SubnetId': subnetID,
        },
        ],
#        CreditSpecification={
#            'CpuCredits': 'standard'
#        },
        EbsOptimized=False,
        IamInstanceProfile={
            'Name': instanceProfileName
        },
        CapacityReservationSpecification={
            'CapacityReservationPreference': 'open'
        },
        TagSpecifications=[
            {
                'ResourceType': 'instance', 
                'Tags': [
                    {
                        'Key': key,
                        'Value': value,
                    },
                ],
            },
            {
                'ResourceType': 'volume', 
                'Tags': [
                    {
                        'Key': key,
                        'Value': value,
                    },
                ],
            },
            {
                'ResourceType': 'network-interface', 
                'Tags': [
                    {
                        'Key': key,
                        'Value': value,
                    },
                ],
            },
        ],
    )
    instance = response['Instances'][0]
    instanceID = instance['InstanceId']
    return instanceID


# Terminate an EC2 instance
def terminate_ec2_instance(instance_ids, region):
    boto3.client('ec2', region_name = region).terminate_instances(
        InstanceIds=instance_ids
    )
    time.sleep(25)
    print(f"{Fore.MAGENTA}EC2 instance{Style.RESET_ALL} {Fore.CYAN}{instance_ids}{Style.RESET_ALL} {Fore.MAGENTA}has been terminated.{Style.RESET_ALL}")
    print('\n')


# Describe the instance status
def describe_instance_status(instanceID, region):
    print(f"{Fore.MAGENTA}[INFO] Waiting for instance status check to report ok for{Style.RESET_ALL} {Fore.CYAN}{instanceID}{Style.RESET_ALL}")
    print('\n')
    instanceStatuses = "null"
    while True:
        response = boto3.client('ec2', region_name = region).describe_instance_status(
            InstanceIds=[
                instanceID,
            ],
        )
        instanceStatuses = response['InstanceStatuses']
        if len(instanceStatuses) == 0:
            print(f"{Fore.MAGENTA}Instance status information is not available yet{Style.RESET_ALL}")
            time.sleep(10)
            continue
        instanceStatus = response['InstanceStatuses'][0]['InstanceStatus']['Status']
        print(f"{Fore.MAGENTA}[INFO] Polling to get status of the instance{Style.RESET_ALL} {Fore.CYAN}{instanceStatus}{Style.RESET_ALL}")
        if instanceStatus == 'ok':
           break
        time.sleep(15)
    print('\n')
    return instanceStatus


# Describe EC2 instances
def describe_instance(instanceID, region):
    response = boto3.client('ec2', region_name = region).describe_instances(
        Filters=[
            {
                'Name': 'instance-id',
                'Values': [
                    instanceID,
                ]
            },
        ],
    )
    instanceInfo = response
    return instanceInfo


# SSH connect to the instance launched
def ssh_connect(instanceID, hostname, completeName):
    print(f"{Fore.MAGENTA}You are now connecting to the instance{Style.RESET_ALL} {Fore.CYAN}{instanceID}{Style.RESET_ALL}")
    print('\n')
    os.system('clear')
    command = "ssh -i " + completeName + " " + hostname
    os.system(command)


# List all SSM documents owned by an account owner
def list_owned_ssm_documents(key, value, region):
    response = boto3.client('ssm', region_name=region).list_documents(
        DocumentFilterList=[
            {
                'key': key,
                'value': value
            },
        ],
    )
    documents = response['DocumentIdentifiers']
    return documents


# Describe the SSM documents selected by the account owner
def describe_ssm_documents(selected_documents, region):
    for selected_document in selected_documents:
        response = boto3.client('ssm', region_name=region).describe_document(
            Name=selected_document,
        )
        print(response)
        print('\n')


# Create an SSM json document 
def create_ssm_document_local():
    message =  f"{Fore.MAGENTA}Choose one of the following courses of action: {Style.RESET_ALL}"
    name = "document_creation"
    options = ["a. I want to create the document here by entering line by line", 
                "b. I've already created the document and want to load it"]
    method = inq.define_list(name, message, options)
    print('\n')
    selected_files = []
    if method[0] == "a":
        documentPath = input(f"{Fore.MAGENTA}Enter the file path where the document(s) will be saved on the local machine, e.g. /main_dir/sub_dir/sub_dir2/.../: {Style.RESET_ALL}")
        print('\n')
        res = "Y"
        while res == "Y":
            documentName = input(f"{Fore.MAGENTA}Enter the document name without extension: {Style.RESET_ALL}")
            print('\n')
            fileName = documentPath + documentName + ".json"
            documentFile = open(fileName, "a")
            row = "begin"
            print(f"{Fore.MAGENTA}Enter the document content line by line and type 'end' to end the entry: {Style.RESET_ALL}")
            print('\n')
            while row != 'end':
                row = input()
                rowData = row + "\n"
                documentFile.write(rowData)
            documentFile.close()
            selected_files.append((fileName, documentName))
            res = input(f"{Fore.MAGENTA}Do we need to create another document (Y/n)?: {Style.RESET_ALL}")
    elif method[0] == "b":
        documentPath = input(f"{Fore.MAGENTA}Enter the file path where the document is saved on the local machine, e.g. /main_dir/sub_dir/sub_dir2/.../: {Style.RESET_ALL}")
        print('\n')
        filesInDirectory = os.listdir(documentPath)
        files = []
        for f in filesInDirectory:
            files.append(f)
        if '.DS_Store' in files:
            files.remove('.DS_Store')
        name = "documents_to_load"
        message = f"{Fore.MAGENTA}Select the relevant SSM documents to load{Style.RESET_ALL}"
        chosen_files = inq.define_checkbox(name, message, files)
        print('\n')
        for chosen_file in chosen_files:
            fileName = documentPath + chosen_file
            documentName = chosen_file.replace(".json", "")
            selected_files.append((fileName, documentName))
    return selected_files


# Create a Systems Manager document
def create_document_api(docFilePath, docName, documentType, documentFormat, region):
    with open(docFilePath) as openFile:
        documentContent = openFile.read()
        response = boto3.client('ssm', region_name=region).create_document(
            Content = documentContent,
            Name = docName,
            VersionName='1.0',
            DocumentType = documentType,
            DocumentFormat = documentFormat,
        )
        resDescription = response['DocumentDescription']
        documentName = resDescription['Name']
    return documentName


# Create a parameter in the Parameter Store
def create_parameter(parameterName, parameterDescription, parameterValue, parameterType,
                            key, value, region):
    boto3.client('ssm', region_name=region).put_parameter(
        Name=parameterName,
        Description=parameterDescription,
        Value=parameterValue,
        Type=parameterType,
        Tags=[
            {
                'Key': key,
                'Value': value
            },
        ]
    )


# Delete a parameter in the Parameter Store
def delete_parameter(parameterName, region):
    boto3.client('ssm', region_name=region).delete_parameter(
        Name=parameterName
    )
    print(f"{Fore.MAGENTA}Parameter{Style.RESET_ALL} {Fore.CYAN}{parameterName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Get a parameter from the Parameter Store
def get_parameter(parameterName, region, withDecryption=True):
    response = boto3.client('ssm', region_name=region).get_parameter(
        Name=parameterName,
        WithDecryption=withDecryption
    )
    parameterValue = response['Parameter']['Value']
    return parameterValue


# Runs commands with parameters on one or more managed instances 
def send_parameter_ssm_commands(instanceID, document, command, seconds, region):
    response = boto3.client('ssm', region_name=region).send_command(
        InstanceIds=[
            instanceID,
        ],
        DocumentName=document,
        DocumentVersion='$LATEST',
        TimeoutSeconds=300,
        Comment='run Command document',
            Parameters={
            'commands': [
                command
            ]
        },
    )
    CommandID = response['Command']['CommandId']
    time.sleep(seconds)
    output = boto3.client('ssm', region_name=region).get_command_invocation(
        CommandId=CommandID,
        InstanceId=instanceID,
        )
    status = output['Status']
    return status


# Runs commands without parameters on one or more managed instances 
def send_ssm_run_commands(instanceID, document, region):
    response = boto3.client('ssm', region_name=region).send_command(
        InstanceIds=[
            instanceID,
        ],
        DocumentName=document,
        DocumentVersion='$LATEST',
        TimeoutSeconds=300,
        Comment='run Command document',
        CloudWatchOutputConfig={
            'CloudWatchOutputEnabled': True
        }
    )
    status = response['Command']['Status']
    return status


# Create an RDS instance
def create_rds(dbName, dbInstanceIdentifier, allocatedStorage, dbInstanceClass, engine, masterUsername, 
                masterUserPassword, vpcSecurityGroupId, availabilityZone, preferredMaintenanceWindow,
                backupRetentionPeriod, key, value, maxAllocatedStorage, region):
    response = boto3.client('rds', region_name=region).create_db_instance(
        DBName=dbName,
        DBInstanceIdentifier=dbInstanceIdentifier,
        AllocatedStorage=allocatedStorage,
        DBInstanceClass=dbInstanceClass,
        Engine=engine,
        MasterUsername=masterUsername,
        MasterUserPassword=masterUserPassword,
        VpcSecurityGroupIds=vpcSecurityGroupId,
        AvailabilityZone=availabilityZone,
        PreferredMaintenanceWindow=preferredMaintenanceWindow,
        BackupRetentionPeriod=backupRetentionPeriod,
        MultiAZ=False,
        #EngineVersion='string',
        PubliclyAccessible=True,
        Tags=[
            {
                'Key': key,
                'Value': value
            },
        ],
        StorageType='gp2',
        EnablePerformanceInsights=False,
        MaxAllocatedStorage=maxAllocatedStorage
    )
    dbInstanceIdentifier = response['DBInstance']['DBInstanceIdentifier']


# Add role to the RDs instance
def add_role_to_rds(dbInstanceIdentifier, roleARN, featureName, region):
    boto3.client('rds', region_name=region).add_role_to_db_instance(
        DBInstanceIdentifier=dbInstanceIdentifier,
        RoleArn=roleARN,
        FeatureName=featureName
    )


# Describe an RDS instance
def describe_rds(dbInstanceIdentifier, region):
    response = boto3.client('rds', region_name=region).describe_db_instances(
        DBInstanceIdentifier=dbInstanceIdentifier
    )

    db_instances = response['DBInstances']
    endpoint = db_instances[0]['Endpoint']['Address']
    port = db_instances[0]['Endpoint']['Port']
    usr = db_instances[0]['MasterUsername']
    dbName = db_instances[0]['DBName']
    return endpoint, port, usr, dbName


# Amazon Comprehend detect sentiment
def detect_sentiment(text, region, language='en'):
    response = boto3.client('comprehend', region_name=region).detect_sentiment(
        Text=text,
        LanguageCode=language
    )
    sentimentScore = response['SentimentScore']
    positive = sentimentScore['Positive']
    negative = sentimentScore['Negative']
    neutral = sentimentScore['Neutral']
    mixed = sentimentScore['Mixed']
    return positive, negative, neutral, mixed


# Create a Cloud9 environment
def create_cloud9_environment(name, description, instanceType, subnetID, key, value, region):
    response = boto3.client('cloud9', region_name=region).create_environment_ec2(
        name=name,
        description=description,
        instanceType=instanceType,
        subnetId=subnetID,
        automaticStopTimeMinutes=30,
        tags=[
            {
                'Key': key,
                'Value': value
            },
        ],
        connectionType='CONNECT_SSH'
    )
    environmentID = response['environmentId']
    return environmentID


# Describe VPCs
def describe_vpcs_1(region):
    response = boto3.client('ec2', region_name=region).describe_vpcs()
    vpc_response = response['Vpcs']
    return vpc_response


def describe_vpcs_2(filterName, filterValue, region):
    response = boto3.client('ec2', region_name = region).describe_vpcs(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterValue,
                ]
            },
        ],
    )
    vpcs_response = response['Vpcs']
    return vpcs_response


# Create a VPC
def create_vpc(cidrBlock, resourceVPC, vpcKey, vpcName, region):
    response = boto3.client('ec2', region_name=region).create_vpc(
        CidrBlock=cidrBlock,
        AmazonProvidedIpv6CidrBlock=False,
        InstanceTenancy='default',
        TagSpecifications=[
            {
                'ResourceType': resourceVPC,
                'Tags': [
                    {
                        'Key': vpcKey,
                        'Value': vpcName
                    },
                ]
            },
        ]
    )
    vpc_response = response
    vpcID = vpc_response['Vpc']['VpcId']
    response = boto3.client('ec2', region_name=region).modify_vpc_attribute(
        EnableDnsHostnames={
            'Value': True
        },
        VpcId=vpcID
    )
    print(f"{Fore.MAGENTA}VPC{Style.RESET_ALL} {Fore.CYAN}{vpcName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return vpcID


# Delete VPC
def delete_vpc(vpcID, vpcName, region):
    boto3.client('ec2', region_name=region).delete_vpc(
        VpcId=vpcID,
    )
    print(f"{Fore.MAGENTA}VPC{Style.RESET_ALL} {Fore.CYAN}{vpcName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create an internet gateway
def create_igw(resourceIGW, igwKey, igwName, region):
    response = boto3.client('ec2', region_name = region).create_internet_gateway(
        TagSpecifications=[
            {
                'ResourceType': resourceIGW,
                'Tags': [
                    {
                        'Key': igwKey,
                        'Value': igwName
                    },
                ]
            },
        ],
    )
    igwID = response['InternetGateway']['InternetGatewayId']
    print(f"{Fore.MAGENTA}Internet gateway{Style.RESET_ALL} {Fore.CYAN}{igwName}{Style.RESET_ALL} {Fore.MAGENTA}has been created and attached to the VPC.{Style.RESET_ALL}")
    print('\n')

    return igwID


# Describe the internet gateway
def describe_igw(filterName, filterValue, region):
    response = boto3.client('ec2', region_name = region).describe_internet_gateways(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterValue,
                ]
            },
        ],
    )
    igwID = response['InternetGateways'][0]['InternetGatewayId']
    return igwID


# Attach the internet gateway
def attach_igw(vpcID, igwID, region):
    boto3.client('ec2', region_name = region).attach_internet_gateway(
        InternetGatewayId=igwID,
        VpcId=vpcID
    )


# Detach internet gateway
def detach_igw(vpcID, igwID, region):
    boto3.client('ec2', region_name = region).detach_internet_gateway(
        InternetGatewayId=igwID,
        VpcId=vpcID
    )


# Delete internet gateway
def delete_igw(igwID, region):
    boto3.client('ec2', region_name = region).delete_internet_gateway(
        InternetGatewayId=igwID,
    )
    print(f"{Fore.MAGENTA}Internet gateway{Style.RESET_ALL} {Fore.CYAN}{igwID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Identify the main route table
def describe_main_rt(rtKey, vpcID, region):
    response = boto3.client('ec2', region_name = region).describe_route_tables(
        Filters=[
            {
                'Name': rtKey,
                'Values': [
                    vpcID,
                ]
            },
        ],
    )
    mainRouteTableID = response['RouteTables'][0]['RouteTableId']
    return mainRouteTableID


# Describe route tables
def describe_route_tables(filterName, filterValue, region):
    response = boto3.client('ec2', region_name = region).describe_route_tables(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterValue,
                ]
            },
        ],
    )
    route_tables = response['RouteTables']
    return route_tables


# Describe prefix lists
def describe_prefix_list(region):
    response = boto3.client('ec2', region_name = region).describe_prefix_lists()
    prefix_lists = response['PrefixLists']
    return prefix_lists


# Create a route table
def create_rt(vpcID, resourceRt, rtKey, rtValue, region):
    response = boto3.client('ec2', region_name = region).create_route_table(
        VpcId=vpcID,
        TagSpecifications=[
            {
                'ResourceType': resourceRt,
                'Tags': [
                    {
                        'Key': rtKey,
                        'Value': rtValue
                    },
                ]
            },
        ]
    )
    routeTableID = response['RouteTable']['RouteTableId']
    return routeTableID


# Associate the route table with a subnet
def associate_rt(routeTableID, subnetID, region):
    response = boto3.client('ec2', region_name = region).associate_route_table(
        RouteTableId=routeTableID,
        SubnetId=subnetID
    )
    associationID = response['AssociationId']
    return associationID


# Delete route table
def delete_rt(rtID, region):
    boto3.client('ec2', region_name = region).delete_route_table(
        RouteTableId=rtID,
    )
    print(f"{Fore.MAGENTA}Route table{Style.RESET_ALL} {Fore.CYAN}{rtID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Open the main route table to the internet traffic
def open_internet_route(destinationCidrBlock, destinationIpv6CidrBlock, igwID, mainRouteTableID, region):
    boto3.client('ec2', region_name = region).create_route(
        DestinationCidrBlock=destinationCidrBlock,
        GatewayId=igwID,
        RouteTableId=mainRouteTableID,
    )
    boto3.client('ec2', region_name = region).create_route(
        DestinationIpv6CidrBlock=destinationIpv6CidrBlock,
        GatewayId=igwID,
        RouteTableId=mainRouteTableID,
    )


# Create routes for the selected targets
def create_ngw_rt_routes(rtID, ipv4_list, natGatewayId, region):
    for ipv4 in ipv4_list:
        boto3.client('ec2', region_name = region).create_route(
            DestinationCidrBlock=ipv4,
            NatGatewayId=natGatewayId,
            RouteTableId=rtID,
        )


# Describe network access control lists
def describe_network_acls(filterName, filterValue, region):
    response = boto3.client('ec2', region_name = region).describe_network_acls(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterValue
                ]
            },
        ],
    )
    network_acls = response['NetworkAcls']
    existing_nacls = {}
    for network_acl in network_acls:
        associations = []
        networkACLID = network_acl['NetworkAclId']
        naclAssociations = network_acl['Associations'] 
        for naclAssociation in naclAssociations: 
            networkACLAssociationID = naclAssociation['NetworkAclAssociationId']
            subnetID = naclAssociation['SubnetId']
            associations.append((networkACLAssociationID, subnetID))
        existing_nacls[networkACLID] = associations
    return network_acls, existing_nacls


# Create a network access control list
def create_nacl(vpcID, resourceNacl, naclKey, naclName, region):
    response = boto3.client('ec2', region_name = region).create_network_acl(
        VpcId=vpcID,
        TagSpecifications=[
            {
                'ResourceType': resourceNacl,
                'Tags': [
                    {
                        'Key': naclKey,
                        'Value': naclName
                    },
                ]
            },
        ]
    )
    naclID = response['NetworkAcl']['NetworkAclId']
    print(f"{Fore.MAGENTA}Network access control list{Style.RESET_ALL} {Fore.CYAN}{naclName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')

    return naclID


# Delete a network access control list
def delete_nacl(naclID, region):
    boto3.client('ec2', region_name = region).delete_network_acl(
        NetworkAclId=naclID
    )
    print(f"{Fore.MAGENTA}Network access control list{Style.RESET_ALL} {Fore.CYAN}{naclID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Associate a nacl with a subnet
def associate_nacl(naclID, associationID, region):
    boto3.client('ec2', region_name = region).replace_network_acl_association(
        AssociationId=associationID,
        NetworkAclId=naclID
    )


# Replace a nacl association with another
def replace_nacl_association(naclID, naclAssociation, region):
    boto3.client('ec2', region_name = region).replace_network_acl_association(
        AssociationId=naclAssociation,
        NetworkAclId=naclID
    )


# Create a network access control list rule
def create_nacl_rule(naclName, cidrBlock, egress, naclID, port, protocol, ruleAction, ruleNumber, region):
    boto3.client('ec2', region_name = region).create_network_acl_entry(
        CidrBlock=cidrBlock,
        Egress=egress,
        NetworkAclId=naclID,
        PortRange={
            'From': port,
            'To': port
        },
        Protocol=protocol,
        RuleAction=ruleAction,
        RuleNumber=ruleNumber
    )
    print(f"{Fore.MAGENTA}Network access control list{Style.RESET_ALL} {Fore.CYAN}{naclName}{Style.RESET_ALL} {Fore.MAGENTA}rule has been defined for traffic from the VPC.{Style.RESET_ALL}")
    print('\n')

# Describe availability zones in a region
def describe_availability_zones(region):
    response = boto3.client('ec2', region_name = region).describe_availability_zones(
        AllAvailabilityZones=True,
    )    
    availabilityZones = response['AvailabilityZones']
    availability_zones = []
    for availabilityZone in availabilityZones:
        zoneName = availabilityZone['ZoneName']
        availability_zones.append(zoneName)
    return availability_zones


# Create a subnet
def create_subnet(subnetResource, subnetKey, subnetValue, available_zone, subnetCidrBlock, vpcID, region):
    response = boto3.client('ec2', region_name = region).create_subnet(
        TagSpecifications=[
            {
                'ResourceType': subnetResource,
                'Tags': [
                    {
                        'Key': subnetKey,
                        'Value': subnetValue
                    },
                ]
            },
        ],
        AvailabilityZone=available_zone,
        CidrBlock=subnetCidrBlock,
        VpcId=vpcID,
    )
    subnetID = response['Subnet']['SubnetId']
    return subnetID


# Describe subnets
def describe_subnets(filterName, filterValue, region):
    response = boto3.client('ec2', region_name=region).describe_subnets(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterValue,
                ]
            },
        ],
    )
    subnet_response = response['Subnets']
    return subnet_response


# Delete subnets
def delete_subnets(subnetID, region):
    boto3.client('ec2', region_name=region).delete_subnet(
        SubnetId=subnetID,
    )
    print(f"{Fore.MAGENTA}Subnet{Style.RESET_ALL} {Fore.CYAN}{subnetID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Allocate an elastic IP address
def allocate_eip(eipName, region):
    response = boto3.client('ec2', region_name = region).allocate_address(
        Domain='vpc',
    )
    allocationID = response['AllocationId']

    # Tag the elastic IP address
    response = boto3.client('ec2', region_name = region).create_tags(
        Resources=[
            allocationID,
        ],
        Tags=[
            {
                'Key': 'Name',
                'Value': eipName
            },
        ]
    )
    return allocationID


# Release elastic IP address
def release_eip(allocationID, region):
    boto3.client('ec2', region_name = region).release_address(
        AllocationId=allocationID,
    )
    print(f"{Fore.MAGENTA}Elastic IP address{Style.RESET_ALL} {Fore.CYAN}{allocationID}{Style.RESET_ALL} {Fore.MAGENTA}has been released.{Style.RESET_ALL}")
    print('\n')


# Create a nat gateway
def create_ngw(sequenceNo, vpcName, subnetID, resourceNGW, ngwKey, ngwValue, region):
    eipName = vpcName + ".eip-" + str(sequenceNo)
    allocationID = allocate_eip(eipName, region)
    response = boto3.client('ec2', region_name = region).create_nat_gateway(
        AllocationId=allocationID,
        SubnetId=subnetID,
        TagSpecifications=[
            {
                'ResourceType': resourceNGW,
                'Tags': [
                    {
                        'Key': ngwKey,
                        'Value': ngwValue
                    },
                ]
            },
        ]
    )
    ngwID = response['NatGateway']['NatGatewayId']
    return ngwID, allocationID


# Describe nat gateway
def describe_ngw(filterName, filterValue, number, region):
    response = boto3.client('ec2', region_name = region).describe_nat_gateways(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterValue,
                ]
            },
        ],
    )
    state = response['NatGateways'][number]['State']
    return state


# Delete nat gateway
def delete_ngw(ngwID, region):
    response = boto3.client('ec2', region_name = region).delete_nat_gateway(
        NatGatewayId=ngwID
    )
    natGatewayID = response['NatGatewayId']
    print(f"{Fore.MAGENTA}Nat gateway{Style.RESET_ALL} {Fore.CYAN}{natGatewayID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a VPC gateway endpoint
def create_vpc_gtw_endpoint(vpcID, vpcEndpointType, serviceName, policyDocument, rtID, 
                            resourceVpcEndpoint, vpceKey, vpceValue, region):
    response = boto3.client('ec2', region_name = region).create_vpc_endpoint(
        VpcEndpointType=vpcEndpointType,
        VpcId=vpcID,
        ServiceName=serviceName,
        PolicyDocument=policyDocument,
        RouteTableIds=rtID,
        TagSpecifications=[
            {
                'ResourceType': resourceVpcEndpoint,
                'Tags': [
                    {
                        'Key': vpceKey,
                        'Value': vpceValue
                    },
                ]
            },
        ]
    )
    vpcEndpointID = response['VpcEndpoint']['VpcEndpointId']
    return vpcEndpointID


# Delete a VPC gateway endpoint
def delete_vpc_gtw_endpoint(vpcEndpointID, region):
    response = boto3.client('ec2', region_name = region).delete_vpc_endpoints(
        VpcEndpointIds=[
            vpcEndpointID,
        ]
    )
    if response['Unsuccessful']:
        print(f"{Fore.RED}{response['Unsuccessful']['Error']['Message']}{Style.RESET_ALL}")
    else:
        print(f"{Fore.MAGENTA}VPC endpoint{Style.RESET_ALL} {Fore.CYAN}{vpcEndpointID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create An AWS CloudWatch logs group
def create_cloudwatch_log_group(logGroupName, key, value, region):
    boto3.client('logs', region_name=region).create_log_group(
        logGroupName=logGroupName,
        tags={
            key: value
        }
    )
    print(f"{Fore.MAGENTA}CloudWatch logs group{Style.RESET_ALL} {Fore.CYAN}{logGroupName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    time.sleep(3)


# Create An AWS CloudWatch logs group
def delete_cloudwatch_log_group(logGroupName, region):
    boto3.client('logs', region_name=region).delete_log_group(
        logGroupName=logGroupName
    )
    print(f"{Fore.MAGENTA}Cloudwatch log group{Style.RESET_ALL} {Fore.CYAN}{logGroupName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a repository on ECR
def create_ecr_repo(repoName, repoKey, repoValue, region):
    ecr_response = boto3.client('ecr', region_name=region).create_repository(
        repositoryName=repoName,
        tags=[
            {
                'Key': repoKey,
                'Value': repoValue
            },
        ],
        encryptionConfiguration={
            'encryptionType': 'AES256',
        }
    )
    time.sleep(3)
    repoRegistryID = ecr_response['repository']['registryId']
    repoUri = ecr_response['repository']['repositoryUri']
    print(f"{Fore.MAGENTA}ECR repository{Style.RESET_ALL} {Fore.CYAN}{repoName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return repoRegistryID, repoUri


# Delete a repository on ECR
def delete_ecr_repo(repoName, region):
    response = boto3.client('ecr', region_name=region).delete_repository(
        repositoryName=repoName,
    )
    repositoryName = response['repository']['repositoryName']
    print(f"{Fore.MAGENTA}ECR repository{Style.RESET_ALL} {Fore.CYAN}{repositoryName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Login to ECR
def get_authorization(repoRegistryID, region):
    response = boto3.client('ecr', region_name=region).get_authorization_token(
        registryIds=[
            repoRegistryID,
        ]
    )
    authData = response['authorizationData'][0]
    ecrPassword = (base64.b64decode(authData['authorizationToken']).replace(b'AWS:', b'').decode('utf-8'))
    ecrURL = authData['proxyEndpoint']
    ecrUsername = 'AWS'
    expires = response['authorizationData'][0]['expiresAt']
    print('\n')
    print(f"{Fore.MAGENTA}Authentication token expires at{Style.RESET_ALL} {Fore.CYAN}{expires}{Style.RESET_ALL}")
    print('\n')
    return ecrUsername, ecrPassword, ecrURL, expires


# Create a ECS cluster
def create_ecs_cluster(clusterName, region):
    cluster_response = boto3.client('ecs', region_name=region).create_cluster(
        clusterName=clusterName,
    )
    clusterARN = cluster_response['cluster']['clusterArn']
    clusterStatus = cluster_response['cluster']['status']
    print(f"{Fore.MAGENTA}ECS cluster{Style.RESET_ALL} {Fore.CYAN}{clusterName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    time.sleep(3)
    return clusterARN, clusterStatus


# Delete a ECS cluster
def delete_ecs_cluster(clusterARN, region):
    response = boto3.client('ecs', region_name=region).delete_cluster(
        cluster=clusterARN
    )
    clusterName = response['cluster']['clusterName']
    print(f"{Fore.MAGENTA}ECS cluster{Style.RESET_ALL} {Fore.CYAN}{clusterName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Register a task definition
def register_task_definition(taskDefinitionName, taskRoleARN, executionRoleARN,
                            networkMode, containerName, ecrRepoName, containerPort,
                            protocol, logGroupName, awslogsStreamPrefix, hostType,
                            cpu, memory, ecsKey, ecsValue, region):
    response = boto3.client('ecs', region_name=region).register_task_definition(
        family=taskDefinitionName,
        taskRoleArn=taskRoleARN,
        executionRoleArn=executionRoleARN,
        networkMode=networkMode,
        containerDefinitions=[
            {
                'name': containerName,
                'image': ecrRepoName,
                'portMappings': [
                    {
                        'containerPort': containerPort,
                        'protocol': protocol
                    },
                ],
                'essential': True,
                'logConfiguration': {
                    'logDriver': 'awslogs',
                    'options': {
                    "awslogs-group": logGroupName,
                    "awslogs-region": region,
                    "awslogs-stream-prefix": awslogsStreamPrefix
                    },
                },
            },
        ],
        requiresCompatibilities=[
            hostType,
        ],
        cpu=cpu,
        memory=memory,
        tags=[
            {
                'key': ecsKey,
                'value': ecsValue
            },
        ],
    )
    taskDefinitionARN = response['taskDefinition']['taskDefinitionArn']
    print(f"{Fore.MAGENTA}Task definition{Style.RESET_ALL} {Fore.CYAN}{taskDefinitionName}{Style.RESET_ALL} {Fore.MAGENTA}has been registered.{Style.RESET_ALL}")
    print('\n')
    time.sleep(3)
    return taskDefinitionARN


# List tasks
def list_tasks(clusterName, serviceName, launchType, region, desiredStatus='RUNNING'):
    response = boto3.client('ecs', region_name=region).list_tasks(
        cluster=clusterName,
        serviceName=serviceName,
        desiredStatus=desiredStatus,
        launchType=launchType
    )
    taskARNs = response['taskArns']
    print(f"{Fore.MAGENTA}Tasks in service{Style.RESET_ALL} {Fore.CYAN}{serviceName}{Style.RESET_ALL} {Fore.MAGENTA}are:{Style.RESET_ALL} {Fore.CYAN}{taskARNs}{Style.RESET_ALL}")
    print('\n')
    return taskARNs


# Stop a task
def stop_task(clusterName, taskID, region):
    boto3.client('ecs', region_name=region).stop_task(
        cluster=clusterName,
        task=taskID,
    )
    print(f"{Fore.MAGENTA}Task{Style.RESET_ALL} {Fore.CYAN}{taskID}{Style.RESET_ALL} {Fore.MAGENTA}has been stopped.{Style.RESET_ALL}")
    print('\n')


# Deregister a task definition
def deregister_task_definition(taskDefinitionARN, region):
    response = boto3.client('ecs', region_name=region).deregister_task_definition(
        taskDefinition=taskDefinitionARN
    )
    taskDefinition = response['taskDefinition']['taskDefinitionArn']
    print(f"{Fore.MAGENTA}Task definition{Style.RESET_ALL} {Fore.CYAN}{taskDefinition}{Style.RESET_ALL} {Fore.MAGENTA}has been deregistered.{Style.RESET_ALL}")
    print('\n')


# Create a ECS service
def create_service(clusterName, serviceName, taskDefinitionName, tgARN,
                                containerName, containerPort, desiredCount, launchType,
                                maximumPercent, minimumHealthyPercent, private_subnet_ids, 
                                SgID, assignPublicIp, healthCheckGracePeriodSeconds, 
                                serviceKey, serviceValue, region):
    response = boto3.client('ecs', region_name=region).create_service(
        cluster=clusterName,
        serviceName=serviceName,
        taskDefinition=taskDefinitionName,
        loadBalancers=[
            {
                'targetGroupArn': tgARN,
                'containerName': containerName,
                'containerPort': containerPort
            },
        ],
        desiredCount=desiredCount,
        launchType=launchType,
        deploymentConfiguration={
            'maximumPercent': maximumPercent,
            'minimumHealthyPercent': minimumHealthyPercent
        },
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': private_subnet_ids,
                'securityGroups': [
                    SgID
                ],
                'assignPublicIp': assignPublicIp
            }
        },
        healthCheckGracePeriodSeconds=healthCheckGracePeriodSeconds,
        tags=[
            {
                'key': serviceKey,
                'value': serviceValue
            },
        ],
    )
    serviceARN = response['service']['serviceArn']
    print(f"{Fore.MAGENTA}ECS service{Style.RESET_ALL} {Fore.CYAN}{serviceName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    time.sleep(3)

    return serviceARN


# Create a ECS service
def delete_service(clusterName, serviceName, region):
    response = boto3.client('ecs', region_name=region).delete_service(
        cluster=clusterName,
        service=serviceName,
    )
    ecsServiceName = response['service']['serviceName']
    print(f"{Fore.MAGENTA}ECS service{Style.RESET_ALL} {Fore.CYAN}{ecsServiceName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a load balancer
def create_load_balancer(nlbName, subnet_ids, scheme, elbKey, elbValue, elbType, region):
    response = boto3.client('elbv2', region_name=region).create_load_balancer(
        Name=nlbName,
        Subnets=subnet_ids,
        # SecurityGroups=[
        #     sgID,
        # ],
        Scheme=scheme,
        Tags=[
            {
                'Key': elbKey,
                'Value': elbValue
            },
        ],
        Type=elbType,
        IpAddressType='ipv4'
    )
    loadBalancerARN = response['LoadBalancers'][0]['LoadBalancerArn']
    dnsName = response['LoadBalancers'][0]['DNSName']
    print(f"{Fore.MAGENTA}Network load balancer{Style.RESET_ALL} {Fore.CYAN}{nlbName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    time.sleep(10)

    return loadBalancerARN, dnsName


# Delete a load balancer
def delete_load_balancer(loadBalancerName, loadBalancerARN, region):
    boto3.client('elbv2', region_name=region).delete_load_balancer(
        LoadBalancerArn=loadBalancerARN
    )
    print(f"{Fore.MAGENTA}Load balancer{Style.RESET_ALL} {Fore.CYAN}{loadBalancerName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a target group
def create_target_group(targetGroupName, protocol, port, vpcID, healthCheckProtocol,
                        healthCheckPath, healthCheckIntervalSeconds, healthCheckTimeoutSeconds,
                        healthyThresholdCount, unhealthyThresholdCount, targetType, region):
    response = boto3.client('elbv2', region_name=region).create_target_group(
        Name=targetGroupName,
        Protocol=protocol,
        Port=port,
        VpcId=vpcID,
        HealthCheckProtocol=healthCheckProtocol,
        HealthCheckEnabled=True,
        HealthCheckPath=healthCheckPath,
        HealthCheckIntervalSeconds=healthCheckIntervalSeconds,
        HealthCheckTimeoutSeconds=healthCheckTimeoutSeconds,
        HealthyThresholdCount=healthyThresholdCount,
        UnhealthyThresholdCount=unhealthyThresholdCount,
        TargetType=targetType,
        # Tags=[
        #     {
        #         'Key': key,
        #         'Value': value
        #     },
        # ]
    )
    tgARN = response['TargetGroups'][0]['TargetGroupArn']
    print(f"{Fore.MAGENTA}Target group{Style.RESET_ALL} {Fore.CYAN}{targetGroupName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    time.sleep(3)
    return tgARN


# Delete a target group
def delete_target_group(targetGroupName, targetGroupARN, region):
    boto3.client('elbv2', region_name=region).delete_target_group(
        TargetGroupArn=targetGroupARN
    )
    print(f"{Fore.MAGENTA}Target group{Style.RESET_ALL} {Fore.CYAN}{targetGroupName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a target group listener
def create_listener(loadBalancerARN, protocol, port, listenerType, tgARN, region):
    response = boto3.client('elbv2', region_name=region).create_listener(
        LoadBalancerArn=loadBalancerARN,
        Protocol=protocol,
        Port=port,
        DefaultActions=[
            {
                'Type': listenerType,
                'ForwardConfig': {
                    'TargetGroups': [
                        {
                            'TargetGroupArn': tgARN,
                            # 'Weight': weight
                        },
                    ],
                }
            },
        ],
        # Tags=[
        #     {
        #         'Key': listenerKey,
        #         'Value': listenerValue
        #     },
        # ]
    )
    listenerARN = response['Listeners'][0]['ListenerArn']
    print(f"{Fore.MAGENTA}Target group listener on port{Style.RESET_ALL} {Fore.CYAN}{port}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    time.sleep(3)    
    return listenerARN


# Change the name of an AWS resource
def create_tags(resourceID, resourceKey, resourceName, region):
    boto3.client('ec2', region_name = region).create_tags(
        Resources=[
            resourceID,
        ],
        Tags=[
            {
                'Key': resourceKey,
                'Value': resourceName
            },
        ]
    )


# Create a secret
def create_secret(secretName, secretDescription, secretString, secretKey, secretValue, region):
    response = boto3.client('secretsmanager', region_name=region).create_secret(
        Name=secretName,
        Description=secretDescription,
        SecretString=secretString,
        Tags=[
            {
                'Key': secretKey,
                'Value': secretValue
            },
        ],
    )
    secretARN = response['ARN']
    print(f"{Fore.MAGENTA}Secret{Style.RESET_ALL} {Fore.CYAN}{secretName}{Style.RESET_ALL} {Fore.MAGENTA}has been created in Secrets Manager.{Style.RESET_ALL}")
    print('\n')
    return secretARN


# Delete a secret
def delete_secret(secretARN, region, forceDeleteWithoutRecovery=True):
    response = boto3.client('secretsmanager', region_name=region).delete_secret(
        SecretId=secretARN,
        ForceDeleteWithoutRecovery=forceDeleteWithoutRecovery
    )
    secretName = response['Name']
    print(f"{Fore.MAGENTA}Secret{Style.RESET_ALL} {Fore.CYAN}{secretName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Retrieve a secret
def retrieve_secret(secretARN, region):
    response = boto3.client('secretsmanager', region_name=region).get_secret_value(
        SecretId=secretARN
    )
    if 'SecretString' in response:
        secret = response['SecretString']
    else:
        secret = base64.b64decode(response['SecretBinary'])
    return secret


# Create a CodeCommit Repository
def create_code_commit_repo(codeCommitRepoName, codeCommitRepoDescription, ccKey, ccValue, region):
    response = boto3.client('codecommit', region_name=region).create_repository(
        repositoryName=codeCommitRepoName,
        repositoryDescription=codeCommitRepoDescription,
        tags={
            ccKey: ccValue
        }
    )
    codeCommitID = response['repositoryMetadata']['repositoryId']
    codeCommitARN = response['repositoryMetadata']['Arn']
    print(f"{Fore.MAGENTA}CodeCommit repository{Style.RESET_ALL} {Fore.CYAN}{codeCommitRepoName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')

    return codeCommitID, codeCommitARN


# Delete a CodeCommit Repository
def delete_code_commit_repo(codeCommitRepoName, region):
    boto3.client('codecommit', region_name=region).delete_repository(
        repositoryName=codeCommitRepoName
    )
    print(f"{Fore.MAGENTA}CodeCommit repository{Style.RESET_ALL} {Fore.CYAN}{codeCommitRepoName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a CodeBuild Project
def create_code_build_project(codeBuildName, codeBuildDescription, sourceType,
              sourceLocation, artifactsType, cacheType, environmentType, image,
              computeType, environmentVariable1, environmentVariable2, privilegedMode,
              codeBuildRoleARN, cbKey, cbValue, vpcID, subnets, security_groups, region):
    response = boto3.client('codebuild', region_name=region).create_project(
        name=codeBuildName,
        description=codeBuildDescription,
        source={
            'type': sourceType,
            'location': sourceLocation,
        },
        artifacts={
            'type': artifactsType,
        },
        cache={
            'type': cacheType,
        },
        environment={
            'type': environmentType,
            'image': image,
            'computeType': computeType,
            'environmentVariables': [
                {
                    'name': environmentVariable1['name'],
                    'value': environmentVariable1['value'],
                    'type': environmentVariable1['type']
                },
                {
                    'name': environmentVariable2['name'],
                    'value': environmentVariable2['value'],
                    'type': environmentVariable2['type']
                },
            ],
            'privilegedMode': privilegedMode,
        },
        serviceRole=codeBuildRoleARN,
        tags=[
            {
                'key': cbKey,
                'value': cbValue
            },
        ],
        vpcConfig={
            'vpcId': vpcID,
            'subnets': subnets,
            'securityGroupIds': security_groups
        },
    )
    projectARN = response['project']['arn']
    print(f"{Fore.MAGENTA}CodeBuild project{Style.RESET_ALL} {Fore.CYAN}{codeBuildName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return projectARN


# Delete a CodeBuild Project
def delete_code_build_project(codeBuildName, region):
    boto3.client('codebuild', region_name=region).delete_project(
        name=codeBuildName
    )
    print(f"{Fore.MAGENTA}CodeBuild project{Style.RESET_ALL} {Fore.CYAN}{codeBuildName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a CodePipeline Pipeline
def create_codepipeline_pipeline(codePipelineName, codePipelineRoleARN, bucketName, 
                                  codeCommitRepoName, sourceOutputArtifactsName,
                                  buildOutputArtifactName, codeBuildName, clusterName, 
                                  serviceName, key, value, region):
    boto3.client('codepipeline', region_name=region).create_pipeline(
        pipeline={
            'name': codePipelineName,
            'roleArn': codePipelineRoleARN,
            'artifactStore': {
                'type': 'S3',
                'location': bucketName,
            },
            'stages': [
                {
                    'name': 'Source',
                    'actions': [
                        {
                            'name': 'Source',
                            'actionTypeId': {
                                'category': 'Source',
                                'owner': 'AWS',
                                'provider': 'CodeCommit',
                                'version': '1'
                            },
                            'runOrder': 1,
                            'configuration': {
                                'BranchName': 'master',
                                'RepositoryName': codeCommitRepoName
                            },
                            'outputArtifacts': [
                                {
                                    'name': sourceOutputArtifactsName
                                },
                            ],
                            'inputArtifacts': [

                            ],
                        },
                    ]
                },
                {
                    'name': 'Build',
                    'actions': [
                        {
                            'name': 'Build',
                            'actionTypeId': {
                                'category': 'Build',
                                'owner': 'AWS',
                                'provider': 'CodeBuild',
                                'version': '1'
                            },
                            'runOrder': 1,
                            'configuration': {
                                'ProjectName': codeBuildName
                            },
                            'outputArtifacts': [
                                {
                                    'name': buildOutputArtifactName
                                },
                            ],
                            'inputArtifacts': [
                                {
                                    'name': sourceOutputArtifactsName
                                },
                            ],
                        },
                    ]
                },
                {
                    'name': 'Deploy',
                    'actions': [
                        {
                            'name': 'Deploy',
                            'actionTypeId': {
                                'category': 'Deploy',
                                'owner': 'AWS',
                                'provider': 'ECS',
                                'version': '1'
                            },
                            'configuration': {
                                'ClusterName': clusterName,
                                'ServiceName': serviceName,
                                'FileName': 'imagedefinitions.json'
                            },
                            'inputArtifacts': [
                                {
                                    'name': buildOutputArtifactName
                                },
                            ],
                        },
                    ]
                },
            ],
        },
        tags=[
            {
                'key': key,
                'value': value
            },
        ]
    )
    print(f"{Fore.MAGENTA}CodePipeline Pipeline{Style.RESET_ALL} {Fore.CYAN}{codePipelineName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')


# Delete a CodePipeline Pipeline
def delete_codepipeline_pipeline(codePipelineName, region):
    boto3.client('codepipeline', region_name=region).delete_pipeline(
        name=codePipelineName
    )
    print(f"{Fore.MAGENTA}CodePipeline pipeline{Style.RESET_ALL} {Fore.CYAN}{codePipelineName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a CodeCommit commit - NOT WORKING UNDER CONSIDERATION
def create_commit(ccRepoName, branchName, parentCommitID, authorName, authorEmail,
                    commitMessage, targetFilePath, fileMode, fileContent, region, isMove=False):
    cc_response = boto3.client('codecommit', region_name=region).create_commit(
        repositoryName=ccRepoName,
        branchName=branchName,
        parentCommitId=parentCommitID,
        authorName=authorName,
        email=authorEmail,
        commitMessage=commitMessage,
        putFiles=[
            {
                'filePath': targetFilePath,
                'fileMode': fileMode,
                'sourceFile': {
                    'filePath': fileContent,
                    'isMove': isMove
                }
            },
        ],
    )
    commitID = cc_response['commitId']
    treeId = cc_response['treeId']
    return commitID, treeId


# Create a DynamoDB table
def create_dynamodb_table(tableName, readCapacityUnits, writeCapacityUnits, attributes, keyTypes, 
                            projectionTypes, globalSecondaryIndexName1, globalSecondaryIndexName2, 
                            billingMode, ddbKey, ddbValue, region, streamEnabled=False, 
                            sseSpecification=False):
    response = boto3.client('dynamodb', region_name=region).create_table(
        AttributeDefinitions=attributes,
        TableName=tableName,
        KeySchema=[
            {
                'AttributeName': attributes[0]['AttributeName'],
                'KeyType': keyTypes[0]
            }
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': globalSecondaryIndexName1,
                'KeySchema': [
                    {
                        'AttributeName': attributes[1]['AttributeName'],
                        'KeyType': keyTypes[0]
                    },
                    {
                    "AttributeName": attributes[0]['AttributeName'],
                    "KeyType": keyTypes[1]
                    }
                ],
                'Projection': {
                    'ProjectionType': projectionTypes[2],
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': readCapacityUnits,
                    'WriteCapacityUnits': writeCapacityUnits
                }
            },
            {
                'IndexName': globalSecondaryIndexName2,
                'KeySchema': [
                    {
                        'AttributeName': attributes[2]['AttributeName'],
                        'KeyType': keyTypes[0]
                    },
                    {
                    "AttributeName": attributes[0]['AttributeName'],
                    "KeyType": keyTypes[1]
                    }
                ],
                'Projection': {
                    'ProjectionType': projectionTypes[2]
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': readCapacityUnits,
                    'WriteCapacityUnits': writeCapacityUnits
                }
            }
        ],
        BillingMode=billingMode,
        ProvisionedThroughput={
            'ReadCapacityUnits': readCapacityUnits,
            'WriteCapacityUnits': writeCapacityUnits
        },
        StreamSpecification={
            'StreamEnabled': streamEnabled
            # 'StreamViewType': 'NEW_IMAGE'|'OLD_IMAGE'|'NEW_AND_OLD_IMAGES'|'KEYS_ONLY'
        },
        SSESpecification={
            'Enabled': sseSpecification
            # 'SSEType': 'AES256'|'KMS',
            # 'KMSMasterKeyId': 'string'
        },
        Tags=[
            {
                'Key': ddbKey,
                'Value': ddbValue
            }
        ]
    )

    tableARN = response['TableDescription']['TableArn']
    tableID = response['TableDescription']['TableId']
    print(f"{Fore.MAGENTA}DynamoDB table{Style.RESET_ALL} {Fore.CYAN}{tableName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return tableARN, tableID


# Delete a DynamoDB table
def delete_dynamodb_table(tableName, region):
    response = boto3.client('dynamodb', region_name=region).delete_table(
        TableName=tableName
    )
    dydbTableName = response['TableDescription']['TableName']
    print(f"{Fore.MAGENTA}DynamoDB table{Style.RESET_ALL} {Fore.CYAN}{dydbTableName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Describe DynamoDB table
def describe_dynamodb_table(tableName, region):
    response = boto3.client('dynamodb', region_name=region).describe_table(
        TableName=tableName
    )
    dynamodb_table_info = response['Table']
    return dynamodb_table_info


# Describe DynamoDB table status
def describe_dynamodb_table_status(tableName, region):
    print(f"{Fore.MAGENTA}[INFO] Waiting for table status check to report ok for{Style.RESET_ALL} {Fore.CYAN}{tableName}{Style.RESET_ALL}")
    print('\n')
    tableStatus = "null"
    while True:
        dynamodb_table_info = describe_dynamodb_table(tableName, region)
        tableStatus = dynamodb_table_info['TableStatus']
        if tableStatus != 'ACTIVE':
            print(f"{Fore.MAGENTA}Table status information is not available yet{Style.RESET_ALL}")
            time.sleep(5)
            continue
        print(f"{Fore.MAGENTA}[INFO] Polling to get status of the table{Style.RESET_ALL} {Fore.CYAN}{tableStatus}{Style.RESET_ALL}")
        if tableStatus == 'ACTIVE':
           break
    print('\n')


# Batch write into the DynamoDB table
# The BatchWriteItem operation puts or deletes multiple items in one or more tables. 
# A single call to BatchWriteItem can write up to 16 MB of data, which can comprise as many as 
# 25 put or delete requests. Individual items to be written can be as large as 400 KB.
def dynamodb_batch_put_request(tableName, putRequestFile, region):
    response = boto3.client('dynamodb', region_name=region).batch_write_item(
        RequestItems=putRequestFile
    )
    if response['UnprocessedItems']:
        unprocessed_items = response['UnprocessedItems'][tableName]
        print(f"{Fore.MAGENTA}The following are unprocessed items: {Style.RESET_ALL}")
        for item in unprocessed_items:
            element = item['PutRequest']['Item']
            print(f"{Fore.RED}{element}{Style.RESET_ALL}")
            print('\n')
    else:
        print(f"{Fore.MAGENTA}All items have been successfully written to the table{Style.RESET_ALL} {Fore.CYAN}{tableName}.{Style.RESET_ALL}")
        print('\n')


# Create Cognito user pool
def create_cognito_user_pool(poolName, password_policy, autoVerifiedAttribute, usernameAttribute, 
                            emailVerificationMessage, emailVerificationSubject, emailSendingAccount,
                            userPoolKey, userPoolValue, advancedSecurityMode, recoveryMechanismName, 
                            region):
    response = boto3.client('cognito-idp', region_name=region).create_user_pool(
        PoolName=poolName,
        Policies={
            'PasswordPolicy': {
                'MinimumLength': password_policy['MinimumLength'],
                'RequireUppercase': password_policy['RequireUppercase'],
                'RequireLowercase': password_policy['RequireLowercase'],
                'RequireNumbers': password_policy['RequireNumbers'],
                'RequireSymbols': password_policy['RequireSymbols'],
                'TemporaryPasswordValidityDays': password_policy['TemporaryPasswordValidityDays']
            }
        },
        AutoVerifiedAttributes=[
            autoVerifiedAttribute,
        ],
        UsernameAttributes=[
            usernameAttribute,
        ],
        # SmsVerificationMessage='string',
        EmailVerificationMessage=emailVerificationMessage,
        EmailVerificationSubject=emailVerificationSubject,
        # VerificationMessageTemplate={
        #     'SmsMessage': 'string',
        #     'EmailMessage': emailMessage,
        #     'EmailSubject': emailSubject,
        #     'EmailMessageByLink': emailMessageByLink,
        #     'EmailSubjectByLink': 'string',
        #     'DefaultEmailOption': defaultEmailOption
        # },
        # SmsAuthenticationMessage='string',
        EmailConfiguration={
            # 'SourceArn': 'string',
            # 'ReplyToEmailAddress': 'string',
            'EmailSendingAccount': emailSendingAccount,
            # 'From': 'string',
            # 'ConfigurationSet': 'string'
        },
        UserPoolTags={
            userPoolKey: userPoolValue
        },
        UserPoolAddOns={
            'AdvancedSecurityMode': advancedSecurityMode
        },
        UsernameConfiguration={
            'CaseSensitive': False
        },
        AccountRecoverySetting={
            'RecoveryMechanisms': [
                {
                    'Priority': 1,
                    'Name': recoveryMechanismName
                },
            ]
        }
    )
    userPoolName = response['UserPool']['Name']
    userPoolID = response['UserPool']['Id']
    print(f"{Fore.MAGENTA}Cognito user pool{Style.RESET_ALL} {Fore.CYAN}{userPoolName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return userPoolName, userPoolID


# Delete Cognito user pool
def delete_cognito_user_pool(userPoolName, userPoolID, region):
    boto3.client('cognito-idp', region_name=region).delete_user_pool(
        UserPoolId=userPoolID
    )
    print(f"{Fore.MAGENTA}Cognito user pool{Style.RESET_ALL} {Fore.CYAN}{userPoolName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create Cognito user pool client
def create_cognito_user_pool_client(clientName, userPoolID, region):
    response = boto3.client('cognito-idp', region_name=region).create_user_pool_client(
        UserPoolId=userPoolID,
        ClientName=clientName,
    )
    clientName = response['UserPoolClient']['ClientName']
    clientID = response['UserPoolClient']['ClientId']
    print(f"{Fore.MAGENTA}Cognito user pool client{Style.RESET_ALL} {Fore.CYAN}{clientName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return clientName, clientID


# Delete Cognito user pool client
def delete_cognito_user_pool_client(userPoolID, clientName, clientID, region):
    boto3.client('cognito-idp', region_name=region).delete_user_pool_client(
        UserPoolId=userPoolID,
        ClientId=clientID
    )
    print(f"{Fore.MAGENTA}Cognito user pool client{Style.RESET_ALL} {Fore.CYAN}{clientName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create VPC link
def create_vpc_link(vpcLinkName, vpcLinkDescription, targetARN, vpcLinkKey, vpcLinkValue, region):
    response = boto3.client('apigateway', region_name=region).create_vpc_link(
        name=vpcLinkName,
        description=vpcLinkDescription,
        targetArns=[
            targetARN,
        ],
        tags={
            vpcLinkKey: vpcLinkValue
        }
    )
    time.sleep(5)
    VPCLinkID = response['id']
    VPCLinkName = response['name']
    print(f"{Fore.MAGENTA}VPC link{Style.RESET_ALL} {Fore.CYAN}{VPCLinkName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return VPCLinkName, VPCLinkID


# Delete VPC link
def delete_vpc_link(vpcLinkName, VPCLinkID, region):
    boto3.client('apigateway', region_name=region).delete_vpc_link(
        vpcLinkId=VPCLinkID
    )
    print(f"{Fore.MAGENTA}VPC link{Style.RESET_ALL} {Fore.CYAN}{vpcLinkName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a new API from an external API definition file
def import_rest_api(parameterKey, parameterValue, body, region, failOnWarnings=True):
    response = boto3.client('apigateway', region_name=region).import_rest_api(
        failOnWarnings=failOnWarnings,
        parameters={
            parameterKey: parameterValue
        },
        body=body
    )
    apiID = response['id']
    apiName = response['name']
    print(f"{Fore.MAGENTA}API{Style.RESET_ALL} {Fore.CYAN}{apiName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return apiID


# Delete REST API
def delete_rest_api(restAPIID, stageName, region):
    boto3.client('apigateway', region_name=region).delete_stage(
        restApiId=restAPIID,
        stageName=stageName
    )
    print(f"{Fore.MAGENTA}REST API{Style.RESET_ALL} {Fore.CYAN}{restAPIID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Creates a Deployment resource, which makes a specified RestApi callable over the internet.
def create_api_deployment(restAPIID, stageName, stageDescription, region):
    response = boto3.client('apigateway', region_name=region).create_deployment(
        restApiId=restAPIID,
        stageName=stageName,
        stageDescription=stageDescription,
    )
    deploymentID = response['id']
    print(f"{Fore.MAGENTA}Deployment resource{Style.RESET_ALL} {Fore.CYAN}{deploymentID}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return deploymentID


# Delete deployment resource
def delete_api_deployment(restAPIID, deploymentID, region):
    boto3.client('apigateway', region_name=region).delete_deployment(
        restApiId=restAPIID,
        deploymentId=deploymentID
    )
    print(f"{Fore.MAGENTA}Deployment resource{Style.RESET_ALL} {Fore.CYAN}{deploymentID}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create a public hosted zone
def create_public_hosted_zone(fullyQualifiedDomainName, callerReference, region):
    response = boto3.client('route53', region_name=region).create_hosted_zone(
        Name=fullyQualifiedDomainName,
        CallerReference=callerReference
    )
    hostedZoneID = response['HostedZone']['Id']
    print(f"{Fore.MAGENTA}Hosted zone for{Style.RESET_ALL} {Fore.CYAN}{fullyQualifiedDomainName}{Style.RESET_ALL} {Fore.MAGENTA}has been created.{Style.RESET_ALL}")
    print('\n')
    return hostedZoneID


# Delete a hosted zone
def delete_hosted_zone(hostedZoneID, fullyQualifiedDomainName, region):
    boto3.client('route53', region_name=region).delete_hosted_zone(
        Id=hostedZoneID
    )
    print(f"{Fore.MAGENTA}Hosted zone for{Style.RESET_ALL} {Fore.CYAN}{fullyQualifiedDomainName}{Style.RESET_ALL} {Fore.MAGENTA}has been deleted.{Style.RESET_ALL}")
    print('\n')


# Create, change, or delete a resource record set
def modify_record_set_1(hostedZoneID, changeBatchComment, action, recordName, recordType, 
                        aliasHostedZoneID, dnsName, region, evaluateTargetHealth=True):
    response = boto3.client('route53', region_name=region).change_resource_record_sets(
        HostedZoneId=hostedZoneID,
        ChangeBatch={
            'Comment': changeBatchComment,
            'Changes': [
                {
                    'Action': action,
                    'ResourceRecordSet': {
                        'Name': recordName,
                        'Type': recordType,
                        'AliasTarget': {
                            'HostedZoneId': aliasHostedZoneID,
                            'DNSName': dnsName,
                            'EvaluateTargetHealth': evaluateTargetHealth
                        }
                    }
                }
            ]
        }
    )
    recordSetID = response['ChangeInfo']['Id']
    print(f"{Fore.CYAN}{action}{Style.RESET_ALL} {Fore.MAGENTA}action for{Style.RESET_ALL} {Fore.CYAN}{recordType}{Style.RESET_ALL} {Fore.MAGENTA}type has been accomplished for{Style.RESET_ALL} {Fore.CYAN}{recordName}{Style.RESET_ALL} {Fore.MAGENTA}record.{Style.RESET_ALL}")
    print('\n')
    return recordSetID


# Create a CloudFront origin access identity
def create_cloudfront_oai(oaiCallerReference, oaiComment, region):
    response = boto3.client('cloudfront', region_name=region).create_cloud_front_origin_access_identity(
        CloudFrontOriginAccessIdentityConfig={
            'CallerReference': oaiCallerReference,
            'Comment': oaiComment
        }
    )
    oaiID = response['CloudFrontOriginAccessIdentity']['Id']
    return oaiID
