import requests
import boto3
import os
from datetime import datetime
import base64
import json

IMAGE_S3_BUCKET_NAME = os.getenv("IMAGE_S3_BUCKET_NAME")
AWS_REGION_NAME = os.getenv("AWS_REGION_NAME")

bedrock_runtime = boto3.client("bedrock-runtime")
translate = boto3.client("translate")
s3 = boto3.client("s3")

def judge_input(input):
    prompt = f"""
        1. If the request asks for information about an animal, output the animal's name.
        2. If the request asks for recommendations(추천), it outputs the names of animals that match the user's requirements.
        3. If the previous conditions are not met, "invalid" is output.

        Output Format Example: "Golden Retriever", "Pomeranian", "<animal name>", "invalid"
        Request : "{input}"
    """
    
    response = bedrock_runtime.invoke_model(
        modelId = 'anthropic.claude-3-5-sonnet-20240620-v1:0', 
        body = json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'messages': [ { 'role': 'user', 'content': prompt } ],
            'max_tokens': 2048,
            'temperature': 0.3
        }),
        accept='application/json', 
        contentType='application/json'
    )

    return json.loads(response.get('body').read())['content'][0]['text']

def get_animal_info(animal_name):
    prompt = f"""
        Please tell me the information of this animal with Korean.
        Animal: "{animal_name}"
    """
    
    response = bedrock_runtime.invoke_model(
        modelId = 'anthropic.claude-3-5-sonnet-20240620-v1:0', 
        body = json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'messages': [ { 'role': 'user', 'content': prompt } ],
            'max_tokens': 2048,
            'temperature': 0.3
        }),
        accept='application/json', 
        contentType='application/json'
    )

    return json.loads(response.get('body').read())['content'][0]['text']

def lambda_handler(event, context):
    text_input = event['text_input']
    callback_url = event['callback_url']

    animal_name = judge_input(text_input)
    if "invalid" in animal_name:
        print("Not related to animals")
        requests.post(callback_url, json={
            'version': '2.0',
            'useCallback': False,
            'template': { 'outputs': [ { 'simpleText': { 'text': f'관련한 동물을 찾을 수 없습니다.' } } ] }
        })
        return True
    
    animal_info = get_animal_info(animal_name)
    english_text = translate.translate_text(
        Text=animal_name, 
        SourceLanguageCode='ko', 
        TargetLanguageCode='en'
    )['TranslatedText']

    response = bedrock_runtime.invoke_model(
        modelId='stability.sd3-large-v1:0',
        body=json.dumps({
            'prompt': f"(realistic:1.5)masterpiece, high quality,8k, sharp focus, healthy, green background, one animal, straight-on, front view, beautiful light, hard shadows {english_text}",
            'negative_prompt': '(logo:1.8), (nsfw), (several animal:1.4), low quality, worst quality, watermark, text, human, monochrome, cartoon, manga, 2D, flat, low resolution, deformed, blurred, bad anatomy, disfigured, badly drawn face, mutation, mutated, extra limb, missing limb, blurred, floating limbs, detached limbs, blurred, bad proportion, cropped image'
        })
    )
    image_data = base64.b64decode(json.loads(response['body'].read().decode('utf-8'))['images'][0])
    image_path = os.path.join('/tmp', 'stability.png')
    with open(image_path, 'wb') as file:
        file.write(image_data)

    image_name = f'generate/{datetime.now().strftime('%Y%m%d%H%M%S')}.png'
    s3.upload_file(image_path, IMAGE_S3_BUCKET_NAME, image_name)
    image_url = f'https://{IMAGE_S3_BUCKET_NAME}.s3.{AWS_REGION_NAME}.amazonaws.com/{image_name}'

    requests.post(callback_url, json={
        'version': '2.0',
        'useCallback': False,
        'template': { 'outputs': [ { 'simpleImage': { 'imageUrl': image_url, 'altText' : 'text-to-image' } }, { 'simpleText': { "text": animal_info } } ] }
    })

    os.remove(image_path)
    return True