#!/usr/bin/env python
import re

import boto3
import glob
import sys
import yaml

pairs = {}  # 引数から取得するパラメタ
param_file = ""  # パラメタファイルのパス

try:
    sys.argv.pop(0)          # スクリプト名が入る。捨てる。
    param_file = sys.argv.pop(0)  # パラメタファイル
    for arg in sys.argv:     # 残りの引数からのパラメタを取得する。
        k, v = arg.split('=')
        pairs[k] = v
except Exception as e:
    print("Usage: create_stack.py <parameter file> [key=value] ... ")
    print(e)
    sys.exit(1)

# パラメタファイルからの各種パラメタを取得する（引数優先で上書き）。
param = []  # パラメタファイルから取得したパラメタ(引数あれば上書き)
SiteID = ""  # サイト識別子。スタック名に使用する。
BUCKET = ""  # 設定情報を取得するバケット名
REGION = ""  # スタックを作成するリージョン
MAIN = "pre.yaml"  # ImageIdが不在の場合のテンプレート(conditionでnoにしてもチェックでエラーになる)
COMMON = 'common.yml'  # 共通パラメタファイル(ディザスタサイトの場合は異なります)

if re.match(".+_2_.+", param_file):
    COMMON = 'common2.yml'
    print(COMMON)


try:
    print("Read parameters ...")
    for paramfile in "parameters/" + COMMON, param_file:
        for k, v in yaml.safe_load(open(paramfile, 'r')).items():
            print('    ParameterKey: ' + k, ' ParameterValue: ' + v)
            if k in pairs:
                v = pairs[k]  # 引数のパラメタを優先するして、上書きする。

            # parameters/???.yaml から取得した値を設定する。
            param.append({'ParameterKey': k, 'ParameterValue': v, })

            if k == 'SiteID':
                # サイト識別子。スタック名と同じ
                SiteID = v

            if k == 'CFBucket':
                # CloudFormationのテンプレートが格納されているバケット名
                BUCKET = v.split('/').pop(3)

            if k == 'Region':
                # スタックを作成するリージョン
                REGION = v

            if k == 'ImageId':
                # ImageIdが存在する場合のテンプレート
                MAIN = "main.yaml"


except Exception as e:  # parameters/???.yamlが読み込めない例外
    print(e)
    sys.exit(2)

# テンプレートファイルをS3バケットにアップロードする
print("Upload yaml file ...")
if BUCKET is not None:
    bucket = boto3.resource('s3').Bucket(BUCKET)
    for file in glob.glob("templates/*.yaml"):
        try:
            bucket.upload_file(file, file)
        except Exception as e:
            print("ERROR: upload file " + file)
            print(e)
        else:
            print("    Done " + file)

# 既存のスタックかどうかをチェックする。(0:新規, 1:既存)
status = {SiteID: 0}
try:
    session = boto3.Session(profile_name='default', region_name=REGION)
    cf = session.client('cloudformation')
    res = cf.list_stacks(
        StackStatusFilter=[
            'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE',
        ]
    )
    for s in res['StackSummaries']:
        if status.get(s['StackName']) is not None:
            status[s['StackName']] = 1  # 既存のスタックにフラグを立てる
except Exception as e:  # CloudFormationのインスタンス化に失敗した場合。
    print(e)
    sys.exit(3)

print(MAIN)
# スタックの作成/更新
for k, v in status.items():
    if v == 0:
        # 新規作成の場合
        try:
            print("Create stack " + k + "...")
            cf.create_stack(
                StackName=k,
                TemplateURL="https://s3-ap-northeast-1.amazonaws.com/" + BUCKET + '/templates/' + MAIN,
                Parameters=param,
                Capabilities=[
                    'CAPABILITY_NAMED_IAM',
                ],
            )
            waiter = cf.get_waiter('stack_create_complete')
            waiter.wait(
                StackName=k,
            )
        except Exception as e:  # 作成失敗したら削除する。
            print('ERROR: create stack ' + k)
            print(e)
            try:
                cf.delete_stack(
                    StackName=k,
                )
                waiter = cf.get_waiter('stack_delete_complete')
                waiter.wait(
                    StackName=k,
                )
            except Exception as e:  # 削除も失敗？
                print('ERROR: delete stack ' + k)
                print(e)
            else:  # 作成失敗した残骸の削除に成功
                print(k + " deleted!.")
        else:  # 作成成功
            print("Stack " + k + " created!.")
    else:
        # 既存更新の場合
        try:
            print("Update stack " + k + "...")
            cf.update_stack(
                StackName=k,
                TemplateURL="https://s3-ap-northeast-1.amazonaws.com/" + BUCKET + '/templates/' + MAIN,
                Parameters=param,
                Capabilities=[
                    'CAPABILITY_NAMED_IAM',
                ],
            )
            waiter = cf.get_waiter('stack_update_complete')
            waiter.wait(
                StackName=k,
            )
        except Exception as e:  # 更新失敗
            print('ERROR: update stack ' + k)
            print(e)
        else:  # 更新成功
            print(k + " updated!.")
