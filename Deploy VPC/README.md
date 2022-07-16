This program allows a user to create VPCs in several AWS regions or delete the existing ones simultaneously. In addition, the user can create, modify or delete resources inside the VPC such as subnets, route tables (RT), security groups (SG), network access control lists (NACL), NAT gateways, SG and NACL rules, RT routes, EC2 instances, and VPC endpoints.  

As an example, the program can achieve such a typical deployment of two VPCs with their resources as those seen in the following diagram though more VPCs with their resources can be created.   

<p align="center"> 
<img src="https://github.com/hsaltan/AWS-Projects/blob/main/Deploy%20VPC/images/aws-vpc.png" />
</p>

During the process of creating resources, the code performs naming and numbering in a logical fashion thus minimizing manual intervention. All operations are managed under a menu similar to the below:

<p align="center">
<img src="https://github.com/hsaltan/AWS-Projects/blob/main/Deploy%20VPC/images/menu1.png" />
</p>

<p align="center">
<img src="https://github.com/hsaltan/AWS-Projects/blob/main/Deploy%20VPC/images/menu2.png" />
</p>
