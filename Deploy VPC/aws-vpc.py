import boto3
import re
import inquirer
import time
from inquirer.themes import GreenPassion
from colorama import Fore, Back, Style 
import sys
import os.path
from requests import get
import itertools
from datetime import datetime
import json
import pickle

print('\n')



def define_parameters():
    global regions, outstanding_regions, availability_zone_map, vpc_to_region, vpc_info, vpc_cidr_block, vpc_list, cidr_blocks_of_vpcs

    default_region = "eu-west-1"
    ec2_client = boto3.client('ec2', region_name = default_region)
    print(Fore.MAGENTA, "Going to define parameters now...", Style.RESET_ALL)
    print('\n')

    # Get the list of enabled regions and their long names
    response = ec2_client.describe_regions()
    enabled_regions = response['Regions']
    regions = []
    for region in enabled_regions:
        regions.append(region['RegionName'])
    print(Fore.MAGENTA, "All regions available: ", Style.RESET_ALL, Fore.CYAN, regions, Style.RESET_ALL)
    print('\n')

    # Get the selected regions when the vpc(s) were first established if any vpc has already been established
    print(Fore.MAGENTA, "Getting the regions where our VPCs are deployed...", Style.RESET_ALL)
    print('\n')

    # Save the regions we are working in as a pickle file
    try:
        with open('outstanding_regions.pkl', 'rb') as f:
            outstanding_regions = pickle.load(f)
    except:
        outstanding_regions = []
        for region in regions:
            response = boto3.client('ec2', region_name = region).describe_vpcs()
            if len(response['Vpcs']) > 1:
                outstanding_regions.append(region)
        with open('outstanding_regions.pkl', 'wb') as f:
            pickle.dump(outstanding_regions, f)

    # In case when we want to work independent of a local file. But this works slower...
    # for region in regions:
    #     response = boto3.client('ec2', region_name = region).describe_vpcs()
    #     if len(response['Vpcs']) > 1:
    #         outstanding_regions.append(region)
    if outstanding_regions:        
        print(Fore.MAGENTA, "All regions outstanding: ", Style.RESET_ALL, Fore.CYAN, outstanding_regions, Style.RESET_ALL)
    else:
        print(Fore.MAGENTA, "No VPC in any region has been deployed yet.", Style.RESET_ALL)
    print('\n')

    # Define availability zones outstanding
    availability_zone_map = {}
    for selected_region in outstanding_regions:
        availability_zones = []
        response = boto3.client('ec2', region_name = selected_region).describe_availability_zones(
            AllAvailabilityZones=True,
        )    
        availabilityZonesInRegion = response['AvailabilityZones']
        for az in availabilityZonesInRegion:
            availability_zones.append(az['ZoneName'])
        availability_zone_map[selected_region] = availability_zones

    # Describe the vpcs created in the selected regions if any vpc has already been established
    vpc_to_region = {}
    vpc_info = {}
    vpc_cidr_block = {}
    for selected_region in outstanding_regions:    
        vpc_to_region, vpc_info, vpc_cidr_block = describe_vpcs(selected_region)
    vpc_list = list(vpc_to_region.keys())
    cidr_blocks_of_vpcs = []
    return outstanding_regions, availability_zone_map, vpc_to_region, vpc_info, vpc_cidr_block, vpc_list, cidr_blocks_of_vpcs



def create_vpc():
    with open('outstanding_regions.pkl', 'rb') as f:
        outstanding_regions = pickle.load(f)

    # Determine the regions in which you want to launch VPCs
    message = f"{Fore.LIGHTBLUE_EX} Select regions in which you want to launch a VPC? {Style.RESET_ALL}"
    questions = [
    inquirer.Checkbox('region_list',
                    message=message,
                    choices=regions
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_regions = answers['region_list']

    # Set the number of VPCs you want to launch in each selected region
    regional_vpcs = {}
    for selected_region in selected_regions:
        numberOfRegionalVPCMessage = f"{Fore.LIGHTBLUE_EX}Enter the number of VPCs you want to launch in region: {Style.RESET_ALL} {Fore.RED}{selected_region}{Style.RESET_ALL}: "
        numberOfRegionalVPCs = int(input(numberOfRegionalVPCMessage))
        print('\n')
        regional_vpcs[selected_region] = numberOfRegionalVPCs
    totalNumberOfVPC = sum(regional_vpcs.values())
    print(Fore.MAGENTA, "Total number of VPCs across all regions are: ", Style.RESET_ALL, Fore.CYAN, totalNumberOfVPC, Style.RESET_ALL)
    print('\n')
    print(Fore.MAGENTA, "VPCs per each region: ", Style.RESET_ALL, Fore.CYAN, regional_vpcs, Style.RESET_ALL)
    print('\n')

    # Get the CIDR blocks of all our VPCs in the world
    for cidr_block in vpc_cidr_block:
        cidrBlockOfVPC = vpc_cidr_block[cidr_block]
        second_part = re.findall(r'([0-9]{1,3})', cidrBlockOfVPC)[1]
        cidr_blocks_of_vpcs.append("z"+second_part)

    for selected_region in selected_regions:

        # Add the new region to the outstanding regions list if it is not in the list already
        if selected_region not in outstanding_regions:
            outstanding_regions.append(selected_region)

        # Describe VPCs in the selected region only for the naming purpose
        vpc_to_region, _, _ = describe_vpcs(selected_region)
        vpc_to_region_key_list = [key for key, value in vpc_to_region.items() if value == selected_region]
        for _ in range(regional_vpcs[selected_region]):
            vpcSequenceNo = find_sequence_number(vpc_to_region_key_list)
            vpcName = selected_region.replace("-", "").upper() + "-" + str(vpcSequenceNo)
            vpc_to_region_key_list.append(vpcName)
            cidrMessage = f"{Fore.LIGHTBLUE_EX}Enter a CIDR block for the{Style.RESET_ALL} {Fore.RED}{vpcName}{Style.RESET_ALL}, {Fore.LIGHTBLUE_EX}e.g. 10.0.0.0/16. Press Enter to go with the default option: {Style.RESET_ALL}"
            cidrInput = input(cidrMessage)
            if cidrInput == "":
                vpcSequenceNo = find_sequence_number(cidr_blocks_of_vpcs)
                defaultCidr = "10."+str(vpcSequenceNo)+".0.0/16"
                cidrBlock = defaultCidr
            else:
                cidrBlock = cidrInput
            second_part = re.findall(r'([0-9]{1,3})', cidrBlock)[1]
            cidr_blocks_of_vpcs.append("z"+second_part)

            # Create the VPC now
            vpc_response = boto3.client('ec2', region_name = selected_region).create_vpc(
                CidrBlock=cidrBlock,
                AmazonProvidedIpv6CidrBlock=False,
                InstanceTenancy='default',
                TagSpecifications=[
                    {
                        'ResourceType': 'vpc',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': vpcName
                            },
                        ]
                    },
                ]
            )
            print('\n')
            print(Fore.MAGENTA, "Going to create VPCs now...", Style.RESET_ALL)
            print('\n')
            vpcID = vpc_response['Vpc']['VpcId']

            # Enable DNS hostname
            response = boto3.client('ec2', region_name = selected_region).modify_vpc_attribute(
                EnableDnsHostnames={
                    'Value': True
                },
                VpcId=vpcID
            )

            # Create an internet gateway
            igw_response = boto3.client('ec2', region_name = selected_region).create_internet_gateway(
                TagSpecifications=[
                    {
                        'ResourceType': 'internet-gateway',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': vpcName + '-igw'
                            },
                        ]
                    },
                ],
            )
            igwID = igw_response['InternetGateway']['InternetGatewayId']

            # Attach the internet gateway
            response = boto3.client('ec2', region_name = selected_region).attach_internet_gateway(
                InternetGatewayId=igwID,
                VpcId=vpcID
            )

            # Identify the main route table
            response = boto3.client('ec2', region_name = selected_region).describe_route_tables(
                Filters=[
                    {
                        'Name': 'vpc-id',
                        'Values': [
                            vpcID,
                        ]
                    },
                ],
            )
            mainRouteTableID = response['RouteTables'][0]['RouteTableId']

            # Change the name of the main route table
            routeTableName = vpcName+'.Main.rt-1'
            response = boto3.client('ec2', region_name = selected_region).create_tags(
                Resources=[
                    mainRouteTableID,
                ],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': routeTableName
                    },
                ]
            )

            # Open the main route table to the internet traffic
            response = boto3.client('ec2', region_name = selected_region).create_route(
                DestinationCidrBlock='0.0.0.0/0',
                GatewayId=igwID,
                RouteTableId=mainRouteTableID,
            )
            response = boto3.client('ec2', region_name = selected_region).create_route(
                DestinationIpv6CidrBlock='::/0',
                GatewayId=igwID,
                RouteTableId=mainRouteTableID,
            )

            # Identify the VPC's default NACL
            existing_nacls = describe_network_acls(selected_region, filterName='vpc-id', filterID=vpcID)
            for key, value in existing_nacls.items():
                if value[3] == True:
                    naclID = existing_nacls[key][0]

            # Change the name of the default network access control list
            naclName = vpcName+".Pub.nacl-1"
            response = boto3.client('ec2', region_name = selected_region).create_tags(
                Resources=[
                    naclID,
                ],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': naclName
                    },
                ]
            )
            # Identify the VPC's default security group
            response = boto3.client('ec2', region_name = selected_region).describe_security_groups(
                Filters=[
                    {
                        'Name': 'vpc-id',
                        'Values': [
                            vpcID,
                        ]
                    },
                ],
            )
            sgID = response['SecurityGroups'][0]['GroupId']

            # Change the name of the default security group
            sgName = vpcName+".Default.sg-1"
            response = boto3.client('ec2', region_name = selected_region).create_tags(
                Resources=[
                    sgID,
                ],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': sgName
                    },
                ]
            )

    # Save the new outstanding regions list
    outstanding_regions = list(set(outstanding_regions))
    with open('outstanding_regions.pkl', 'wb') as f:
        pickle.dump(outstanding_regions, f)
    print('\n')
    print(Fore.MAGENTA, "VPC(s) have been successfully created in the selected regions: ", Style.RESET_ALL, Fore.CYAN, regional_vpcs, Style.RESET_ALL)
    print('\n')
    print(Fore.MAGENTA, "Internet gateways have been created and attached to the VPCs. Main route table has been opened to the internet traffic.", Style.RESET_ALL)
    print('\n')



def create_subnet(subnetMessage, vpcRegion, vpc, subnetTag, cidrNumber, printMessage, vpcID):
    questions = [
    inquirer.List('subnet_list',
                    message=subnetMessage,
                    choices=availability_zone_map[vpcRegion]
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selectedZone = answers['subnet_list']            
    cidrBlockForSubnet = vpc_cidr_block[vpc] + str(cidrNumber) + ".0/24"
    subnetTagValue  = f"{vpc}.{subnetTag}"
    print(Fore.MAGENTA, printMessage, Style.RESET_ALL)
    print('\n')
    response = boto3.client('ec2', region_name = vpcRegion).create_subnet(
    TagSpecifications=[
        {
            'ResourceType': 'subnet',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': subnetTagValue
                },
            ]
        },
    ],
    AvailabilityZone=selectedZone,
    CidrBlock=cidrBlockForSubnet,
    VpcId=vpcID,
)
    subnetID = response['Subnet']['SubnetId']
    return subnetID, subnetTagValue         
 


def add_subnet():
    # Choose the vpcs in which you want to create subnets
    subnetMessage = f"{Fore.LIGHTBLUE_EX} Select the vpcs that you want to add subnets {Style.RESET_ALL}"
    add_subnets_to_vpc = select_vpcs(subnetMessage)

    # Set the number of public and private subnets for each VPC in each region
    vpc_subnet_map = {}
    for add_subnet in add_subnets_to_vpc:
        subnet_map = []
        numberOfPublicSubnetMessage = f"{Fore.LIGHTBLUE_EX}Enter the number of{Style.RESET_ALL} {Fore.RED}public{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}subnets to be deployed in{Style.RESET_ALL} {Fore.RED}{vpc_to_region[add_subnet]}{Style.RESET_ALL} {Back.YELLOW}{Fore.LIGHTBLUE_EX}{add_subnet}{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}.\nType 0 for no deployment:{Style.RESET_ALL}"
        numberOfPublicSubnetsInput = int(input(numberOfPublicSubnetMessage))
        subnet_map.append(numberOfPublicSubnetsInput)
        print('\n')
        numberOfPrivateSubnetMessage = f"{Fore.LIGHTBLUE_EX}Enter the number of{Style.RESET_ALL} {Fore.RED}private{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}subnets to be deployed in{Style.RESET_ALL} {Fore.RED}{vpc_to_region[add_subnet]}{Style.RESET_ALL} {Back.YELLOW}{Fore.LIGHTBLUE_EX}{add_subnet}{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}.\nType 0 for no deployment:{Style.RESET_ALL}"
        numberOfPrivateSubnetsInput = int(input(numberOfPrivateSubnetMessage))        
        subnet_map.append(numberOfPrivateSubnetsInput)
        print('\n')
        vpc_subnet_map[add_subnet] = subnet_map
    print(Fore.MAGENTA, "VPCs, public and private subnets: ", Fore.CYAN, vpc_subnet_map, Style.RESET_ALL)
    print('\n')

    # Create public and private subnets
    for vpc in vpc_subnet_map:
        vpcRegion = vpc_to_region[vpc]
        vpcID = vpc_info[vpc]

        # Describe the existing subnets in the chosen VPC
        public_subnet_cidr_numbers = []
        private_subnet_cidr_numbers = []
        try:
            subnets, public_subnet_names, private_subnet_names = describe_subnets(vpcID, vpcRegion)

            # Find the lowest available cidr numbers for the new subnets
            for subnet in subnets:
                subnetCidrBlock = subnets[subnet][2]
                subnetCidrNumber = int(re.findall(r'[.][0-9]{1,3}', subnetCidrBlock)[1].replace(".",""))
                if subnetCidrNumber >= 100:
                    public_subnet_cidr_numbers.append("S" + str(subnetCidrNumber - 100))
                elif subnetCidrNumber < 100:
                    private_subnet_cidr_numbers.append("S" + str(subnetCidrNumber))
            
        except:
            public_subnet_cidr_numbers = ["S0"]
            private_subnet_cidr_numbers = ["S0"]
            public_subnet_names = ["Pub0"]
            private_subnet_names = ["Pri0"]

        # Find the main route table
        _, mainRouteTableID = describe_rt(vpcRegion, filtername='vpc-id', filterID=vpcID)
 
        # Create public subnets
        numberOfPublicSubnets = vpc_subnet_map[vpc][0]
        for public in range(numberOfPublicSubnets):
            publicMessage = f"{Fore.LIGHTBLUE_EX}Select the availability zone to create{Style.RESET_ALL} {Fore.RED}{public+1}. public{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}subnet in VPC{Style.RESET_ALL} {Fore.RED}{vpc}{Style.RESET_ALL}"
            printMessage = f"{Fore.LIGHTBLUE_EX}Going to create public subnets now...{Style.RESET_ALL}"
 
            # Numeration of public subnet
            publicSubnetSequenceNo = find_sequence_number(public_subnet_names)
            tag = "Pub"+str(publicSubnetSequenceNo)
            public_subnet_names.append(tag)
            publicCidrNumber = find_sequence_number(public_subnet_cidr_numbers) + 100
            publicSubnetID, publicSubnetTagValue = create_subnet(publicMessage, vpcRegion, vpc, tag, publicCidrNumber, printMessage, vpcID)
            public_subnet_cidr_numbers.append("S" + str(publicCidrNumber - 100))

            # Associate the public subnet with the main route table
            boto3.client('ec2', region_name = vpcRegion).associate_route_table(
                RouteTableId=mainRouteTableID,
                SubnetId=publicSubnetID
            )
            print(f"{Fore.MAGENTA}Public subnet has been successfully created: {Style.RESET_ALL} {Fore.CYAN}{publicSubnetTagValue}{Style.RESET_ALL}")
            print('\n')
            print(Fore.MAGENTA, "Main route table has been associated with the public subnet.", Style.RESET_ALL)
            print('\n')

        # Create private subnets
        numberOfPrivateSubnets = vpc_subnet_map[vpc][1]
        for private in range(numberOfPrivateSubnets):
            privateMessage = f"{Fore.LIGHTBLUE_EX}Select the availability zone to create{Style.RESET_ALL} {Fore.RED}{private+1}. private{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}subnet in VPC{Style.RESET_ALL} {Fore.RED}{vpc}{Style.RESET_ALL}"
            printMessage = f"{Fore.LIGHTBLUE_EX}Going to create private subnets now...{Style.RESET_ALL}"
 
            # Numeration of private subnet
            privateSubnetSequenceNo = find_sequence_number(private_subnet_names)
            tag = "Pri"+str(privateSubnetSequenceNo)
            private_subnet_names.append(tag)
            privateCidrNumber = find_sequence_number(private_subnet_cidr_numbers)
            _, privateSubnetTagValue = create_subnet(privateMessage, vpcRegion, vpc, tag, privateCidrNumber, printMessage, vpcID)
            private_subnet_cidr_numbers.append("S" + str(privateCidrNumber))
            print(f"{Fore.MAGENTA}Private subnet has been successfully created: {Style.RESET_ALL} {Fore.CYAN}{privateSubnetTagValue}{Style.RESET_ALL}")
            print('\n')
            message = f"{Fore.LIGHTBLUE_EX}Should we create and/or associate a route table with this subnet? (y/N):{Style.RESET_ALL}"
            confirmation = input(message)
            print("\n")
            if confirmation == "y" or confirmation == "Y":
                create_and_associate_rt(vpc)
            else:
                print(Fore.MAGENTA, "You can associate a route table with the subnet later.", Style.RESET_ALL)
            print("\n")



def create_and_associate_rt(vpc=None, subnets={}):
    # Choose the vpc in which you want to create and/or associate a route table
    if vpc:
        vpcName = vpc
        vpcRegion = vpc_to_region[vpc]
        vpcID = vpc_info[vpc]
    else:
        rtMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to create and/or associate a route table{Style.RESET_ALL}"
        vpcName, vpcRegion, vpcID = select_vpc(rtMessage)
 
    # Check to create a new route table or use an existing one
    rtMessage = f"{Fore.LIGHTBLUE_EX}Do you want to create and associate a new route table or associate an existing one?{Style.RESET_ALL}"
    givenAnswer = new_or_existing(rtMessage)

    # Describe the existing subnets in the chosen VPC
    subnets, _, _ = describe_subnets(vpcID, vpcRegion)

    # Determine the subnets that will be associated with the route table
    rtMessage = f"{Fore.LIGHTBLUE_EX}Select the subnet(s) you want to associate with the route table{Style.RESET_ALL}"
    selected_subnets = select_subnets(rtMessage, subnets, string="Checkbox")
 
    # Describe existing route tables in the chosen VPC
    existing_route_tables, _ = describe_rt(vpcRegion, filtername='vpc-id', filterID=vpcID)
    route_table_names = list(existing_route_tables.keys())
    rtSequenceNo = find_sequence_number(route_table_names)
 

    # Create a new route table 
    def create_rt():
        routeTableName = vpcName+".rt-"+str(rtSequenceNo)
        response = boto3.client('ec2', region_name = vpcRegion).create_route_table(
            VpcId=vpcID,
            TagSpecifications=[
                {
                    'ResourceType': 'route-table',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': routeTableName
                        },
                    ]
                },
            ]
        )
        routeTableID = response['RouteTable']['RouteTableId']

        # Associate the new route table with the selected subnet(s)
        for selected_subnet in selected_subnets:
            selectedSubnetID = selected_subnet[1]
            check_rt_association(vpcRegion, selectedSubnetID, routeTableID)
        print(Fore.MAGENTA, "Route table has been successfully created and associated with the subnets selected.", Style.RESET_ALL)
        print('\n')


    # Associate the existing route table with the selected subnet(s)
    def associate_rt():
        rtMessage = f"{Fore.LIGHTBLUE_EX} Select the route table you want to associate with the selected subnets {Style.RESET_ALL}"
        rt = select_rt(rtMessage, existing_route_tables)
        print('\n')     
        for selected_subnet in selected_subnets:
            routeTableID=existing_route_tables[rt][0]
            selectedSubnetID = selected_subnet[1]
            check_rt_association(vpcRegion, selectedSubnetID, routeTableID)
        print(Fore.MAGENTA, "Route table has been successfully associated with the subnets selected.", Style.RESET_ALL)
        print('\n')

    if givenAnswer == "new":
        create_rt()
    elif givenAnswer == "existing":
        associate_rt()



def create_and_associate_nacl():
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to create and/or associate a network access control list{Style.RESET_ALL}"
    vpcName, vpcRegion, vpcID = select_vpc(vpcMessage)
    print('\n')

    # Check to create a new network access control list or use an existing one
    naclMessage = f"{Fore.LIGHTBLUE_EX}Do you want to create and associate a new network access control list or associate an existing one?{Style.RESET_ALL}"
    givenAnswer = new_or_existing(naclMessage)
    print('\n')

    # Describe the existing subnets in the chosen VPC
    subnets, _, _ = describe_subnets(vpcID, vpcRegion)

    # Determine the subnets that will be associated with the network access control list
    naclMessage = f"{Fore.LIGHTBLUE_EX}Select the subnet(s) you want to associate with the network access contol list{Style.RESET_ALL}"
    selected_subnets = select_subnets(naclMessage, subnets, string="Checkbox")
    print('\n')

    # Describe the existing NACLs in the chosen VPC
    existing_nacls = describe_network_acls(vpcRegion, filterName='vpc-id', filterID=vpcID)

    # Get the sequence number
    existing_nacl_names = list(existing_nacls.keys())
    naclSequenceNo = find_sequence_number(existing_nacl_names)


    # Create a new network access control list 
    def create_nacl():
        networkACLName = vpcName+".nacl-"+str(naclSequenceNo)
        response = boto3.client('ec2', region_name = vpcRegion).create_network_acl(
            VpcId=vpcID,
            TagSpecifications=[
                {
                    'ResourceType': 'network-acl',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': networkACLName
                        },
                    ]
                },
            ]
        )
        naclID = response['NetworkAcl']['NetworkAclId']

        # Get the associations
        associations = [value[1] for key, value in existing_nacls.items()]
        nonEmptyList = list(itertools.chain(*[x for x in associations if x != []]))

        # Associate the new network access control list with the selected subnet(s)
        for selected_subnet in selected_subnets:
            SubnetId = selected_subnet[1]
            for association in nonEmptyList:
                 if list(association.keys())[0] == SubnetId:
                     associationID = association[SubnetId]
            response = boto3.client('ec2', region_name = vpcRegion).replace_network_acl_association(
                AssociationId=associationID,
                NetworkAclId=naclID
            )
        print(Fore.MAGENTA, "Network access control list has been successfully created and associated with the selected subnets.", Style.RESET_ALL)
        print('\n')


    # Associate the existing network access control list with the selected subnet(s)
    def associate_nacl():
        naclMessage = f"{Fore.LIGHTBLUE_EX}Select the network access control list you want to associate with the selected subnets{Style.RESET_ALL}"
        selected_nacl = select_nacls(naclMessage, existing_nacls, string="List")
        naclID = existing_nacls[selected_nacl][0]
        print('\n')

         # Get the associations
        associations = [value[1] for key, value in existing_nacls.items()]
        nonEmptyList = list(itertools.chain(*[x for x in associations if x != []]))

        # Associate the new network access control list with the selected subnet(s)
        for selected_subnet in selected_subnets:
            SubnetId = selected_subnet[1]
            for association in nonEmptyList:
                 if list(association.keys())[0] == SubnetId:
                     associationID = association[SubnetId]
            boto3.client('ec2', region_name = vpcRegion).replace_network_acl_association(
                AssociationId=associationID,
                NetworkAclId=naclID
            )
        print(Fore.MAGENTA, "Network access control list has been successfully associated with the selected subnets.", Style.RESET_ALL)
        print('\n')

    if givenAnswer == "new":
        create_nacl()
    elif givenAnswer == "existing":
        associate_nacl()



def create_and_attach_sg():
    sgmessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to create and/or attach a security group{Style.RESET_ALL}"
    vpcName, vpcRegion, vpcID = select_vpc(sgmessage)
    print('\n')

    # Check to create a new security group or use an existing one
    sgMessage = f"{Fore.LIGHTBLUE_EX}Do you want to create and attach a new security group or attach an existing one?{Style.RESET_ALL}"
    givenAnswer = new_or_existing(sgMessage)
    print('\n')

    # Describe the existing network interfaces in the chosen VPC
    existing_network_interfaces, _ = describe_network_interfaces(vpcID, vpcRegion)

    # Determine the network interfaces that will be attached to the security group
    niMessage = f"{Fore.LIGHTBLUE_EX}Select the network interfaces you want to attach to the security group{Style.RESET_ALL}"
    selected_network_interfaces = select_ni(niMessage, existing_network_interfaces)
    print('\n')

    # Describe the existing security groups in the chosen VPC
    security_groups = describe_sg(vpcRegion, vpcID)
    security_group_names = list(security_groups.keys())
    sgSequenceNo = find_sequence_number(security_group_names)
    securityGroupIDs = []


    # Create a new security group 
    def create_sg():
        securityGroupName = vpcName+".sg-"+str(sgSequenceNo)
        descriptionInput = input(f"{Fore.LIGHTBLUE_EX}Type a security group description. Press Enter to go with the default option: {Style.RESET_ALL}")
        print('\n')
        defaultDescription = f"security group for instances to be deployed in VPC {vpcName}"
        if descriptionInput == "":
            description = defaultDescription
        else:
            description = descriptionInput
        response = boto3.client('ec2', region_name = vpcRegion).create_security_group(
            Description=description,
            GroupName=securityGroupName,
            VpcId=vpcID,
            TagSpecifications=[
                {
                    'ResourceType':'security-group',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': securityGroupName
                        },
                    ]
                },
            ],
        )
        securityGroupID = response['GroupId']
        chosenAction = check_sg_attachment()

        if chosenAction == 'replace':
            replace_sg(vpcRegion, selected_network_interfaces, existing_network_interfaces, securityGroupID)
            print(Fore.MAGENTA, "Security groups for the selected network interfaces have been replaced with the new security group.", Style.RESET_ALL)
            print('\n')
        elif chosenAction == 'add':
            securityGroupIDs.append(securityGroupID)
            add_sg(vpcRegion, selected_network_interfaces, existing_network_interfaces, securityGroupIDs)
            print(Fore.MAGENTA, "New security group has been added to other security groups that are attached to the selected network interfaces.", Style.RESET_ALL)
            print('\n')


    # Attach a security group to the selected network interface(s)
    def attach_sg():
        # Select the security group
        sgMessage = f"{Fore.LIGHTBLUE_EX}Select the security group you want to attach to network interfaces{Style.RESET_ALL}"
        selected_security_groups = select_sg(sgMessage, security_groups)
        chosenAction = check_sg_attachment()
        if chosenAction == 'replace':
            for security_group in selected_security_groups:
                securityGroupIDs.append(security_groups[security_group])
            replace_sg(vpcRegion, selected_network_interfaces, existing_network_interfaces, securityGroupIDs)
            print(Fore.MAGENTA, "Security groups for the selected network interfaces have been replaced with the new security group.", Style.RESET_ALL)
            print('\n')
        elif chosenAction == 'add':
            for security_group in selected_security_groups:
                securityGroupIDs.append(security_groups[security_group])
            add_sg(vpcRegion, selected_network_interfaces, existing_network_interfaces, securityGroupIDs)
            print(Fore.MAGENTA, "New security group has been added to other security groups that are attached to the selected network interfaces.", Style.RESET_ALL)
            print('\n')

    if givenAnswer == "new":
        create_sg()
    elif givenAnswer == "existing":
        attach_sg()



# Create a NACL entry
def create_nacl_entries(vpcRegion, vpcID, existing_nacls, selected_nacls):
    print('\n')
    print(f"{Fore.LIGHTBLUE_EX}1. Press Enter to skip defining an ALLOW or DENY rule{Style.RESET_ALL}")
    print('\n')
    print(f"{Fore.LIGHTBLUE_EX}2. To enter multiple IP addresses, separate them by commas, e.g. 173.20.12.6/32, 173.33.250.18/32, 10.6.224.13/16{Style.RESET_ALL}")
    print('\n') 
    all_nacls = define_and_create_rule(existing_nacls, selected_nacls, vpcRegion)
    print(f"{Fore.MAGENTA}Entry rules for the following network access control list, traffic, port and IP addresses have been succesfully created:{Style.RESET_ALL}")
    print('\n') 
    for nacl in all_nacls:
        all_nacl_values = all_nacls[nacl]
        for key, value in all_nacl_values.items():
            print(f"{Fore.YELLOW}{key} {value}{Style.RESET_ALL}")
            print('\n')



def replace_nacl_entries(vpcRegion, vpcID, existing_nacls, selected_nacls):

    def replace_values():

        _, type_and_ports = describe_ports()

        input_questions = {
            'CidrBlock': "",
            'PortRange' : "",
            'RuleAction': f"{Fore.LIGHTBLUE_EX}Choose{Style.RESET_ALL} {Fore.RED}allow{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}to allow the traffic, or{Style.RESET_ALL} {Fore.RED}deny{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}to block the traffic{Style.RESET_ALL}",
        }

        input_options = {
            'CidrBlock': input(f"{Fore.LIGHTBLUE_EX}Enter the new IP address (only one): {Style.RESET_ALL}") if 'CidrBlock' in selected_parameters else selected_nacl_entry['CidrBlock'],
            'PortRange' : selected_nacl_entry['PortRange'],
            'RuleAction': choose_from_list(['allow', 'deny']) if 'RuleAction' in selected_parameters else selected_nacl_entry['RuleAction']
        }

        for selected_parameter in selected_parameters:
            print(input_questions[selected_parameter])
            print('\n')
            selected_nacl_entry[selected_parameter] = input_options[selected_parameter]

        if 'PortRange' in selected_parameters:
            print(f"{Fore.LIGHTBLUE_EX}Choose the new port: {Style.RESET_ALL}")
            print('\n')
            ProtocolPort = type_and_ports[choose_from_list(type_and_ports)]
            port = ProtocolPort[1]
            protocol = str(ProtocolPort[0])
        else:
            port = selected_nacl_entry['PortRange']['From']
            protocol = selected_nacl_entry['Protocol']

        boto3.client('ec2', region_name = vpcRegion).replace_network_acl_entry(
            CidrBlock=input_options['CidrBlock'],
            Egress=selected_nacl_entry['Egress'],
            NetworkAclId=naclID,
            PortRange={
                'From': port,
                'To': port
            },
            Protocol=protocol,
            RuleAction=input_options['RuleAction'],
            RuleNumber=selected_nacl_entry['RuleNumber']
        )
        new_nacl_entry = {'Cidr Block': input_options['CidrBlock'], 'Egress': selected_nacl_entry['Egress'], 'Port Range': {'From': port, 'To': port}, 'Protocol': protocol, 'Rule Action': input_options['RuleAction'], 'Rule Number': selected_nacl_entry['RuleNumber']}
        print(f"{Fore.MAGENTA}Selected network ACL rule number {selected_nacl_entry['RuleNumber']} has been replaced with{Style.RESET_ALL} {Fore.YELLOW}{new_nacl_entry}{Style.RESET_ALL}")
        print('\n')


    # Select the network access control list entries you want to work on 
    for selected_nacl in selected_nacls:
        print(f"{Fore.MAGENTA}You can replace the entry(s) of network access control list{Style.RESET_ALL} {Fore.RED}{selected_nacl}{Style.RESET_ALL}")
        print('\n')
        naclID = existing_nacls[selected_nacl][0]
        naclEntryMessage = f"{Fore.LIGHTBLUE_EX}Select the network access control list entries you want to replace{Style.RESET_ALL}"
        selected_nacl_entries = select_nacl_entries(vpcRegion, naclID, naclEntryMessage)
        print('\n')
        for selected_nacl_entry in selected_nacl_entries:
            print(f"{Fore.MAGENTA}The network access control list entry that will be replaced: {Style.RESET_ALL}\n\n{Fore.RED}{selected_nacl_entry}{Style.RESET_ALL}")
            print('\n')
            parameterMessage = f"{Fore.LIGHTBLUE_EX}Choose the parameters of the network access control list entry, which you want to change: {Style.RESET_ALL}"
            questions = [
                inquirer.Checkbox('parameters',
                                message=parameterMessage,
                                choices=['CidrBlock', 'PortRange', 'RuleAction']
                                ),
            ]
            answers = inquirer.prompt(questions, theme=GreenPassion())
            selected_parameters = answers['parameters']
            print('\n')
            replace_values()



def modify_nacl_entries():
    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to modify network access control list entries{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe the network access control lists in the chosen VPC
    existing_nacls = describe_network_acls(vpcRegion, filterName='vpc-id', filterID=vpcID)

    # Select the network access control list that you want to change its entries
    naclMessage = f"{Fore.LIGHTBLUE_EX}Select the network access control list that you want to change its entries{Style.RESET_ALL}"
    selected_nacls = select_nacls(naclMessage, existing_nacls, string="Checkbox")

    # Choose the type of operation you want to do with the network ACL entries
    resourceMessage = f"{Fore.LIGHTBLUE_EX}Choose the type of operation you want to do with the network ACL entries{Style.RESET_ALL}"
    operation = modify_resource(resourceMessage)

    if operation == "create an entry":
        create_nacl_entries(vpcRegion, vpcID, existing_nacls, selected_nacls)
    elif operation == "replace an entry":
        replace_nacl_entries(vpcRegion, vpcID, existing_nacls, selected_nacls)



def create_sg_rules(vpcRegion, vpcID, security_groups, selected_security_groups, traffic, type_and_ports):
    all_entries = []
    print('\n')
    for selected_security_group in selected_security_groups:
        sgID = security_groups[selected_security_group]

        # Decide inbound and/or outbound rules
        print(f"{Fore.LIGHTBLUE_EX}Define inbound and outbound rules for{Style.RESET_ALL}{Fore.RED} {selected_security_group}{Style.RESET_ALL}")
        print('\n')
        trafficMessage = f"{Fore.LIGHTBLUE_EX}Select{Style.RESET_ALL}{Fore.RED} inbound{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}and/or{Style.RESET_ALL}{Fore.RED} outbound{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}options to define rules{Style.RESET_ALL}"
        questions = [
            inquirer.Checkbox('traffic',
                            message=trafficMessage,
                            choices=traffic
                            ),
            ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        selected_traffics = answers['traffic']
        print('\n')
        for selected_traffic in selected_traffics:
            types = list(type_and_ports.keys())
            typeMessage = f"{Fore.LIGHTBLUE_EX}Select the type of{Style.RESET_ALL} {Fore.RED}{selected_traffic}{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}traffic{Style.RESET_ALL}"
            questions = [
                inquirer.Checkbox('type',
                                message=typeMessage,
                                choices=types
                                ),
                ]
            answers = inquirer.prompt(questions, theme=GreenPassion())
            traffic_types = answers['type']
            for traffic_type in traffic_types:
                protocol = type_and_ports[traffic_type][0]
                port = type_and_ports[traffic_type][1]
                if protocol == "$":
                    protocol = input(f"{Fore.LIGHTBLUE_EX}Enter the protocol number: {Style.RESET_ALL}")
                if port == "$":
                    port = input(f"{Fore.LIGHTBLUE_EX}Enter the port number: {Style.RESET_ALL}")
                ipAddresses = input(f"{Fore.LIGHTBLUE_EX}Enter IP address(es) to allow for{Style.RESET_ALL} {Fore.RED}{selected_traffic} {traffic_type}{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}traffic.\nTo enter multiple IP addresses, separate them by commas, e.g. 173.20.12.6/32, 173.33.250.18/32, 10.6.224.13/16: {Style.RESET_ALL}")
                ip_list = ipAddresses.replace(" ", "").split(",")
                description = input(f"{Fore.LIGHTBLUE_EX}Enter a description. Press Enter to leave it blank: {Style.RESET_ALL}")
                print('\n')
                for ip in ip_list:
                    if selected_traffic == "Inbound":
                        boto3.client('ec2', region_name = vpcRegion).authorize_security_group_ingress(
                            GroupId=sgID,
                            IpPermissions=[
                                {
                                    'FromPort': port,
                                    'IpProtocol': str(protocol),
                                    'IpRanges': [
                                        {
                                            'CidrIp': ip,
                                            'Description': description,
                                        },
                                    ],
                                    'ToPort': port,
                                },
                            ],
                        )
                    elif selected_traffic == "Outbound":
                        boto3.client('ec2', region_name = vpcRegion).authorize_security_group_egress(
                            GroupId=sgID,
                            IpPermissions=[
                                {
                                    'FromPort': port,
                                    'IpProtocol': str(protocol),
                                    'IpRanges': [
                                        {
                                            'CidrIp': ip,
                                            'Description': description,
                                        },
                                    ],
                                    'ToPort': port,
                                },
                            ],
                        )
                ipAddresses = ipAddresses.replace(" ", "").replace(",", ", ")
                entry = "For " + selected_security_group + ", " + selected_traffic + " " + traffic_type + " traffic rules have been defined for the following IP addresses: " + ipAddresses
                all_entries.append(entry)
    print(f"{Fore.MAGENTA}Entry rules for the following security groups, traffic, port and IP addresses have been succesfully created:{Style.RESET_ALL}")
    print('\n')
    for entry in all_entries:
        print(f"{Fore.YELLOW}{entry}{Style.RESET_ALL}")
        print('\n')



def modify_sg():
    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to modify security group entries{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe the existing security groups in the chosen VPC
    security_groups = describe_sg(vpcRegion, vpcID)

    # Select the security group that you want to change its entries
    sgMessage = f"{Fore.LIGHTBLUE_EX}Select the network access control list that you want to change its entries{Style.RESET_ALL}"
    selected_security_groups = select_sg(sgMessage, security_groups)

    traffic, type_and_ports = describe_ports()

    # Choose the type of operation you want to do with the security group entries
    resourceMessage = f"{Fore.LIGHTBLUE_EX}Choose the type of operation you want to do with the security group entries{Style.RESET_ALL}"
    operation = modify_resource(resourceMessage)

    if operation == "create an entry":
        create_sg_rules(vpcRegion, vpcID, security_groups, selected_security_groups, traffic, type_and_ports)
    elif operation == "replace an entry":
        changeEntryMessage = f"{Fore.MAGENTA}To replace a security group rule, first you should revoke the rule and then re-authorize it with new parameters.{Style.RESET_ALL}"
        print(changeEntryMessage)
        print('\n')



def create_routes(vpcRegion, vpcID, existing_route_tables, selected_route_tables, action):

    results = {}
    for selected_route_table in selected_route_tables:
        print('\n')
        print(f"{Fore.LIGHTBLUE_EX}Route table to be modified: {Style.RESET_ALL}{Fore.RED}{selected_route_table}{Style.RESET_ALL}")
        print('\n')
        options = []
        continuation = "yes"
        while continuation == "yes":


            # Define CIDR blocks as the destinations for the targets
            def define_cidr_blocks():
                ipv4 = input(f"{Fore.LIGHTBLUE_EX}Enter IPv4 CIDR blocks. Separate them by commas, e.g. 10.0.0.1, 173.25.34.46, 10.1.25.153. Press Enter to skip it: {Style.RESET_ALL}")
                ipv4_list = ipv4.replace(" ", "").split(",")
                print('\n')
                print('\n')
                ipv6 = input(f"{Fore.LIGHTBLUE_EX}Enter IPv6 CIDR blocks. Separate them by commas.\n\n e.g. 2001:0db8:85a3:0000:0000:8a2e:0370:7334, 2001:db8:85a3:8d3:1319:8a2e:370:7348, ::/0. Press Enter to skip it: {Style.RESET_ALL}")
                ipv6_list = ipv6.replace(" ", "").split(",")
                print('\n')
                return ipv4_list, ipv6_list


            # Replace targets in routes
            def replace_rt_routes(rtID, ip, ipv, selected_target, gatewayId, natGatewayId):
                if ipv == 4:
                    boto3.client('ec2', region_name = vpcRegion).replace_route(
                        DestinationCidrBlock=ip,
                        GatewayId=gatewayId,
                        NatGatewayId=natGatewayId,
                        RouteTableId=rtID,
                    )
                if ip == 6 and selected_target != "Nat Gateway":
                    boto3.client('ec2', region_name = vpcRegion).replace_route(
                        DestinationIpv6CidrBlock=ip,
                        GatewayId=gatewayId,
                        NatGatewayId=natGatewayId,
                        RouteTableId=rtID,
                    )


            # Create routes for the selected targets
            def create_rt_routes(rtID, ipv4_list, ipv6_list, gatewayId, natGatewayId):
                for ipv4 in ipv4_list:
                    boto3.client('ec2', region_name = vpcRegion).create_route(
                        DestinationCidrBlock=ipv4,
                        GatewayId=gatewayId,
                        NatGatewayId=natGatewayId,
                        RouteTableId=rtID,
                    )
                if ipv6_list and selected_option != "Nat Gateway":
                    for ipv6 in ipv6_list:
                        boto3.client('ec2', region_name = vpcRegion).create_route(
                            DestinationIpv6CidrBlock=ipv6,
                            GatewayId=gatewayId,
                            NatGatewayId=natGatewayId,
                            RouteTableId=rtID,
                        )


            # Select the targets for routes
            def define_targets():
                rtID = existing_route_tables[selected_route_table][0]
                if selected_option == "Gateway": 
                    gatewayId = describe_igw(vpcRegion, vpcID)
                    ipv4_list, ipv6_list = define_cidr_blocks()
                    natGatewayId=""
                    create_rt_routes(rtID, ipv4_list, ipv6_list, gatewayId, natGatewayId)
                    options.append(gatewayId)
                elif selected_option == "Nat Gateway":
                    nat_gateways = describe_ngw(vpcRegion, vpcID)
                    ngws = {}
                    for nat_gateway in nat_gateways:
                        ngwName = nat_gateway['Tags'][0]['Value']
                        ngwID = nat_gateway['NatGatewayId']
                        ngws[ngwName] = ngwID
                    ngwMessage = f"{Fore.LIGHTBLUE_EX}Choose a NAT gateway as the target.{Style.RESET_ALL}"
                    selected_ngw = select_ngw(ngwMessage, ngws)
                    natGatewayId = ngws[selected_ngw]
                    ipv4_list, ipv6_list = define_cidr_blocks()
                    gatewayId=""
                    create_rt_routes(rtID, ipv4_list, ipv6_list, gatewayId, natGatewayId)
                    options.append(natGatewayId)
                results[selected_route_table] = options


            # Replace routes
            def replace_routes():
                rtID = existing_route_tables[selected_route_table][0]
                routes = existing_route_tables[selected_route_table][2]
                routeMessage = f"{Fore.LIGHTBLUE_EX}Choose the routes that you want to replace in the route table{Style.RESET_ALL} {Fore.RED}{selected_route_table}{Style.RESET_ALL}"
                questions = [
                inquirer.Checkbox('route',
                                message=routeMessage,
                                choices=routes
                                ),
                ]
                answers = inquirer.prompt(questions, theme=GreenPassion())
                selected_routes = answers['route']
                for selected_route in selected_routes:
                    try:
                        ip = selected_route['DestinationCidrBlock']
                        ipv = 4
                    except:
                        pass
                    try:
                        ip = selected_route['DestinationIpv6CidrBlock']
                        ipv = 6
                    except:
                        pass
                    print(f"{Fore.LIGHTBLUE_EX}For the route{Style.RESET_ALL} {Fore.RED}{selected_route}{Style.RESET_ALL}{Fore.LIGHTBLUE_EX},{Style.RESET_ALL}")
                    print('\n')
                    destinationMessage = f"{Fore.LIGHTBLUE_EX}choose a new target for the destination{Style.RESET_ALL}"
                    questions = [
                    inquirer.List('target',
                                    message=destinationMessage,
                                    choices=['Gateway', 'Nat Gateway']
                                    )
                    ]
                    answers = inquirer.prompt(questions, theme=GreenPassion())
                    selected_target = answers['target']
                    print('\n')
                    if selected_target == "Gateway":
                        gatewayId = describe_igw(vpcRegion, vpcID)
                        target = gatewayId
                        natGatewayId = ""
                        # vpcEId = ""
                    elif selected_target == "Nat Gateway":
                        nat_gateways = describe_ngw(vpcRegion, vpcID)
                        ngws = {}
                        for nat_gateway in nat_gateways:
                            ngwName = nat_gateway['Tags'][0]['Value']
                            ngwID = nat_gateway['NatGatewayId']
                            ngws[ngwName] = ngwID
                        ngwMessage = f"{Fore.LIGHTBLUE_EX}Choose a NAT gateway as the target.{Style.RESET_ALL}"
                        selected_ngw = select_ngw(ngwMessage, ngws)
                        print('\n')
                        natGatewayId = ngws[selected_ngw]
                        target = natGatewayId
                        gatewayId = ""
                    replace_rt_routes(rtID, ip, ipv, selected_target, gatewayId, natGatewayId)
                    if ipv == 6 and selected_target == "Nat Gateway":
                        print(f"{Fore.MAGENTA}For the route table{Style.RESET_ALL} {Fore.RED}{selected_route_table}{Style.RESET_ALL}{Fore.MAGENTA}, the following route with the IPv6 destination could not be replaced with{Style.RESET_ALL} {Fore.CYAN}{selected_target} {target}:{Style.RESET_ALL}")
                        print('\n')
                        print(f"{Fore.YELLOW}{selected_route}{Style.RESET_ALL}")
                        print('\n')
                    else:
                        print(f"{Fore.MAGENTA}For the route table{Style.RESET_ALL} {Fore.RED}{selected_route_table}{Style.RESET_ALL}{Fore.MAGENTA}, the following route has been replaced with{Style.RESET_ALL} {Fore.CYAN}{selected_target} {target}:{Style.RESET_ALL}")
                        print('\n')
                        print(f"{Fore.YELLOW}{selected_route}{Style.RESET_ALL}")
                        print('\n')
                answer = input(f"{Fore.LIGHTBLUE_EX}Do you need to replace more targets in the route table{Style.RESET_ALL} {Fore.RED}{selected_route_table}{Style.RESET_ALL}{Fore.LIGHTBLUE_EX}? (y/N): {Style.RESET_ALL}")
                nonlocal continuation
                if answer == "y" or answer == "Y":
                    continuation = "yes"
                else:
                    continuation = "no"
                print('\n')
                return continuation


            # Decide if we want to create or replace a rule
            if action == "create":
                optionList = ['Gateway', 'Nat Gateway']
                routeMessage = f"{Fore.LIGHTBLUE_EX}Choose destination targets from the list.{Style.RESET_ALL}"
                questions = [
                inquirer.Checkbox('route',
                                message=routeMessage,
                                choices=optionList
                                ),
                ]
                answers = inquirer.prompt(questions, theme=GreenPassion())
                selected_options = answers['route']
                for selected_option in selected_options:
                    define_targets()
                answer = input(f"{Fore.LIGHTBLUE_EX}Do you need to define more destinations for the route table{Style.RESET_ALL} {Fore.RED}{selected_route_table}{Style.RESET_ALL}{Fore.LIGHTBLUE_EX}? (y/N): {Style.RESET_ALL}")
                if answer == "y" or answer == "Y":
                    continuation = "yes"
                else:
                    continuation = "no"
                    print(f"{Fore.MAGENTA}Following routes to the selected target destinations have been created for the chosen route tables: {Style.RESET_ALL}")
                    print('\n')
                    for result in results:
                        print(f"{Fore.CYAN}{result}: {results[result]}{Style.RESET_ALL}")
                        print('\n')
            elif action == "replace":
                replace_routes()



def modify_rt():
    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to modify route table routes{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe the route tables in the chosen VPC
    existing_route_tables, _ = describe_rt(vpcRegion, filtername='vpc-id', filterID=vpcID)

    # Select the route tables(s) that you want to change their routes
    rtsMessage = f"{Fore.LIGHTBLUE_EX}Select the route table(s) that you want to change their routes{Style.RESET_ALL}"
    selected_route_tables = select_rts(rtsMessage, existing_route_tables)

    # Choose the type of operation you want to do with the route table routes
    resourceMessage = f"{Fore.LIGHTBLUE_EX}Choose the type of operation you want to do with the routes of the selected route table(s){Style.RESET_ALL}"
    operation = modify_resource(resourceMessage)

    if operation == "create an entry":
        action = "create"
    elif operation == "replace an entry":
        action = "replace"
    create_routes(vpcRegion, vpcID, existing_route_tables, selected_route_tables, action)



def launch_ec2_instances(bastion="no"):

    if bastion == "yes":
        instanceLabel = "Bastion Host"
        finalMessage = f"{Fore.MAGENTA}Bastion host and a security group have been created, and SSH connection is opened both on network ACL and security group.{Style.RESET_ALL}"
        sgMessage = f"{Fore.LIGHTBLUE_EX}Do you need to create a new security group or attach an existing one? Security group will have SSH open to your local machine{Style.RESET_ALL}"
    else:
        instanceLabel = "EC2 Instance"
        finalMessage = f"{Fore.MAGENTA}EC2 instance has been created. For necessary traffic arrangements, you should create and/or modify security group and network ACL.{Style.RESET_ALL}"
        sgMessage = f"{Fore.LIGHTBLUE_EX}Do you need to create a new security group or attach an existing one?{Style.RESET_ALL}"

    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to launch the{Style.RESET_ALL} {Fore.RED}{instanceLabel}{Style.RESET_ALL}"
    vpcName, vpcRegion, vpcID = select_vpc(vpcMessage)
    print('\n')

    # Describe the subnets
    subnets, _, _ = describe_subnets(vpcID, vpcRegion)

    # Create a key pair if necessary
    keyPairMessage = input(f"{Fore.LIGHTBLUE_EX}Do you need to create a key pair? (y/N): {Style.RESET_ALL}")
    print('\n')
    if keyPairMessage == "y" or keyPairMessage == "Y":
        key_pairs = describe_key_pairs(vpcRegion)
        key_names = [x['KeyName'] for x in key_pairs]
        keyPairSequenceNo = find_sequence_number(key_names)
        keyName = vpcName + "-kp-" + str(keyPairSequenceNo)
        response = boto3.client('ec2', region_name = vpcRegion).create_key_pair(
            KeyName=keyName,
        )
        keyMaterial = response['KeyMaterial']

        # Save the key pair to the local disk
        path = input(f"{Fore.LIGHTBLUE_EX}Type the path where the key pair will be saved locally, e.g. /main_dir/sub_dir/sub_dir2/.../: {Style.RESET_ALL}")
        print('\n')
        fileName = keyName
        completeName = os.path.join(path, fileName+".pem")
        fileSaved = open(completeName, "w")
        fileSaved.write(keyMaterial)
        fileSaved.close()
        os.chmod(completeName, 0o400)
    else:
        path = input(f"{Fore.LIGHTBLUE_EX}Type the path where the key pair is located on the local machine, e.g. /main_dir/sub_dir/sub_dir2/.../: {Style.RESET_ALL}")
        print('\n')
        files = os.listdir(path)
        key_pairs = []
        for f in files:
            key_pairs.append(f)
        if '.DS_Store' in key_pairs:
            key_pairs.remove('.DS_Store')
        message = f"{Fore.LIGHTBLUE_EX}Select the regional key pair{Style.RESET_ALL}"
        questions = [
        inquirer.List('key-pair',
                        message=message,
                        choices=key_pairs
                        ),
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        keyName = answers['key-pair']
        print('\n')
        completeName = os.path.join(path, keyName)

    # Describe the public subnets 
    public_subnets = {}
    for key, value in subnets.items():
        if value[3] == "Pub":
            public_subnets[key] = value

    if not public_subnets:
        input_message = input(f"{Fore.LIGHTBLUE_EX}There is no public subnet at the moment. Shall we add one? (y/N): {Style.RESET_ALL}")
        print('\n')
        if input_message == "y" or input_message == "Y":
            add_subnet()
        else:
            exit_script()

    # Select the public subnet where the bastion host / EC2 instance will be launched
    subnetMessage = f"{Fore.LIGHTBLUE_EX}Select the subnet where the{Style.RESET_ALL} {Fore.RED}{instanceLabel}{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}will be launched.{Style.RESET_ALL}"
    print('\n')
    selectedSubnet = select_subnets(subnetMessage, public_subnets if bastion == "yes" else subnets, string="List")
    selectedSubnetID = selectedSubnet[1]

    # Describe the existing security groups in the chosen VPC
    security_groups = describe_sg(vpcRegion, vpcID)
    security_group_names = list(security_groups.keys())

    # Create a new security group or attach an existing one    
    questions = [
        inquirer.List('sg',
                        message=sgMessage,
                        choices=['create a security group', 'attach a security group']
                        ),
        ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    sgAnswer = answers['sg']
    print('\n')

    # Local public ip
    publicIP = get('https://api.ipify.org').text + "/32"
    sgRuleFor22 = 'entry'

    if sgAnswer == "create a security group":
        # Create a specific security group for the bastion host
        sgSequenceNo = find_sequence_number(security_group_names)
        securityGroupName = vpcName + "." + instanceLabel.replace(" ", "") + ".sg-" + str(sgSequenceNo) 
        response = boto3.client('ec2', region_name = vpcRegion).create_security_group(
            Description="security group for the" + instanceLabel,
            GroupName=securityGroupName,
            VpcId=vpcID,
            TagSpecifications=[
                {
                    'ResourceType':'security-group',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': securityGroupName
                        },
                    ]
                },
            ],
        )
        print('\n')
        sgID = response['GroupId']
    elif sgAnswer == "attach a security group":
        asgMessage = f"{Fore.LIGHTBLUE_EX}Select the security group that will be attached to the instance{Style.RESET_ALL}"
        questions = [
            inquirer.List('sgs',
                            message=asgMessage,
                            choices=security_group_names
                            ),
            ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        selected_security_group = answers['sgs']
        print('\n')
        sgID = security_groups[selected_security_group]

        # Describe the traffic rules of the chosen security group
        response = boto3.client('ec2', region_name = vpcRegion).describe_security_groups(
            Filters=[
                {
                    'Name': 'group-id',
                    'Values': [
                        sgID,
                    ]
                },
            ],
        )
        ipPermissions = response['SecurityGroups'][0]['IpPermissions']
        for ipPermission in ipPermissions:
            try:
                if ipPermission['FromPort'] == 22 and ipPermission['ToPort'] == 22:
                    ip_ranges = ipPermission['IpRanges']
                    for ip_range in ip_ranges:
                        if ip_range['CidrIp'] == publicIP:
                            sgRuleFor22 = 'no entry'
            except:
                pass

    # Make some security arrangements for the bastion host in particular
    if bastion == "yes":
        if sgRuleFor22 == 'entry':

            # Open the SSH inbound traffic of the security group for the local IP
            boto3.client('ec2', region_name = vpcRegion).authorize_security_group_ingress(
                GroupId=sgID,
                IpPermissions=[
                    {
                        'FromPort': 22,
                        'IpProtocol': 'tcp',
                        'IpRanges': [
                            {
                                'CidrIp': publicIP,
                                'Description': 'SSH access from the local machine',
                            },
                        ],
                        'ToPort': 22,
                    },
                ],
            )

        # Find the network ACL of the subnet in which bastion host will be launched
        existing_nacls = describe_network_acls(vpcRegion, filterName='association.subnet-id', filterID=selectedSubnetID)
        naclID = [value[0] for key, value in existing_nacls.items()][0]

        # Find the next rule numbers for the inbound and outbound traffic
        igressRuleNumber, egressRuleNumber = find_rule_number(vpcRegion, naclID)
        igressRuleNumber += 100
        egressRuleNumber += 100

        # Create an igress rule for SSH connection from the local machine
        boto3.client('ec2', region_name = vpcRegion).create_network_acl_entry(
            CidrBlock=publicIP,
            Egress=False,
            NetworkAclId=naclID,
            PortRange={
                'From': 22,
                'To': 22
            },
            Protocol='6',
            RuleAction='allow',
            RuleNumber=igressRuleNumber
        )

        # Create an egress rule for SSH connection from the local machine
        boto3.client('ec2', region_name = vpcRegion).create_network_acl_entry(
            CidrBlock=publicIP,
            Egress=True,
            NetworkAclId=naclID,
            PortRange={
                'From': 22,
                'To': 22
            },
            Protocol='6',
            RuleAction='allow',
            RuleNumber=egressRuleNumber
        )

    # Describe the instances in the selected subnet
    try:
        existing_instances = describe_instances(vpcRegion, vpcID, selectedSubnetID)
        existing_instance_names = list(existing_instances.keys())
    except:
        existing_instance_names = ["I0"]

    # Get the instance sequence number
    instanceSequenceNo = find_sequence_number(existing_instance_names)

    # Name the bastion host / EC2 instance
    newInstanceLabel = instanceLabel.split()[0].lower()
    instanceName = selectedSubnet[0] + "." + newInstanceLabel + "-" + str(instanceSequenceNo)
    keyName = keyName.replace('.pem', "")

    # Enter an AMI
    ami = input(f"{Fore.LIGHTBLUE_EX}Enter a valid AMI for the selected region: {Style.RESET_ALL}")
    print('\n')

    # Launch the bastion host / EC2 instance
    response = boto3.client('ec2', region_name = vpcRegion).run_instances(
        BlockDeviceMappings=[
            {
                'DeviceName': '/dev/xvda',
                'Ebs': {
                    'VolumeSize': 8,
                    'DeleteOnTermination': True,
                    'VolumeType': 'gp2',
                },
            },
        ],
        ImageId=ami,
        InstanceType='t2.micro',
        KeyName=keyName,
        MaxCount=1,
        MinCount=1,
        Placement={
            'Tenancy': 'default'
        },
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
            'SubnetId': selectedSubnetID,    
        },
        ],
        CreditSpecification={
            'CpuCredits': 'standard'
        },
        EbsOptimized=False,
        CapacityReservationSpecification={
            'CapacityReservationPreference': 'open'
        },
        TagSpecifications=[
            {
                'ResourceType': 'instance', 
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': instanceName,
                    },
                ],
            },
            {
                'ResourceType': 'volume', 
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': instanceName,
                    },
                ],
            },
            {
                'ResourceType': 'network-interface', 
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': instanceName,
                    },
                ],
            },
        ],
    )
    instanceID = response['Instances'][0]['InstanceId']

    # Describe the bastion host / EC2 instance
    print(f"{Fore.MAGENTA}Please wait while the {instanceLabel} is being launched...It should take 45 seconds before the full setup.{Style.RESET_ALL}")
    time.sleep(45)
    instanceInfo = describe_instance(vpcRegion, instanceID)
    publicDNS = instanceInfo['PublicDnsName']
    username="ec2-user"
    hostname = username + "@" + publicDNS
    print('\n')
    
    print(finalMessage)
    print('\n')

    if bastion == "yes":
        connectMessage = input(f"{Fore.LIGHTBLUE_EX}Do you need SSH connection to the bastion host now? (y/N): {Style.RESET_ALL}")
        print('\n')
        if connectMessage == "y" or connectMessage == "Y":
            ssh_connect(hostname, completeName)
        else:
            open_menu()



def launch_nat_gw():
    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to launch a NAT gateway{Style.RESET_ALL}"
    vpcName, vpcRegion, vpcID = select_vpc(vpcMessage)
    print('\n')

    # Describe the subnets
    subnets, _, _ = describe_subnets(vpcID, vpcRegion)

    # Describe the public subnets 
    public_subnets = {}
    for key, value in subnets.items():
        if value[3] == "Pub":
            public_subnets[key] = value

    if not public_subnets:
        input_message = input(f"{Fore.LIGHTBLUE_EX}There is no public subnet at the moment. Shall we add one? (y/N): {Style.RESET_ALL}")
        print('\n')
        if input_message == "y" or input_message == "Y":
            add_subnet()
        else:
            exit_script()

    # Select the public subnet where the NAT gateway will be launched
    publicSubnetMessage = f"{Fore.LIGHTBLUE_EX}Choose the public subnet where the NAT gateway will be launched.{Style.RESET_ALL}"
    print('\n')
    selectedSubnet = select_subnets(publicSubnetMessage, public_subnets, string="List")
    selectedSubnetID = selectedSubnet[1]

    # Describe elastic IPs in the chosen VPC
    eips_names = []
    eips = describe_eips(vpcRegion, filterName='domain', filterID='vpc')
    for eip in eips:
        eip_name = eip['Tags'][0]['Value']
        eips_names.append(eip_name)

    # Get a sequence number for the new elastic IP
    eipSequenceNo = find_sequence_number(eips_names)

    # Allocate an elastic IP address
    eipName = vpcName + ".eip-" + str(eipSequenceNo)
    response = boto3.client('ec2', region_name = vpcRegion).allocate_address(
        Domain='vpc',
    )
    allocationID = response['AllocationId']

    # Tag the elastic IP address
    response = boto3.client('ec2', region_name = vpcRegion).create_tags(
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

    # Launch the NAT gateway
    ngwName = selectedSubnet[0] + ".ngw"
    response = boto3.client('ec2', region_name = vpcRegion).create_nat_gateway(
        AllocationId=allocationID,
        SubnetId=selectedSubnetID,
        TagSpecifications=[
            {
                'ResourceType': 'natgateway',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': ngwName
                    },
                ]
            },
        ]
    )
    ngwID = response['NatGateway']['NatGatewayId']

    # Describe the private subnets 
    private_subnets = {}
    for key, value in subnets.items():
        if value[3] == "Pri":
            private_subnets[key] = value

    if not private_subnets:
        input_message = input(f"{Fore.LIGHTBLUE_EX}There is no private subnet at the moment. Shall we add one? (y/N): {Style.RESET_ALL}")
        print('\n')
        if input_message == "y" or input_message == "Y":
            add_subnet()
        else:
            exit_script()

    # Select the private subnets you want to route to the NAT gateway
    privateSubnetMessage = f"{Fore.LIGHTBLUE_EX}Choose the private subnet(s) that you want to connect to the NAT gateway.{Style.RESET_ALL}"
    print('\n')
    selectedPrivateSubnets = select_subnets(privateSubnetMessage, private_subnets, string="Checkbox")

    # Find the route tables of the selected private subnets
    for selectedPrivateSubnet in selectedPrivateSubnets:
        selectedPrivateSubnetID = selectedPrivateSubnet[1]
        _, rtID = describe_rt(vpcRegion, filtername='association.subnet-id', filterID=selectedPrivateSubnetID)

        # Create a route that is connected to the NAT gateway
        try:
            response = boto3.client('ec2', region_name = vpcRegion).create_route(
                DestinationCidrBlock='0.0.0.0/0',
                NatGatewayId=ngwID,
                RouteTableId=rtID,
            )
        except:
            pass
    message = f"{Fore.MAGENTA}NAT gateway{Style.RESET_ALL} {Fore.CYAN}{ngwName}{Style.RESET_ALL} {Fore.MAGENTA}has been created, and the following private subnet(s) have been routed to it: {Style.RESET_ALL}"
    print(message)
    print('\n')
    for selectedPrivateSubnet in selectedPrivateSubnets:
        print(f"{Fore.CYAN}{selectedPrivateSubnet[0]}{Style.RESET_ALL}") 
    print('\n')



def create_vpc_s3_endpoint():

    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to create a VPC gateway S3 endpoint{Style.RESET_ALL}"
    vpcName, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Create an S3 bucket
    now = datetime.now()
    dt_string = now.strftime("%Y-%b-%d-%H-%M-%S")
    bucketName = "s3b-" + dt_string.lower()
    boto3.client('s3', region_name = vpcRegion).create_bucket(
        ACL='private',
        Bucket=bucketName,
        CreateBucketConfiguration={
            'LocationConstraint': vpcRegion
        },
    )
    bucketArn = "arn:aws:s3:::"+bucketName+"/*"

    # Create a policy document
    vpcGatewayEndpointS3PolicyDocument = {
        
            "Version": "2012-10-17",
            "Statement": [
            {
                "Sid": "vpce01",
                "Principal": "*",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",  
                ],
                "Resource": bucketArn
            },
        ]
    }
    vpcGatewayEndpointS3PolicyDocument = json.dumps(vpcGatewayEndpointS3PolicyDocument, indent = 4)

    # Describe route tables
    existing_route_tables, _ = describe_rt(vpcRegion, filtername='vpc-id', filterID=vpcID)

    # Select the route table for VPC endpoint
    rtsMessage = f"{Fore.LIGHTBLUE_EX}Select the route table(s) to connect to the VPC gateway S3 endpoint:{Style.RESET_ALL}"
    selected_route_tables = select_rts(rtsMessage, existing_route_tables)
    route_table_ids = []
    for selected_route_table in selected_route_tables:
        rtID = existing_route_tables[selected_route_table][0]
        route_table_ids.append(rtID)

    # Describe VPC endpoints in the chosen VPC
    vpc_endpoints = describe_vpc_endpoints(vpcRegion, filtername='vpc-id', filterID=vpcID)
    vpcEndpointNames = []
    for vpc_endpoint in vpc_endpoints:
        vpcEndpointName = vpc_endpoint['Tags'][0]['Value']
        vpcEndpointNames.append(vpcEndpointName)

    # Find a sequence number for the VPC endpoint
    vpceSequenceNo = find_sequence_number(vpcEndpointNames)
    vpceName = vpcName + ".vpce-" + str(vpceSequenceNo)

    # Create a VPC gateway S3 endpoint
    boto3.client('ec2', region_name = vpcRegion).create_vpc_endpoint(
        VpcEndpointType='Gateway',
        VpcId=vpcID,
        ServiceName='com.amazonaws.eu-west-1.s3',
        PolicyDocument=vpcGatewayEndpointS3PolicyDocument,
        RouteTableIds=route_table_ids,
        TagSpecifications=[
            {
                'ResourceType': 'vpc-endpoint',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': vpceName
                    },
                ]
            },
        ]
    )
    print(f"{Fore.MAGENTA}VPC gateway S3 endpoint{Style.RESET_ALL} {Fore.CYAN}{vpceName}{Style.RESET_ALL} {Fore.MAGENTA}and S3 bucket{Style.RESET_ALL} {Fore.CYAN}{bucketName}{Style.RESET_ALL} {Fore.MAGENTA}has been successfully created.{Style.RESET_ALL}")
    print('\n')



# Describe the VPCs in a given region
def describe_vpcs(selected_region):
    response = boto3.client('ec2', region_name = selected_region).describe_vpcs()
    vpcs = response['Vpcs']
    for vpc in vpcs:
        try:
            vpcName = vpc['Tags'][0]['Value']
            vpcID = vpc['VpcId']
            cidrBlock = vpc['CidrBlock']
            vpcCidrBlock = re.findall(r'([0-9]{1,3}[.][0-9]{1,3}[.])', cidrBlock)[0]
            vpc_to_region[vpcName] = selected_region
            vpc_info[vpcName] = vpcID
            vpc_cidr_block[vpcName] = vpcCidrBlock
        except:
            pass
    return vpc_to_region, vpc_info, vpc_cidr_block



# Describe network access control lists
def describe_network_acls(vpcRegion, filterName='vpc-id', filterID=0):
    response = boto3.client('ec2', region_name = vpcRegion).describe_network_acls(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterID
                ]
            },
        ],
    )
    network_acls = response['NetworkAcls']
    existing_nacls = {}
    for network_acl in network_acls:
        nacl_data = []
        associations = []
        isDefault = network_acl['IsDefault']
        networkACLID = network_acl['NetworkAclId']
        try:
            networkACLName = network_acl['Tags'][0]['Value']
        except:
            networkACLName = "default"
        naclAssociations = network_acl['Associations'] 
        rule_entries = network_acl['Entries']
        for naclAssociation in naclAssociations: 
            networkACLAssociationID = naclAssociation['NetworkAclAssociationId']
            subnetID = naclAssociation['SubnetId']
            associations.append({subnetID: networkACLAssociationID})
        nacl_data = [networkACLID, associations, rule_entries, isDefault]
        existing_nacls[networkACLName] = nacl_data
    return existing_nacls



# Describe the existing subnets in the chosen VPC
def describe_subnets(vpcID, vpcRegion):
    try:
        subnets = {}
        response = boto3.client('ec2', region_name = vpcRegion).describe_subnets(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [
                        vpcID,
                    ]
                },
            ],
        )

    # Get full subnet information
    
        numberOfSubnets = len(response['Subnets'])
        for i in range(numberOfSubnets):
            subnet_info = []
            subnetName = response['Subnets'][i]['Tags'][0]['Value']
            subnetID = response['Subnets'][i]['SubnetId']
            subnetCidrBlock = response['Subnets'][i]['CidrBlock']
            az = response['Subnets'][i]['AvailabilityZone']
            subnetType = re.findall(r'[.][A-Z]{1}[a-z]{2}', subnetName)[0].replace(".", "")
            subnet_info.extend([subnetName, subnetID, subnetCidrBlock, subnetType, az])
            subnets[i+1] = subnet_info

            # Get public and private subnets separately for the numeration purpose
            public_subnet_names = [value[0] for key, value in subnets.items() if value[3] == "Pub"]
            private_subnet_names = [value[0] for key, value in subnets.items() if value[3] == "Pri"]
        return subnets, public_subnet_names, private_subnet_names
    except:
        pass


# Describe the existing network interfaces in the chosen VPC
def describe_network_interfaces(vpcID, vpcRegion):
    response = boto3.client('ec2', region_name = vpcRegion).describe_network_interfaces()
    network_interfaces = response['NetworkInterfaces']
    network_interface_security_groups = {}
    existing_network_interfaces = {}
    for network_interface in network_interfaces:
        networkInterfaceID = network_interface['NetworkInterfaceId']
        networkInterfaceName = network_interface['TagSet'][0]['Value']
        networkInterfaceVPCID = network_interface['VpcId']
        networkInterfaceSecurityGroups = network_interface['Groups']
        if networkInterfaceVPCID == vpcID:
            existing_network_interfaces[networkInterfaceName] = networkInterfaceID
            network_interface_security_groups[networkInterfaceName] = networkInterfaceSecurityGroups
    return existing_network_interfaces, network_interface_security_groups


# Describe the existing security groups in the chosen VPC
def describe_sg(vpcRegion, vpcID):
    response = boto3.client('ec2', region_name = vpcRegion).describe_security_groups(
        Filters=[
            {
                'Name': 'vpc-id',
                'Values': [
                    vpcID,
                ]
            },
        ],
    )
    existing_security_groups = response['SecurityGroups']
    security_groups = {}
    for security_group in existing_security_groups:
        sgName = security_group['GroupName']
        sgId = security_group['GroupId']
        security_groups[sgName] = sgId
    return security_groups



# Describe existing route tables in the chosen VPC
def describe_rt(vpcRegion, filtername='vpc-id', filterID=0):
    existing_route_tables = {}
    response = boto3.client('ec2', region_name = vpcRegion).describe_route_tables(
        Filters=[
            {
                'Name': filtername,
                'Values': [
                    filterID,
                ]
            },
        ],
    )
    rt_tables = response['RouteTables']
    mainRTID = rt_tables[0]['RouteTableId']
    for rt in rt_tables:
        rt_info = []
        rtID = rt['RouteTableId']
        rtName = rt['Tags'][0]['Value']
        rtAssociations = rt['Associations']
        routes = rt['Routes']
        assoc_info = []
        for association in rtAssociations:
            try:
                rtAssociationID = association['RouteTableAssociationId']
            except:
                rtAssociationID = None
            try:
                assoc_info.append(rtAssociationID)
            except:
                pass
        rt_info.extend([rtID, assoc_info, routes])
        existing_route_tables[rtName] = rt_info
    return existing_route_tables, mainRTID 



# Describe the existing internet gateway in the chosen VPC
def describe_igw(vpcRegion, deleteVPCID):
    response = boto3.client('ec2', region_name = vpcRegion).describe_internet_gateways(
    Filters=[
        {
            'Name': 'attachment.vpc-id',
            'Values': [
                deleteVPCID,
            ]
        },
    ],
)
    igwID = response['InternetGateways'][0]['InternetGatewayId']
    return igwID



# Describe key pairs in a particular region
def describe_key_pairs(vpcRegion):
    response = boto3.client('ec2', region_name = vpcRegion).describe_key_pairs()
    key_pairs = response['KeyPairs']
    return key_pairs



# Describe NAT gateways in a particular VPC
def describe_ngw(vpcRegion, vpcID):
    response = boto3.client('ec2', region_name = vpcRegion).describe_nat_gateways(
        Filters=[
            {
                'Name': 'vpc-id',
                'Values': [
                    vpcID,
                ]
            },
        ],
    )
    nat_gateways = response['NatGateways']
    return nat_gateways



# Describe VPC endpoints in a particular VPC
def describe_vpc_endpoints(vpcRegion, filtername='vpc-id', filterID=0):
    response = boto3.client('ec2', region_name = vpcRegion).describe_vpc_endpoints(
        Filters=[
            {
                'Name': filtername,
                'Values': [
                    filterID,
                ]
            },
        ],
    )
    vpc_endpoints = response['VpcEndpoints']
    return vpc_endpoints



# Describe instances in a particular VPC
def describe_instances(vpcRegion, vpcID, subnetID):
    existing_instances = {}
    response = boto3.client('ec2', region_name = vpcRegion).describe_instances(
        Filters=[
            {
                'Name': 'vpc-id',
                'Values': [
                    vpcID,
                ]
            },
            {
                'Name': 'subnet-id',
                'Values': [
                    subnetID,
                ]    
            },
        ],
    )

    instances = response['Reservations'][0]['Instances']
    for instance in instances:
        instanceName = instance['Tags'][0]['Value']
        instanceID = instance['InstanceId']
        existing_instances[instanceName] = instanceID
    return existing_instances



# Describe a specific instance
def describe_instance(vpcRegion, instanceID):
    response = boto3.client('ec2', region_name = vpcRegion).describe_instances(
        Filters=[
            {
                'Name': 'instance-id',
                'Values': [
                    instanceID,
                ]
            },
        ],
    )
    instanceInfo = response['Reservations'][0]['Instances'][0]
    return instanceInfo



# Describe elastic IP adresses
def describe_eips(vpcRegion, filterName='domain', filterID='vpc'):
    response = boto3.client('ec2', region_name = vpcRegion).describe_addresses(
        Filters=[
            {
                'Name': filterName,
                'Values': [
                    filterID,
                ]
            },
        ],
    )
    eips = response['Addresses']
    return eips



def describe_ports():
    traffic = ["Inbound", "Outbound"]

    # type: [protocol, port_range]
    type_and_ports = {
        'All traffic': [-1, None], 
        'Custom Protocol': ['$', None], 
        'Custom TCP': [6, '$'],
        'Custom UDP': [17, '$'], 
        'All TCP': [6, None], 
        'All UDP': [17, None], 
        'All ICMP - IPv4': [1, None],
        'SSH': [6, 22], 
        'telnet': [6, 23], 
        'SMTP': [6, 25], 
        'nameserver': [6, 42],
        'DNS (TCP)': [6, 53],
        'DNS (UDP)': [17, 53],
        'HTTP': [6, 80], 
        'POP3': [6, 110],
        'IMAP': [6, 143], 
        'LDAP': [6, 389], 
        'HTTPS': [6, 443], 
        'SMB': [6, 445], 
        'SMTPS': [6, 465], 
        'IMAPS': [6, 993],
        'POP3S': [6, 995],
        'MS SQL': [6, 1433], 
        'Oracle': [6, 1521],
        'NFS': [6, 2049],
        'MySQL/Aurora': [6, 3306],
        'RDP': [6, 3389],
        'PostgreSQL': [6, 5432],
        'Redshift': [6, 5439],
        'WinRM-HTTP': [6, 5985],
        'WinRM-HTTPS': [6, 5986],
        'HTTP*': [6, 8080],
        'HTTPS*': [6, 8443],
        'Elastic Graphics': [6, 2007]
        }
    return traffic, type_and_ports



# Find a sequence number for a resource
def find_sequence_number(name_list):
    natural_sequence_numbers = list(range(1, 100_000))
    sequence_numbers_list = []
    for name in name_list:
        try: 
            searchNumber = re.search(r"[0-9]+$", name).group()
            sequence_numbers_list.append(int(searchNumber))
        except:
            pass
    for number in sequence_numbers_list:
        if number in natural_sequence_numbers:
            natural_sequence_numbers.remove(number)
    currentSequenceNo = min(natural_sequence_numbers)
    return currentSequenceNo 



def find_rule_number(vpcRegion, naclID):
    # Get the existing network ACL entries
    existing_nacls = describe_network_acls(vpcRegion, filterName='network-acl-id', filterID=naclID)
    rule_entries = [value[2] for key, value in existing_nacls.items()]
    rule_entries = rule_entries[0]

    # Calculate the next rule numbers for inbound and outbound traffic
    inbound_rule_numbers = [100]
    outbound_rule_numbers = [100]
    for rule_entry in rule_entries:
        egress = rule_entry['Egress']
        ruleNumber = rule_entry['RuleNumber']
        if egress == False:
            inbound_rule_numbers.append(ruleNumber)
        if egress == True:
            outbound_rule_numbers.append(ruleNumber)
        new_inbound_rule_numbers = list(filter(lambda x: x <= 32000, inbound_rule_numbers))
        new_outbound_rule_numbers = list(filter(lambda y: y <= 32000, outbound_rule_numbers))
        maxInboundRuleNumber = max(new_inbound_rule_numbers)
        maxOutboundRuleNumber = max(new_outbound_rule_numbers)
        nextInboundRuleNumber = maxInboundRuleNumber 
        nextOutboundRuleNumber = maxOutboundRuleNumber
    return nextInboundRuleNumber, nextOutboundRuleNumber



def define_and_create_rule(existing_nacls, selected_nacls, vpcRegion):

    # Create the rule
    def create_rules(rules_dict, nextInboundRuleNumber, nextOutboundRuleNumber):
        all_entries = []
        protocol = type_and_ports[traffic_type][0]
        port = type_and_ports[traffic_type][1]
        if protocol == "$":
            protocol = input(f"{Fore.LIGHTBLUE_EX}Enter a protocol number: {Style.RESET_ALL}")
        if port == "$":
            port = input(f"{Fore.LIGHTBLUE_EX}Enter a port number: {Style.RESET_ALL}")
        for rule in rules_dict:
            ips = rules_dict[rule]
            for ip in ips:
                if selected_traffic == "Inbound":
                    egressValue = False
                    nextInboundRuleNumber += 100
                    ruleNumber = nextInboundRuleNumber
                else:
                    egressValue = True
                    nextOutboundRuleNumber += 100
                    ruleNumber = nextOutboundRuleNumber
                boto3.client('ec2', region_name = vpcRegion).create_network_acl_entry(
                CidrBlock=ip,
                Egress=egressValue,
                NetworkAclId=naclID,
                PortRange={
                    'From': port,
                    'To': port
                },
                Protocol=str(protocol),
                RuleAction=rule,
                RuleNumber=ruleNumber
            )
                entry = str(ruleNumber) + " " + rule.upper() + " " + ip
                all_entries.append(entry)
        return all_entries, nextInboundRuleNumber, nextOutboundRuleNumber


   # Enter IP addresses for each type of traffic to allow or deny
    def define_rules(nextInboundRuleNumber, nextOutboundRuleNumber):
        rules_dict = {}
        rules_dict['allow'] = []
        rules_dict['deny'] = []
        for rule in rules_dict:
            ipAddresses = input(f"{Fore.LIGHTBLUE_EX}Enter IP address(es) to{Style.RESET_ALL} {Fore.RED}{rule}{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}for{Style.RESET_ALL} {Fore.RED}{selected_traffic} {traffic_type}{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}traffic: {Style.RESET_ALL}")
            print('\n')
            if ipAddresses:
                rule_list = ipAddresses.replace(" ", "").split(",")
                rules_dict[rule] = rule_list
        return create_rules(rules_dict, nextInboundRuleNumber, nextOutboundRuleNumber)


    traffic, type_and_ports = describe_ports()
    all_nacls = {}
    for selected_nacl in selected_nacls:
        naclID = existing_nacls[selected_nacl][0]
        nextInboundRuleNumber, nextOutboundRuleNumber = find_rule_number(vpcRegion, naclID)
 
        # Decide inbound and/or outbound rules
        print(f"{Fore.LIGHTBLUE_EX}Define inbound and outbound rules for{Style.RESET_ALL}{Fore.RED} {selected_nacl}{Style.RESET_ALL}")
        print('\n')
        trafficMessage = f"{Fore.LIGHTBLUE_EX}Select{Style.RESET_ALL}{Fore.RED} inbound{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}and/or{Style.RESET_ALL}{Fore.RED} outbound{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}options to define rules{Style.RESET_ALL}"
        questions = [
            inquirer.Checkbox('traffic',
                            message=trafficMessage,
                            choices=traffic
                            ),
            ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        selected_traffics = answers['traffic']
        print('\n')
 
        # Choose the traffic types for inbound and outbound traffic
        traffics_dict = {}
        for selected_traffic in selected_traffics:
            types = list(type_and_ports.keys())
            typeMessage = f"{Fore.LIGHTBLUE_EX}Select the type of{Style.RESET_ALL} {Fore.RED}{selected_traffic}{Style.RESET_ALL} {Fore.LIGHTBLUE_EX}traffic{Style.RESET_ALL}"
            questions = [
                inquirer.Checkbox('type',
                                message=typeMessage,
                                choices=types
                                ),
                ]
            answers = inquirer.prompt(questions, theme=GreenPassion())
            traffic_types = answers['type']

            # Put all together
            for traffic_type in traffic_types:
                key = "For " + selected_nacl + ", " + selected_traffic + " " + traffic_type + " traffic rules have been defined as follows: "
                all_entries, nextInboundRuleNumber, nextOutboundRuleNumber = define_rules(nextInboundRuleNumber, nextOutboundRuleNumber)
                value = all_entries
                traffics_dict[key]  = value
        all_nacls[selected_nacl] = traffics_dict
    return all_nacls 



# Exit the program
def exit_script():
    return sys.exit()



def check_rt_association(vpcRegion, selectedSubnetID, routeTableID):
    response = boto3.client('ec2', region_name = vpcRegion).describe_route_tables(
        Filters=[
            {
                'Name': 'association.subnet-id',
                'Values': [
                    selectedSubnetID,
                ]
            },
        ],
    )
    try:
        routeTableAssociationId = response['RouteTables'][0]['Associations'][0]['RouteTableAssociationId']
    except:
        routeTableAssociationId = None
    if routeTableAssociationId:
        replace_rt(vpcRegion, routeTableAssociationId, routeTableID)
    else:
        boto3.client('ec2', region_name = vpcRegion).associate_route_table(
            RouteTableId=routeTableID,
            SubnetId=selectedSubnetID
        )



def check_sg_attachment():
    # Decide if the security group will replace or be added to the current security groups attached
    message = f"{Fore.LIGHTBLUE_EX}Will the security group replace the other currently attached security groups or be attached to the network interface in addition to them?{Style.RESET_ALL}"
    questions = [
    inquirer.List('sg',
                    message=message,
                    choices=['replace', 'add', 'exit']
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    chosenAction = answers['sg']
    if chosenAction == "exit":
        exit_script()
    return chosenAction



# Choose the vpc in which you want to operate
def select_vpc(vpcMessage):
    questions = [
    inquirer.List('vpcs',
                    message=vpcMessage,
                    choices=vpc_list
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    vpcName = answers['vpcs']
    vpcRegion = vpc_to_region[vpcName]
    vpcID = vpc_info[vpcName]
    return vpcName, vpcRegion, vpcID



# Choose the vpcs in which you want to operate
def select_vpcs(vpcsmessage):
    questions = [
    inquirer.Checkbox('vpcs',
                    message=vpcsmessage,
                    choices=vpc_list
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_vpcs = answers['vpcs']
    return selected_vpcs



# Decide to create a new resource or use an existing one
def new_or_existing(resourceMessage):
    option_list = ['new', 'existing', 'exit']
    questions = [
    inquirer.List('resource',
                    message=resourceMessage,
                    choices=option_list
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    givenAnswer = answers['resource']
    if givenAnswer == "exit":
        exit_script()
    return givenAnswer



# Choose the subnets on which you want to operate
def select_subnets(subnetMessage, subnets, string="Checkbox"):
    if string == "Checkbox":
        questions = [
        inquirer.Checkbox('sub',
                        message=subnetMessage,
                        choices=list(subnets.values())
                        ),
        ]
    else:
        questions = [
        inquirer.List('sub',
                        message=subnetMessage,
                        choices=list(subnets.values())
                        ),
        ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_subnets = answers['sub']
    return selected_subnets



# Select the EC2 instance you want to work on
def select_instance(instanceMessage, existing_instances, string="Checkbox"):
    if string == "Checkbox":
        questions = [
        inquirer.Checkbox('instance',
                        message=instanceMessage,
                        choices=list(existing_instances.keys())
                        ),
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
    else:
        questions = [
        inquirer.List('instance',
                        message=instanceMessage,
                        choices=list(existing_instances.keys())
                        ),
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_instance = answers['instance']
    return selected_instance



# Select NAT gateways you want to work on
def select_ngw(ngwMessage, ngws):
    questions = [
    inquirer.List('ngws',
                    message=ngwMessage,
                    choices=list(ngws.keys())
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_ngw = answers['ngws']
    return selected_ngw



# Select VPC endpoints you want to work on
def select_vpc_endpoint(vpcEndpointMessage, vpc_endpts, string="Checkbox"):

    if string == "Checkbox":
        questions = [
        inquirer.Checkbox('vpcendp',
                        message=vpcEndpointMessage,
                        choices=list(vpc_endpts.keys())
                        ),
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
    else:
        questions = [
        inquirer.List('vpcendp',
                        message=vpcEndpointMessage,
                        choices=list(vpc_endpts.keys())
                        ),
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_vpc_endpoint = answers['vpcendp']
    return selected_vpc_endpoint



# Select the route tables you want to operate on
def select_rts(rtsMessage, existing_route_tables):
    questions = [
    inquirer.Checkbox('rt',
                    message=rtsMessage,
                    choices=list(existing_route_tables.keys())
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_route_tables = answers['rt']
    return selected_route_tables



# Select the route tables you want to operate on
def select_rt(rtMessage, existing_route_tables):
    questions = [
    inquirer.List('rt',
                    message=rtMessage,
                    choices=list(existing_route_tables.keys())
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    rt = answers['rt']
    return rt



# Select the network access control list you want to operate on
def select_nacls(naclMessage, existing_nacls, string="Checkbox"):
    nacl_list = list(existing_nacls.keys())
    if string == "List":
        questions = [
        inquirer.List('nacl',
                        message=naclMessage,
                        choices=nacl_list
                        ),
        ]
    else:
        questions = [
        inquirer.Checkbox('nacl',
                        message=naclMessage,
                        choices=nacl_list
                        ),
        ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_nacls = answers['nacl']
    return selected_nacls



# Select the network access control list entries you want to work on
def select_nacl_entries(vpcRegion, naclID, naclEntryMessage):
    existing_nacls = describe_network_acls(vpcRegion, filterName='network-acl-id', filterID=naclID)
    rule_entries = [value[2] for key, value in existing_nacls.items()]
    rule_entries = rule_entries[0]

    questions = [
    inquirer.Checkbox('entry',
                    message=naclEntryMessage,
                    choices=rule_entries
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_nacl_entries = answers['entry']
    return selected_nacl_entries



# Select the network interfaces you want to operate on
def select_ni(niMessage, existing_network_interfaces):
    option_list = list(existing_network_interfaces.keys())
    questions = [
    inquirer.Checkbox('ni',
                    message=niMessage,
                    choices=option_list
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_network_interfaces = answers['ni']
    return selected_network_interfaces



# Select the security group you want to operate on
def select_sg(sgMessage, security_groups):
    option_list = list(security_groups.keys())
    questions = [
        inquirer.Checkbox('sgs',
                        message=sgMessage,
                        choices=option_list
                        ),
        ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_security_groups = answers['sgs']
    print('\n')
    return selected_security_groups



def select_sg_rules(vpcRegion, sgID, selected_security_group):
    ingress_rules = []
    egress_rules = []
    sg_rules_and_message_dict = {}
    sg_selected_rules_dic = {}
    
    response = boto3.client('ec2', region_name = vpcRegion).describe_security_groups(
        Filters=[
            {
                'Name': 'group-id',
                'Values': [
                    sgID,
                ]
            },
        ],
    )

    ingress_rule_entries = response['SecurityGroups'][0]['IpPermissions']
    egress_rule_entries = response['SecurityGroups'][0]['IpPermissionsEgress']

    for ingress_rule_entry in ingress_rule_entries:
        port = ingress_rule_entry['FromPort']
        protocol = ingress_rule_entry['IpProtocol']
        ip_ranges = ingress_rule_entry['IpRanges']
        for ip_range in ip_ranges:
            ingress_rule_entry_record = {}
            ingress_rule_entry_record['Cidr'] = ip_range['CidrIp']
            ingress_rule_entry_record['Port'] = port
            ingress_rule_entry_record['Protocol'] = protocol
            ingress_rules.append(ingress_rule_entry_record)
    for egress_rule_entry in egress_rule_entries:
        try:
            port = egress_rule_entry['FromPort']
        except:
            port = ""
        protocol = egress_rule_entry['IpProtocol']
        ip_ranges = egress_rule_entry['IpRanges']
        for ip_range in ip_ranges:
            egress_rule_entry_record = {}
            egress_rule_entry_record['Cidr'] = ip_range['CidrIp']
            egress_rule_entry_record['Port'] = port
            egress_rule_entry_record['Protocol'] = protocol
            egress_rules.append(egress_rule_entry_record)

    inboundMessage = "inbounde"+f"{Fore.LIGHTBLUE_EX}Select the security group inbound rule(s) you want to delete in{Style.RESET_ALL} {Fore.RED}{selected_security_group}{Style.RESET_ALL}{Fore.LIGHTBLUE_EX}. Press Enter to skip it.{Style.RESET_ALL}"
    outboundMessage = "outbound"+f"{Fore.LIGHTBLUE_EX}Select the security group outbound rule(s) you want to delete in{Style.RESET_ALL} {Fore.RED}{selected_security_group}{Style.RESET_ALL}{Fore.LIGHTBLUE_EX}. Press Enter to skip it.{Style.RESET_ALL}"
    sg_rules_and_message_dict[inboundMessage] = ingress_rules
    sg_rules_and_message_dict[outboundMessage] = egress_rules

    for key, value in sg_rules_and_message_dict.items():
        questions = [
        inquirer.Checkbox('rule',
                        message=key[13:],
                        choices=value
                        ),
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        selected_sg_rules = answers['rule']
        newKey = key[:9].replace("\x1b", "").replace("e", "")
        sg_selected_rules_dic[newKey] = selected_sg_rules
    return sg_selected_rules_dic



# Select network ACL or security group operation to modify its entries
def modify_resource(message):
    questions = [
    inquirer.List('entry',
                    message=message,
                    choices=['create an entry', 'replace an entry', 'exit']
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    operation = answers['entry']
    if operation == "exit":
        exit_script()
    return operation



def choose_from_list(inputList):
    message = f"{Fore.LIGHTBLUE_EX}Choose from the list: {Style.RESET_ALL}"
    questions = [
    inquirer.List('choose',
                    message=message,
                    choices=inputList
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    result_list = answers['choose']
    return result_list



def replace_rt(vpcRegion, assocID, routeTableID):
    try:
        boto3.client('ec2', region_name = vpcRegion).replace_route_table_association(
        AssociationId=assocID,
        RouteTableId=routeTableID
       )
    except:
        pass



def replace_nacl(vpcRegion, assocID, naclID):
    try:
        boto3.client('ec2', region_name = vpcRegion).replace_network_acl_association(
            AssociationId=assocID,
            NetworkAclId=naclID
        )
    except:
        pass



def replace_sg(vpcRegion, selected_network_interfaces, existing_network_interfaces, securityGroupID):
    for network_interface in selected_network_interfaces:
        try:
            networkInterfaceID = existing_network_interfaces[network_interface]
            boto3.client('ec2', region_name = vpcRegion).modify_network_interface_attribute(
                Groups=securityGroupID,
                NetworkInterfaceId=networkInterfaceID
            )
        except:
            pass



def add_sg(vpcRegion, selected_network_interfaces, existing_network_interfaces, securityGroupID):
    for network_interface in selected_network_interfaces:
        try:
            networkInterfaceID = existing_network_interfaces[network_interface]
            response = boto3.client('ec2', region_name = vpcRegion).describe_network_interfaces(
                Filters=[
                    {
                        'Name': 'network-interface-id',
                        'Values': [
                            networkInterfaceID,
                        ]
                    },
                ],
            )
            ni_security_groups = response['NetworkInterfaces'][0]['Groups']
            ni_security_groups_ids = [x['GroupId'] for x in ni_security_groups]
            ni_security_groups_ids.extend(securityGroupID)
            boto3.client('ec2', region_name = vpcRegion).modify_network_interface_attribute(
                Groups=ni_security_groups_ids,
                NetworkInterfaceId=networkInterfaceID
            )
        except:
            pass



def ssh_connect(hostname, completeName='/YOUR_PATH_TO_KEY_PAIR/KEY_PAIR.pem'):
    print(f"{Fore.LIGHTBLUE_EX}You are now connecting to the bastion host...You can run commands on it using the terminal{Style.RESET_ALL}")
    print('\n')
    os.system('clear')
    command = "ssh -i " + completeName + " " + hostname
    os.system(command)



def connect_instance():
    # Choose the vpc in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to work on EC2 instances{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)
    print('\n')

    # Describe the existing subnets in the chosen VPC
    subnets, _, _ = describe_subnets(vpcID, vpcRegion)

    # Choose the subnet in which you want to look for EC2 instances to work with
    subnetMessage = f"{Fore.LIGHTBLUE_EX}Choose the subnet in which you want to look for EC2 instances to work on{Style.RESET_ALL}"
    selected_subnets = select_subnets(subnetMessage, subnets, string="List")
    subnetID = selected_subnets[1]
    print('\n')

    # Describe the existing EC2 instances in the chosen subnet
    existing_instances = describe_instances(vpcRegion, vpcID, subnetID)

    # Select the EC2 instance you want to work on
    instanceMessage = f"{Fore.LIGHTBLUE_EX}Select the EC2 instance you want to work on{Style.RESET_ALL}"
    selected_instance = select_instance(instanceMessage, existing_instances, string="List")
    print('\n')

    # Describe the instance selected
    instanceID = existing_instances[selected_instance]
    instanceInfo = describe_instance(vpcRegion, instanceID)
    publicDNS = instanceInfo['PublicDnsName']
    username="ec2-user"
    hostname = username + "@" + publicDNS

    # SSH connect to the EC2 instance
    path = '/YOUR_PATH_TO_KEY_PAIRS_FOLDER/'
    files = os.listdir(path)
    key_pairs = []
    for f in files:
        key_pairs.append(f)
    if '.DS_Store' in key_pairs:
        key_pairs.remove('.DS_Store')
    message = f"{Fore.LIGHTBLUE_EX}Select the regional key pair{Style.RESET_ALL}"
    questions = [
    inquirer.List('key-pair',
                    message=message,
                    choices=key_pairs
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    keyName = answers['key-pair']
    print('\n')
    completeName = os.path.join(path, keyName)
    ssh_connect(hostname, completeName)



def delete_vpc():

    # Choose the vpcs you want to delete
    print('\n')
    print(f"{Fore.LIGHTBLUE_EX}First, you should make sure that all EC2 instances, bastion hosts and/or NAT gateways deployed in the VPC to be deleted have been terminated already before the deletion.{Style.RESET_ALL}")
    print('\n')
    message = f"{Fore.LIGHTBLUE_EX}Select the VPC(s) you want to delete{Style.RESET_ALL}"
    questions = [
    inquirer.Checkbox('delete_vpc',
                    message=message,
                    choices=vpc_list
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    vpcs = answers['delete_vpc']
    print('\n')

    for vpc in vpcs:
        deleteVPCID = vpc_info[vpc]
        vpcRegion = vpc_to_region[vpc]
        try:
            deleteIGWID = describe_igw(vpcRegion, deleteVPCID)
        except:
            pass

        # Describe and delete the subnets in the chosen VPC
        try:
            subnets, _, _ = describe_subnets(deleteVPCID, vpcRegion)
            for subnet in subnets:
                subnetID = subnets[subnet][1]
                boto3.client('ec2', region_name = vpcRegion).delete_subnet(
                    SubnetId=subnetID
                )
        except:
            pass
        
        # Describe and delete the route tables
        existing_route_tables, _ = describe_rt(vpcRegion, filtername='vpc-id', filterID=deleteVPCID)
        for existing_route_table in existing_route_tables:
            routeTableID = existing_route_tables[existing_route_table][0]
            try:
                boto3.client('ec2', region_name = vpcRegion).delete_route_table(
                    RouteTableId=routeTableID
                )
            except:
                pass

        # Describe and delete the existing security groups
        security_groups = describe_sg(vpcRegion, deleteVPCID)
        for security_group in security_groups:
            sgID = security_groups[security_group]
            try:
                boto3.client('ec2', region_name = vpcRegion).delete_security_group(
                    GroupId=sgID
                )
            except:
                pass

        # Describe and delete the existing network ACLs
        existing_nacls = describe_network_acls(vpcRegion, filterName='vpc-id', filterID=deleteVPCID)
        for existing_nacl in existing_nacls:
            naclID = existing_nacls[existing_nacl][0]
            try:
                boto3.client('ec2', region_name = vpcRegion).delete_network_acl(
                    NetworkAclId=naclID
                )
            except:
                pass

        # Detach and delete the internet gateway
        try:
            boto3.client('ec2', region_name = vpcRegion).detach_internet_gateway(
                InternetGatewayId=deleteIGWID,
                VpcId=deleteVPCID
            )
            boto3.client('ec2', region_name = vpcRegion).delete_internet_gateway(
                InternetGatewayId=deleteIGWID,
            )
        except:
            pass

        # Delete the VPC
        boto3.client('ec2', region_name = vpcRegion).delete_vpc(
            VpcId=deleteVPCID
        )
        print(f"{Fore.MAGENTA}VPC{Style.RESET_ALL} {Fore.RED}{vpc}{Style.RESET_ALL} {Fore.MAGENTA}in region{Style.RESET_ALL} {Fore.RED}{vpcRegion}{Style.RESET_ALL} {Fore.MAGENTA}has been successfully deleted.{Style.RESET_ALL}")
        print('\n')

    # Revise the outstanding regions
    outstanding_regions = []
    for region in regions:
        response = boto3.client('ec2', region_name = region).describe_vpcs()
        if len(response['Vpcs']) > 1:
            outstanding_regions.append(region)
    with open('outstanding_regions.pkl', 'wb') as f:
        pickle.dump(outstanding_regions, f)



def delete_subnet():
    # Choose the VPC in which you want to delete subnets
    subnetMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete subnets{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(subnetMessage)

    # Describe the subnets in the chosen VPC
    subnets, _, _ = describe_subnets(vpcID, vpcRegion)

    # Select the subnets you want to delete
    deleteSubnetMessage = f"{Fore.LIGHTBLUE_EX}Select the subnets you want to delete{Style.RESET_ALL}"
    selected_subnets = select_subnets(deleteSubnetMessage, subnets, string="Checkbox")

    for selected_subnet in selected_subnets:
        boto3.client('ec2', region_name = vpcRegion).delete_subnet(
            SubnetId=selected_subnet[1]
        )
    print(Fore.MAGENTA, "The following subnets have been successfully deleted:", Style.RESET_ALL)
    print('\n')
    for selected_subnet in selected_subnets:
        print(Fore.YELLOW, selected_subnet, Style.RESET_ALL)
        print('\n')
 


def delete_rt():
    # Choose the vpc in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete route table{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe existing route tables in the chosen VPC
    existing_route_tables, _ = describe_rt(vpcRegion, filtername='vpc-id', filterID=vpcID)

    # Select the route tables you want to delete
    rtsMessage = f"{Fore.LIGHTBLUE_EX}Select the route tables you want to delete{Style.RESET_ALL}"
    selected_route_tables = select_rts(rtsMessage, existing_route_tables)

    # Dissociate and delete the route tables
    for selected_route_table in selected_route_tables:
        dissociations = existing_route_tables[selected_route_table][1]
        for associationID in dissociations:
            boto3.client('ec2', region_name = vpcRegion).disassociate_route_table(
                AssociationId=associationID,
            )
        routeTableID = existing_route_tables[selected_route_table][0]
        boto3.client('ec2', region_name = vpcRegion).delete_route_table(
            RouteTableId=routeTableID
        )
    print(f"{Fore.MAGENTA}Selected route tables have been successfully deleted:{Style.RESET_ALL} {Fore.CYAN}{selected_route_tables}{Style.RESET_ALL}")
    print('\n')



def delete_nacl():
    # Choose the vpc in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete network access control list{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe the existing nacls
    existing_nacls = describe_network_acls(vpcRegion, filterName='vpc-id', filterID=vpcID)

    # Select the nacls you want to delete
    naclMessage = f"{Fore.LIGHTBLUE_EX}Select the network access control lists you want to delete{Style.RESET_ALL}"
    print(f"{Fore.LIGHTBLUE_EX}The default network ACL cannot be deleted. So, it is not among the options.{Style.RESET_ALL}")
    print('\n')

    # Get the default network ACL
    for key, value in existing_nacls.items():
        if value[3] == True:
            defaultNaclName = key
            defaultNaclData = value
    
    refined_existing_nacls = existing_nacls.copy()
    del refined_existing_nacls[defaultNaclName]
    selected_nacls = select_nacls(naclMessage, refined_existing_nacls, string="Checkbox")
    refined_existing_nacls[defaultNaclName] = defaultNaclData

    # Delete the selected network access control lists
    for selected_nacl in selected_nacls:
        naclID = existing_nacls[selected_nacl][0]
        associations = existing_nacls[selected_nacl][1]
        if associations:
            assocMessage = f"{Fore.LIGHTBLUE_EX}This network access control list has associations with subnet(s). Select another network ACL to replace it before deletion.{Style.RESET_ALL}"
            del refined_existing_nacls[selected_nacl]
            newNacl = select_nacls(assocMessage, refined_existing_nacls, string="List")
            newNaclID = existing_nacls[newNacl][0]
            for association in associations:
                associationID = list(association.values())[0]
                replace_nacl(vpcRegion, associationID, newNaclID)
        boto3.client('ec2', region_name = vpcRegion).delete_network_acl(
            NetworkAclId=naclID
        )
    print(f"{Fore.MAGENTA}Selected network access control lists have been successfully deleted:{Style.RESET_ALL} {Fore.CYAN}{selected_nacls}{Style.RESET_ALL}")
    print('\n')



def delete_sg():
    # Choose the vpc in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete security group{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe the existing security groups
    security_groups = describe_sg(vpcRegion, vpcID)

    # Select the security groups you want to delete
    sgMessage = f"{Fore.LIGHTBLUE_EX}Select the security groups you want to delete{Style.RESET_ALL}"
    selected_security_groups = select_sg(sgMessage, security_groups)

    # Delete the selected security groups
    for selected_security_group in selected_security_groups:

        # Describe the existing network interfaces in the chosen VPC
        existing_network_interfaces, network_interface_security_groups = describe_network_interfaces(vpcID, vpcRegion)
        sgID = security_groups[selected_security_group]

        # Check if any network interfaces are attached to this security group
        for ni_sg in network_interface_security_groups:
            networkInterfaceID = existing_network_interfaces[ni_sg]
            group_members = [x['GroupId'] for x in network_interface_security_groups[ni_sg]]
            if len(group_members) < 2:
                niMessage = f"{Fore.MAGENTA}The network interface that this security group is attached to has no other security group attachments.\n\nYou should replace the security group before deleting it. Shall we replace it now? (y/N): {Style.RESET_ALL}"
                message = input(niMessage)
                print('\n')
                if message == "y" or message == "Y":
                    all_security_groups = describe_sg(vpcRegion, vpcID)
                    security_groups = {key:val for key, val in all_security_groups.items() if val != group_members[0]}
                    sgMessage = f"{Fore.MAGENTA}Choose security group(s) that will replace the current security group: {Style.RESET_ALL}"
                    print('\n')
                    selected_sg = select_sg(sgMessage, security_groups)
                    securityGroupIDs = [security_groups[security_group] for security_group in selected_sg]
                    add_sg(vpcRegion, ni_sg, existing_network_interfaces, securityGroupIDs)
                else:
                    exit_script()
            if sgID in group_members:
                group_members.remove(sgID)
                try:
                    group_members.extend([x for x in securityGroupIDs if x not in group_members])
                except:
                    pass
                boto3.client('ec2', region_name = vpcRegion).modify_network_interface_attribute(
                    Groups=group_members,
                    NetworkInterfaceId=networkInterfaceID
                )
        boto3.client('ec2', region_name = vpcRegion).delete_security_group(
            GroupId=sgID
        )
    print(Fore.MAGENTA, "Selected security groups have been successfully deleted: ", selected_security_groups, Style.RESET_ALL)
    print('\n')



def delete_nacl_entries():
    # Describe and select a VPC in which you want to work 
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete a network access control list entry{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe the existing network access control lists in the chosen VPC
    existing_nacls = describe_network_acls(vpcRegion, filterName='vpc-id', filterID=vpcID)

    # Select the network access control list you want to operate on
    naclMessage = f"{Fore.LIGHTBLUE_EX}Select the network access control list that you want to delete its entry(s){Style.RESET_ALL}"
    selected_nacls = select_nacls(naclMessage, existing_nacls, string="Checkbox")

    # Select the entries in the chosen network ACLs, which you want to delete
    for selected_nacl in selected_nacls:
        naclID = existing_nacls[selected_nacl][0]
        naclEntryMessage =  f"{Fore.LIGHTBLUE_EX}Select the network access control list entry(s) you want to delete in{Style.RESET_ALL} {Fore.RED}{selected_nacl}{Style.RESET_ALL}"
        selected_nacl_entries = select_nacl_entries(vpcRegion, naclID, naclEntryMessage)
        print('\n')
        print(f"{Fore.MAGENTA}The following network access control list entries in{Style.RESET_ALL} {Fore.RED}{selected_nacl}{Style.RESET_ALL} {Fore.MAGENTA}have been successfully deleted: {Style.RESET_ALL}")
        print("\n")

        # Delete the selected network ACL inbound entries
        for selected_nacl_entry in selected_nacl_entries:
            egressValue = selected_nacl_entry['Egress']
            ruleNumber = selected_nacl_entry['RuleNumber']
            boto3.client('ec2', region_name = vpcRegion).delete_network_acl_entry(
                Egress=egressValue,
                NetworkAclId=naclID,
                RuleNumber=ruleNumber
            )
            print(f"{Fore.YELLOW}{selected_nacl_entry}{Style.RESET_ALL}")
            print('\n')



def delete_sg_rules():
    # Describe and select a VPC in which you want to work 
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete a security group rule{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe the existing security groups in the chosen VPC
    security_groups = describe_sg(vpcRegion, vpcID)

    # Select the security group you want to operate on
    sgMessage = f"{Fore.LIGHTBLUE_EX}Select the security group that you want to delete its rule(s){Style.RESET_ALL}"
    selected_security_groups = select_sg(sgMessage, security_groups)

   # Select the rules in the chosen security groups, which you want to delete
    for selected_security_group in selected_security_groups:
        sgID = security_groups[selected_security_group]
        sg_selected_rules_dic = select_sg_rules(vpcRegion, sgID, selected_security_group)

        if sg_selected_rules_dic["inbound"]:
            print(f"{Fore.MAGENTA}The following security group inbound rules in{Style.RESET_ALL} {Fore.RED}{selected_security_group}{Style.RESET_ALL} {Fore.MAGENTA}have been successfully deleted: {Style.RESET_ALL}")
            print("\n")
            # Delete the selected security group inbound rules
            for sg_rule in sg_selected_rules_dic["inbound"]:
                boto3.client('ec2', region_name = vpcRegion).revoke_security_group_ingress(
                    CidrIp=sg_rule['Cidr'],
                    FromPort=sg_rule['Port'],
                    GroupId=sgID,
                    IpProtocol=sg_rule['Protocol'],
                    ToPort=sg_rule['Port']
                    )
                print(f"{Fore.YELLOW}INBOUND -> {sg_rule}{Style.RESET_ALL}")
                print('\n')

        if sg_selected_rules_dic["outbound"]:
            print(f"{Fore.MAGENTA}The following security group outbound rules in{Style.RESET_ALL} {Fore.RED}{selected_security_group}{Style.RESET_ALL} {Fore.MAGENTA}have been successfully deleted: {Style.RESET_ALL}")
            print("\n")

        # Delete the selected security group inbound rules
            for sg_rule in sg_selected_rules_dic["outbound"]:
                boto3.client('ec2', region_name = vpcRegion).revoke_security_group_egress(
                    GroupId=sgID,
                    IpPermissions=[
                        {
                            'FromPort': sg_rule['Port'],
                            'IpProtocol': sg_rule['Protocol'],
                            'IpRanges': [
                                {
                                    'CidrIp': sg_rule['Cidr']
                                },
                            ],
                            'ToPort': sg_rule['Port']
                        },
                    ],
                )
                print(f"{Fore.YELLOW}OUTBOUND -> {sg_rule}{Style.RESET_ALL}")
                print('\n')



def terminate_ec2_instances(bastion="no"):
    existing_instances = {}
    bastion_instances = {}

    def delete_instance():
        boto3.client('ec2', region_name = vpcRegion).terminate_instances(
            InstanceIds=[
                terminateInstanceID,
            ],
        )
        # Wait for termination before proceeding
        print(f"{Fore.MAGENTA}Terminating the instance...It should take a minute.{Style.RESET_ALL}")
        print('\n')
        time.sleep(60)

    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to terminate instances: {Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)
    print('\n')

    # Describe all instances in the chosen VPC
    response = boto3.client('ec2', region_name = vpcRegion).describe_instances(
        Filters=[
            {
                'Name': 'vpc-id',
                'Values': [
                    vpcID,
                ]
            },
        ],
    )
    instances = response['Reservations']
    for instance in instances:
        instanceName = instance['Instances'][0]['Tags'][0]['Value']
        instanceID = instance['Instances'][0]['InstanceId']
        if "bastion" in instanceName:
            bastion_instances[instanceName] = instanceID
        existing_instances[instanceName] = instanceID

    # Select the instances you want to delete
    if bastion == "yes":
        instanceMessage = f"{Fore.LIGHTBLUE_EX}Select the bastion host(s) you want to terminate: {Style.RESET_ALL}"
        selected_instances = select_instance(instanceMessage, bastion_instances, string="Checkbox")
        for selected_instance in selected_instances:

            # Delete the instance
            terminateInstanceID = existing_instances[selected_instance]
            instanceInfo = describe_instance(vpcRegion, terminateInstanceID)
            delete_instance()
            subnetID = instanceInfo['SubnetId']

            # Delete the security group
            security_groups = instanceInfo['SecurityGroups']
            for security_group in security_groups:
                if "BastionHost" in security_group['GroupName']:
                    sgID = security_group['GroupId']
                    try:
                        boto3.client('ec2', region_name = vpcRegion).delete_security_group(
                                GroupId=sgID
                            )
                    except:
                        print(Fore.MAGENTA, "This security group is attached to another network interface. You need to replace it before deleting it.", Style.RESET_ALL)
                        print('\n')
                        time.sleep(3)
                        delete_sg()

            # Find the network ACL of the subnet in which the bastion host is located
            publicIP = get('https://api.ipify.org').text + "/32"
            existing_nacls = describe_network_acls(vpcRegion, filterName='association.subnet-id', filterID=subnetID)
            naclID = [value[0] for key, value in existing_nacls.items()][0]
            rule_entries = [value[2] for key, value in existing_nacls.items()]
            rule_entries = rule_entries[0]

            for rule_entry in rule_entries:
                try:
                    portFrom = rule_entry['PortRange']['From']
                    portTo = rule_entry['PortRange']['To']
                except:
                    portFrom = 0
                    portTo = 0
                cidrBlock = rule_entry['CidrBlock']

                # Delete the SSH entries on the network ACL
                if portFrom == 22 and portTo == 22 and cidrBlock == publicIP:
                    egressValue = rule_entry['Egress']
                    ruleNumber = rule_entry['RuleNumber']
                    boto3.client('ec2', region_name = vpcRegion).delete_network_acl_entry(
                        Egress=egressValue,
                        NetworkAclId=naclID,
                        RuleNumber=ruleNumber
                    )
        print(f"{Fore.MAGENTA}Selected bastions host(s) and the associated security group(s) have been successfully deleted,\n\nand the corresponding network ACL SSH entries have also been removed.{Style.RESET_ALL}")
        print('\n')
    elif bastion == "no":
        instanceMessage = f"{Fore.LIGHTBLUE_EX}Select the EC2 instance(s) you want to terminate: {Style.RESET_ALL}"
        selected_instances = select_instance(instanceMessage, existing_instances, string="Checkbox")
        for selected_instance in selected_instances:
            terminateInstanceID = existing_instances[selected_instance]
            delete_instance()
        print(f"{Fore.MAGENTA}Selected EC2 instance(s) have been successfully deleted.{Style.RESET_ALL}")
        print('\n')



def delete_nat_gw():
    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete the NAT gateway(s){Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)
    print('\n')

    # Describe the NAT gateways in the chosen VPC
    nat_gateways = describe_ngw(vpcRegion, vpcID)
    ngws = {}
    for nat_gateway in nat_gateways:
        ngwName = nat_gateway['Tags'][0]['Value']
        ngwID = nat_gateway['NatGatewayId']
        allocationID = nat_gateway['NatGatewayAddresses'][0]['AllocationId']
        ngws[ngwName] = [ngwID, allocationID]

    # Choose the NAT gateway(s) you want to delete
    ngwMessage = f"{Fore.LIGHTBLUE_EX}Choose the NAT gateway(s) you want to delete{Style.RESET_ALL}"
    questions = [
    inquirer.Checkbox('ngw',
                    message=ngwMessage,
                    choices=list(ngws.keys())
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected_ngws = answers['ngw']

    # Delete the NAT gateway(s) and release their elastic IPs
    for selected_ngw in selected_ngws:
        natgwID = ngws[selected_ngw][0]
        boto3.client('ec2', region_name = vpcRegion).delete_nat_gateway(
            NatGatewayId=natgwID
        )
        # Find the route tables that have NAT gateway connections and delete the blackhole routes
        existing_route_tables, _ = describe_rt(vpcRegion, filtername='route.nat-gateway-id', filterID=natgwID)
        for existing_route_table in existing_route_tables:
            rtID = existing_route_tables[existing_route_table][0]
            routes = existing_route_tables[existing_route_table][2]
            for route in routes:
                if 'NatGatewayId' in list(route.keys()):
                    destinationCidrBlock = route['DestinationCidrBlock']
                    boto3.client('ec2', region_name = vpcRegion).delete_route(
                        DestinationCidrBlock=destinationCidrBlock,
                        RouteTableId=rtID,
                    )
    print(f"{Fore.MAGENTA}Deleting the NAT gateway(s)...It should take about a minute.{Style.RESET_ALL}")
    print('\n')
    time.sleep(90)
    for selected_ngw in selected_ngws:
        allocID = ngws[selected_ngw][1]
        boto3.client('ec2', region_name = vpcRegion).release_address(
            AllocationId=allocID
        )
    print(f"{Fore.MAGENTA}Released the elastic IP addresses.{Style.RESET_ALL}")
    print('\n')
    message = f"{Fore.MAGENTA}NAT gateway(s){Style.RESET_ALL} {Fore.CYAN}{selected_ngws}{Style.RESET_ALL} {Fore.MAGENTA}, and their allocated elastic IP(s) and route table routes have been successfully deleted.{Style.RESET_ALL}"
    print(message)
    print('\n')



def delete_routes():
    # Choose the vpc in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete routes{Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe existing route tables in the chosen VPC
    existing_route_tables, _ = describe_rt(vpcRegion, filtername='vpc-id', filterID=vpcID)

    # Select the route tables that you want to delete their routes
    rtsMessage = f"{Fore.LIGHTBLUE_EX}Select the route tables that you want to delete their routes{Style.RESET_ALL}"
    selected_route_tables = select_rts(rtsMessage, existing_route_tables)

    # Select the routes that will be deleted
    for selected_route_table in selected_route_tables:
        rtID = existing_route_tables[selected_route_table][0]
        routes = existing_route_tables[selected_route_table][2]
        routeMessage = f"{Fore.LIGHTBLUE_EX}Choose the routes that you want to delete in the route table{Style.RESET_ALL} {Fore.RED}{selected_route_table}{Style.RESET_ALL}"
        questions = [
        inquirer.Checkbox('route',
                        message=routeMessage,
                        choices=routes
                        ),
        ]
        answers = inquirer.prompt(questions, theme=GreenPassion())
        selected_routes = answers['route']

        # Delete the routes
        for selected_route in selected_routes:
            try:
                ip = selected_route['DestinationCidrBlock']
                boto3.client('ec2', region_name = vpcRegion).delete_route(
                    DestinationCidrBlock=ip,
                    RouteTableId=rtID
                )
            except:
                pass
            try:
                ip = selected_route['DestinationIpv6CidrBlock']
                boto3.client('ec2', region_name = vpcRegion).delete_route(
                    DestinationIpv6CidrBlock=ip,
                    RouteTableId=rtID
                )
            except:
                pass

    print(f"{Fore.MAGENTA}The following routes have been successfully deleted:{Style.RESET_ALL}")
    print('\n')
    for selected_route in selected_routes: 
        print(f"{Fore.YELLOW}{selected_route}{Style.RESET_ALL}")
        print('\n')



def delete_vpc_s3_endpoint():

    # Choose the vpcs in which you want to operate
    vpcMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC in which you want to delete VPC gateway S3 endpoint(s){Style.RESET_ALL}"
    _, vpcRegion, vpcID = select_vpc(vpcMessage)

    # Describe the VPC gateway S3 endpoints
    vpc_endpoints = describe_vpc_endpoints(vpcRegion, filtername='vpc-id', filterID=vpcID)
    vpc_endpoint_data = {}
    for vpc_endpoint in vpc_endpoints:
        vpcEndpointName = vpc_endpoint['Tags'][0]['Value']
        vpcEndpointId = vpc_endpoint['VpcEndpointId']
        route_table_ids = vpc_endpoint['RouteTableIds']
        vpc_endpoint_data[vpcEndpointName] = [vpcEndpointId, route_table_ids]

    # Select the VPC gateway S3 endpoints that you want to delete
    vpcEndpointMessage = f"{Fore.LIGHTBLUE_EX}Select the VPC gateway S3 endpoint(s) that you want to delete{Style.RESET_ALL}"
    selected_vpc_endpoints = select_vpc_endpoint(vpcEndpointMessage, vpc_endpoint_data, string="Checkbox")
    delete_vpc_endpoints = [vpc_endpoint_data[x][0] for x in selected_vpc_endpoints]

    # Delete the selected VPC gateway S3 endpoints
    boto3.client('ec2', region_name = vpcRegion).delete_vpc_endpoints(
        VpcEndpointIds=delete_vpc_endpoints
    )
    print(f"{Fore.MAGENTA}The following VPC gateway S3 endpoint(s) and their associated route(s) have been successfully deleted:{Style.RESET_ALL}")
    print('\n')
    for selected_vpc_endpoint in selected_vpc_endpoints:
        print(f"{Fore.YELLOW}{selected_vpc_endpoint}{Style.RESET_ALL}")
        print('\n')



def open_menu():

    # Select the operation you want to do
    message = f"{Fore.LIGHTBLUE_EX}Do you want to create/modify a resource or delete a resource?{Style.RESET_ALL}"
    questions = [
    inquirer.List('operation',
                    message=message,
                    choices=["create/modify", "delete", "exit"]
                    ),
    ]
    answers = inquirer.prompt(questions, theme=GreenPassion())
    choice = answers['operation']
    print('\n')
    if choice == "exit":
        exit_script()

    elif choice == "create/modify":
        # Select the operation you want to do
        message = f"{Fore.LIGHTBLUE_EX}Select the operation you want to perform{Style.RESET_ALL}"
        questions = [
        inquirer.List('resources',
                        message=message,
                        choices=[
                            "Create VPC",
                            "Add Subnet",
                            "Create, Replace or Attach Route Table",
                            "Create, Replace or Attach Network Access Control List",
                            "Create, Replace or Attach Security Group",
                            "Create or Modify Routes in Route Table",
                            "Create or Modify Network Access Control List Entries",
                            "Create or Modify Security Group Rules",
                            "Launch NAT Gateway", 
                            "Launch Bastion Host", 
                            "Launch EC2 Instances",
                            "SSH Connect to an Instance",
                            "Create VPC S3 Endpoint",
                            "Exit"
                        ]
                    ),
        ]

        answers = inquirer.prompt(questions, theme=GreenPassion())
        options = answers['resources']
        print('\n')

        if options == "Create VPC":
            create_vpc()
        elif options == "Add Subnet":
            add_subnet()
        elif options == "Create, Replace or Attach Route Table":
            create_and_associate_rt()
        elif options == "Create, Replace or Attach Network Access Control List":
            create_and_associate_nacl()
        elif options == "Create, Replace or Attach Security Group":
            create_and_attach_sg()
        elif options == "Create or Modify Routes in Route Table":
            modify_rt()
        elif options == "Create or Modify Network Access Control List Entries":
            modify_nacl_entries()
        elif options == "Create or Modify Security Group Rules":
            modify_sg()
        elif options == "Launch NAT Gateway":
            launch_nat_gw()
        elif options == "Launch Bastion Host":
            launch_ec2_instances(bastion="yes")
        elif options == "Launch EC2 Instances":
            launch_ec2_instances(bastion="no")
        elif options == "SSH Connect to an Instance":
            connect_instance()
        elif options == "Create VPC S3 Endpoint":
            create_vpc_s3_endpoint()
        elif options == "Exit":
            exit_script()

    elif choice == "delete":
        # Select the operation you want to do
        message = f"{Fore.LIGHTBLUE_EX}Select the operation you want to perform{Style.RESET_ALL}"
        questions = [
        inquirer.List('resources',
                        message=message,
                        choices=[
                            "Delete VPC", 
                            "Delete Subnet",
                            "Delete Route Table",
                            "Delete Route Table Routes",
                            "Delete Network Access Control List",
                            "Delete Network Access Control List Entries",
                            "Delete Security Group",
                            "Delete Security Group Rules",
                            "Delete NAT Gateway",
                            "Terminate Bastion Host",
                            "Terminate EC2 Instances",
                            "Delete VPC S3 Endpoint",
                            "Exit"
                            ]
                        ),
        ]

        answers = inquirer.prompt(questions, theme=GreenPassion())
        options = answers['resources']
        print('\n')

        if options == "Delete VPC":
            delete_vpc()
        elif options == "Delete Subnet":
            delete_subnet()
        elif options == "Delete Route Table":
            delete_rt()
        elif options == "Delete Route Table Routes":
            delete_routes()
        elif options == "Delete Network Access Control List":
            delete_nacl()
        elif options == "Delete Network Access Control List Entries":
            delete_nacl_entries()
        elif options == "Delete Security Group":
            delete_sg()
        elif options == "Delete Security Group Rules":
            delete_sg_rules()
        elif options == "Delete NAT Gateway":
            delete_nat_gw()
        elif options == "Terminate Bastion Host":
            terminate_ec2_instances(bastion="yes")
        elif options == "Terminate EC2 Instances":
            terminate_ec2_instances(bastion="no")
        elif options == "Delete VPC S3 Endpoint":
            delete_vpc_s3_endpoint()
        elif options == "Exit":
            exit_script()

define_parameters()

open_menu()
menuMessage = input(f"{Fore.LIGHTBLUE_EX}Do you want to continue? (y/N): {Style.RESET_ALL}")
if menuMessage == "y" or menuMessage == "Y":
    open_menu()
else:
    exit_script()
