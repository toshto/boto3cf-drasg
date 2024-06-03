#!/usr/bin/env python
import boto3
import os
import sys


# 引数チェック
try:
    sys.argv.pop(0)
    s = sys.argv.pop(0)
except Exception as e:
    print("Usage: ec2ssh.py <StackName> [region_name]")
    print(e)
    sys.exit(1)

try:
    r= sys.argv.pop(0)
except Exception as e:
    r = 'ap-northeast-1'

session = boto3.Session(profile_name='default', region_name=r)
ec2 = session.client('ec2')

instance_list = ec2.describe_instances(
    Filters=[{'Name': 'tag:StackName', 'Values': [s]}]
)
instances = []
for Reservations in instance_list['Reservations']:
    for instance in Reservations['Instances']:
        if instance['State']['Name'] == 'running':
            datetime = str(instance['LaunchTime'])
            instances.append(
                (
                    str(instance['LaunchTime']),
                    instance['State']['Name'], instance['KeyName'], instance['PublicDnsName']
                )
            )

n = 0
for inst in instances:
    n += 1
    print(str(n) + ') ' + '[' + inst[0] + '] ' + inst[3])

if n != 0:
    print('input number > ', end="")
    try:
        n = int(input()) - 1
    except ValueError:
        print ("Bye.")
        sys.exit(0)

else:
    print('no instance existed.')
    exit()

if instances[n][0] is not None:
    os.system('clear')
    os.system('ssh -i ~/.ssh/' + instances[n][2] + '.pem ec2-user@' + instances[n][3])
else:
    print("out of bound")
