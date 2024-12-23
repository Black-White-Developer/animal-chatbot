import json
import boto3
import os

client = boto3.client("lambda")

def lambda_handler(event, context):
    request_body = json.loads(event['body'])
    print(request_body)

    if request_body['flow']['trigger']['type'] == 'IMAGE_UPLOAD':
        answer = "조금 기다리면 동물에 대해 설명해 줄게요!"
        client.invoke(
            FunctionName=os.environ["IMAGE_PROCESS_FUNCTION_NAME"],
            InvocationType='Event',
            Payload=json.dumps({
                'image_input' : request_body['userRequest']['utterance'],
                'callback_url' : request_body['userRequest']['callbackUrl']
            })
        )
    else:
        answer = "조금 기다리면 동물의 모습과 설명을 제공할게요!"
        client.invoke(
            FunctionName=os.environ["TEXT_PROCESS_FUNCTION_NAME"],
            InvocationType='Event',
            Payload=json.dumps({
                'text_input' : request_body['userRequest']['utterance'],
                'callback_url' : request_body['userRequest']['callbackUrl']
            })
        )

    return {
        'statusCode':200,
        'body': json.dumps({
            'version': '2.0',
            'useCallback' : True,
            'data': { 'text' : answer }
        })
    }