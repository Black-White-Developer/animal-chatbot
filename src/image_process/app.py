import requests
import boto3
import json
import os
from datetime import datetime

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
bedrock_runtime = boto3.client("bedrock-runtime")

bucket_name = os.getenv("IMAGE_S3_BUCKET_NAME")
s3_image_key = f'detect/{datetime.now().strftime('%Y%m%d%H%M%S')}.png'

def detect_labels():
    response = rekognition.detect_labels(
        Image={'S3Object':{'Bucket': bucket_name, 'Name': s3_image_key}},
        MaxLabels=10, MinConfidence=75
    )

    labels = []
    for label in response['Labels']:
        labels.append(label['Name'])

    return ", ".join(labels)

def bedrock_chatbot(text):
    response = bedrock_runtime.invoke_model(
        modelId = 'anthropic.claude-3-5-sonnet-20240620-v1:0', 
        body = json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'messages': [ { 'role': 'user', 'content': f"""
                All answers must be in Korean.
                Current extracted label: {text}

                1) Output the breed of the animal here.
                Output Format Example: "Golden Retriever", "Pomeranian", "<breed name>", "invalid"

                2) Please tell me the information of this breed.
            """ } ],
            'max_tokens': 2048,
            'temperature': 0.5
        }),
        accept='application/json', 
        contentType='application/json'
    )
    return json.loads(response.get('body').read())['content'][0]['text']

def lambda_handler(event, context):
    image_input = event['image_input']
    callback_url = event['callback_url']

    response = requests.get(image_input)
    if response.status_code == 200:
        s3.put_object(Bucket=bucket_name, Key=s3_image_key, Body=response.content)
        print("이미지가 S3에 업로드되었습니다.")
        labels = detect_labels()
        message = bedrock_chatbot(labels)
    else:
        print("이미지 다운로드 실패:", response.status_code)
        message = "이미지 처리에 실패했습니다."
        return True

    requests.post(callback_url, json={
        'version': '2.0',
        'useCallback': False,
        'template': { 'outputs': [ { 'simpleText': { 'text': message } } ] }
    })

    return True