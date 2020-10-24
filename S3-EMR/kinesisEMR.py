"""

aws emr add-steps --cluster-id j-1QAORT274XV3E --steps Type=Spark,Name="Kinesis-SQL",ActionOnFailure=CONTINUE,Args=[--jars,s3://sparkkinesis/spark-sql-kinesis_2.11-1.2.1_spark-2.4-SNAPSHOT.jar,s3://sparkkinesis/kinesis_example.py,kinesis-sql,ExampleInputStream,https://kinesis.us-east-1.amazonaws.com,us-east-1]

"""
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructField, StructType, StringType, IntegerType, Row
import boto3
import requests
import random

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(
            "Usage: kinesis_example.py <app-name> <stream-name> <endpoint-url> <region-name>")
        sys.exit(-1)

    applicationName, streamName, endpointUrl, regionName = sys.argv[1:]

    spark = SparkSession \
        .builder \
        .appName(applicationName) \
        .getOrCreate()

    kinesis = spark \
            .readStream \
            .format('kinesis') \
            .option('streamName', streamName) \
            .option('endpointUrl', endpointUrl)\
            .option('region', regionName) \
            .option('startingposition', 'LATEST')\
            .load()\

    schema = StructType([
                StructField("PTO_MIN", StringType()),
                StructField("TEM_MAX", StringType()),
                StructField("PTO_INS", StringType()),
                StructField("TEM_INS", StringType()),
                StructField("UMD_INS", StringType()),
                StructField("TEM_MAX", StringType())])
    
    def getDic(dicResult, celsius):
        if celsius.real <= 27.0:
            dicResult['nivel'] = 'Normal'
        elif celsius.real > 27.1 and celsius.real < 32.0:
            dicResult['nivel'] = 'Cautela'
        elif celsius.real > 32.1 and celsius.real < 41.0:
            dicResult['nivel'] = 'Cautela Extrema'
        elif celsius.real > 41.1 and celsius.real < 54.0:
            dicResult['nivel'] = 'Perigo'
        elif celsius.real > 54:
            dicResult['nivel'] = 'Perigo Extremo'
        return dicResult

    def sendThingsBoard(data):
        tb_host = "demo.thingsboard.io"
        device_token = "YOUR_DEVICE_TOKEN"
        try:
            url = 'http://' + tb_host + '/api/v1/' + device_token + '/telemetry'
            requests.post(url, json=data)
        except ConnectionError:
            print ('Failed to send data.')

    def process(row):
        dic = row.asDict()
        c1 = -42.379
        c2 = 2.04901523
        c3 = 10.14333127
        c4 = -0.22475541
        c5 = -6.83783*0.01
        c6 = -5.481717*0.1
        c7 = 1.22874*0.01
        c8 = 8.5282*0.001
        c9 = -1.99*0.00001
        numero = random.randint(20, 70)

        T = (float(dic["TEM_INS"]) * 1.8) + 32
        RH = float(dic["UMD_INS"])
        dicResult = {'HI': 0, 'nivel': 'Normal'}
        celsius = 0.0

        HI_1 = 0.0
        HI_2 = (1.1 * T) - 10.3 + (0.047 * RH)
        
        if HI_2 < 80:
            HI_1 = HI_2
            celsius = (HI_1 - 32)/1.8
            dicResult['HI'] = celsius
        else:
            HI_2 = c1 + (c2*T) + (c3*RH) + (c4*T*RH) + (c5*(T**2)) + (c6*(RH**2)) + (c7*(T**2)*RH) + (c8*T*(RH**2)) + (c9*(T**2)*(RH**2))
            if 80 <= T and T <= 112 and RH >= 13:
                HI_1 = HI_2 - (((3.25 - (0.25 * RH)) * ((17 - abs(T - 95))/17))**0.5)
            else:
                if 80 <= T and T <= 87 and RH > 85:
                    HI_1 = HI_2 + (0.02 * (RH - 85) * (87 - T))
                else:
                    HI_1 = HI_2
            celsius = (HI_1 - 32)/1.8
            dicResult['HI'] = celsius.real
        dicResult = getDic(dicResult, celsius)

        new_row = Row(**dicResult)
        clientSQS = boto3.client('sqs', region_name='us-east-1')
        url = "https://sqs.us-east-1.amazonaws.com/ID_QUEUE/NAME_QUEUE"
        clientSQS.send_message(QueueUrl=url,MessageBody=str(new_row))

        sendThingsBoard(dicResult)

    kinesis\
        .selectExpr('CAST(Data AS STRING)')\
        .select(from_json('Data', schema).alias('Data'))\
        .select('Data.*')\
        .writeStream\
        .outputMode('append')\
        .foreach(process)\
        .trigger(processingTime='2 seconds') \
        .start()\
        .awaitTermination()
