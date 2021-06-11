This program allows a user to create VPCs in several AWS regions or delete the existing ones simultaneously. In addition, the user can create, modify or delete resources inside the VPC such as subnets, route tables (RT), security groups (SG), network access control lists (NACL), NAT gateways, SG and NACL rules, RT routes, EC2 instances, and VPC endpoints.  

As an example, the program can achieve such a typical deployment of two VPCs with their resources as those seen in the following diagram though more VPCs with their resources can be created.   

<p align="center"> 
<img src="https://user-images.githubusercontent.com/40828825/121691384-9d3d1880-cacf-11eb-8ed1-e674f0735860.png" />
</p>

During the process of creating resources, the code performs naming and numbering in a logical fashion thus minimizing manual intervention. All operations are managed under a menu similar to the below:

<p align="center">
<img src="https://user-images.githubusercontent.com/40828825/121690789-f8bad680-cace-11eb-8437-7c77f800cf48.png" />
</p>

<p align="center">
<img src="https://user-images.githubusercontent.com/40828825/121690940-1f790d00-cacf-11eb-9743-8ead4a66fc3c.png" />
</p>

This code needs improvements and corrections, so any help is welcome!


