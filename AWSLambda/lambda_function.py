import json
import requests
import pandas as pd
import datetime
import time
import boto3
from boto3 import Session

awsRegion = "us-east-1"
accessKeyId = "YOUR_ID_KEY"
secretAccessKey = "YOUR_SECRET_KEY"
sessionToken = "SEU_TOKEN_SESSION"
inputStream = "ExampleInputStream"
response = []

#kinesis =  boto.kinesis.connect_to_region(region)

dataHoje = str(datetime.date.today())
lista = []

def create_client():  
    return boto3.client('kinesis', awsRegion, aws_access_key_id=accessKeyId, aws_secret_access_key=secretAccessKey, aws_session_token=sessionToken)

def main(data):
    kinesis = create_client()
    stream_name = "ExampleInputStream"
    stream_shard_count = 1
    return send_kinesis(kinesis, stream_name, stream_shard_count, data)


def send_kinesis(kinesis_client, kinesis_stream_name, kinesis_shard_count, df):
    kinesisRecords = [] # empty list to store data
    (rows, columns) = df.shape
    currentBytes = 0
    shardCount = 1
    response = None
    for i in df.index:
        j = {'PTO_MIN': df["PTO_MIN"][i], 'TEM_MAX': df["TEM_MAX"][i],'PTO_INS': df["PTO_INS"][i],'TEM_INS': df["TEM_INS"][i],'UMD_INS':  df["UMD_INS"][i]}
        j = json.dumps(j)
        encodedValues = bytes(j, 'utf-8')
        kinesisRecord = { "Data": encodedValues, "PartitionKey": str(shardCount) }
        kinesisRecords.append(kinesisRecord)
        shardCount += 1
    return kinesis_client.put_records( Records=kinesisRecords, StreamName = kinesis_stream_name )

def lambda_handler(event=None, context=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

    resp = requests.get('https://apitempo.inmet.gov.br/estacao/dados/' + dataHoje,  headers=headers)
    
    if resp.status_code != 200:
        return (resp.raise_for_status())
    else:
        df = pd.DataFrame(resp.json())
        #df = df[df["TEM_MAX"].astype('float') ]
        df = df[df["TEM_INS"].notnull()]
        df = df[df["UMD_INS"].notnull()]
        df = df[df["UF"] == "PE"]
        return (main(df))

'''
ini = time.time()
lambda_handler()
fim = time.time()
print ("Tempo: ", fim-ini)
'''
