# lambda/index.py
import json
import os
# import boto3 # Bedrock用 (コメントアウト)
# import re  # 正規表現モジュールをインポート (コメントアウト)
# from botocore.exceptions import ClientError # Bedrock用 (コメントアウト)
import urllib.request # HTTPリクエスト用にインポート
import urllib.error   # HTTPエラー処理用にインポート


# # Lambda コンテキストからリージョンを抽出する関数 (コメントアウト)
# def extract_region_from_arn(arn):
#     # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
#     match = re.search('arn:aws:lambda:([^:]+):', arn)
#     if match:
#         return match.group(1)
#     return "us-east-1"  # デフォルト値

# # グローバル変数としてクライアントを初期化（初期値） (コメントアウト)
# bedrock_client = None

# # モデルID (コメントアウト)
# MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")

# --- ここからカスタムAPI用の設定 ---
# 独自のチャットボットAPIエンドポイントを環境変数から取得
CUSTOM_CHATBOT_API_ENDPOINT = "https://1d50-34-125-140-190.ngrok-free.app/generate"
if not CUSTOM_CHATBOT_API_ENDPOINT:
    # エンドポイントが設定されていない場合はエラーにするか、デフォルト値を設定
    # raise ValueError("環境変数 CUSTOM_CHATBOT_API_ENDPOINT が設定されていません。")
    print("警告: 環境変数 CUSTOM_CHATBOT_API_ENDPOINT が設定されていません。")
    # ここで処理を中断するか、デフォルトのエンドポイントを使うなどの処理を追加できます
# --- ここまでカスタムAPI用の設定 ---

def lambda_handler(event, context):
    try:
        # # コンテキストから実行リージョンを取得し、クライアントを初期化 (コメントアウト)
        # global bedrock_client
        # if bedrock_client is None:
        #     region = extract_region_from_arn(context.invoked_function_arn)
        #     bedrock_client = boto3.client('bedrock-runtime', region_name=region)
        #     print(f"Initialized Bedrock client in region: {region}")
        
        print("Received event:", json.dumps(event))
        
        # Cognitoで認証されたユーザー情報を取得
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")
        
        # リクエストボディの解析
        body = json.loads(event['body'])
        message = body['message']
        conversation_history = body.get('conversationHistory', [])
        
        print("Processing message:", message)
        # print("Using model:", MODEL_ID) # Bedrock用 (コメントアウト)

        # 会話履歴を使用
        messages = conversation_history.copy()

        # ユーザーメッセージを追加
        messages.append({
            "role": "user",
            "content": message
        })

        # --- ここからカスタムAPI呼び出し ---
        if CUSTOM_CHATBOT_API_ENDPOINT: # エンドポイントが設定されている場合のみ実行
            # 独自のAPI用のリクエストペイロードを構築 (API仕様に合わせて変更が必要)
            # 例: {'history': messages}
            request_data = json.dumps({
                'history': messages,
                # 他に必要なパラメータがあれば追加 (例: 'user_id': user_info.get('sub') if user_info else None)
            }).encode('utf-8')

            print(f"Calling custom chatbot API at {CUSTOM_CHATBOT_API_ENDPOINT}")

            # 独自のAPIを呼び出し (urllib.requestを使用)
            req = urllib.request.Request(
                CUSTOM_CHATBOT_API_ENDPOINT,
                data=request_data,
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, # Acceptヘッダーも追加推奨
                method='POST'
            )
            try:
                with urllib.request.urlopen(req) as response:
                    response_body = json.loads(response.read().decode('utf-8'))
                    print("Custom API response:", json.dumps(response_body))

                    # 応答の検証 (API仕様に合わせて変更が必要)
                    # 例: 'response'キーに結果が入る想定
                    if not response_body or 'response' not in response_body:
                        raise Exception("Custom APIから有効な応答が得られませんでした。レスポンス形式を確認してください。")

                    # アシスタントの応答を取得 (API仕様に合わせて変更が必要)
                    # 例: 'response'キーに結果が入る想定
                    assistant_response = response_body['response']

            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') # エラーレスポンスの内容も取得試行
                print(f"HTTP Error: {e.code} {e.reason}")
                print(f"Error response body: {error_body}")
                raise Exception(f"Custom API呼び出しでHTTPエラーが発生しました: {e.code} - {error_body}")
            except urllib.error.URLError as e:
                print(f"URL Error: {e.reason}")
                raise Exception(f"Custom APIへの接続に失敗しました: {e.reason}")
            except json.JSONDecodeError:
                raise Exception("Custom APIの応答がJSON形式ではありませんでした。")
            except Exception as e: # その他の予期せぬエラー
                print(f"An unexpected error occurred during custom API call: {str(e)}")
                raise Exception(f"Custom API呼び出し中に予期せぬエラーが発生しました: {str(e)}")

        else:
            # エンドポイントが設定されていない場合の代替応答
            assistant_response = "チャットボットAPIエンドポイントが設定されていません。"
            print("警告: CUSTOM_CHATBOT_API_ENDPOINT が未設定のため、API呼び出しをスキップしました。")
        # --- ここまでカスタムAPI呼び出し ---


        # --- ここからBedrock呼び出し (コメントアウト) ---
        # # Nova Liteモデル用のリクエストペイロードを構築
        # # 会話履歴を含める
        # bedrock_messages = []
        # for msg in messages:
        #     if msg["role"] == "user":
        #         bedrock_messages.append({
        #             "role": "user",
        #             "content": [{"text": msg["content"]}]
        #         })
        #     elif msg["role"] == "assistant":
        #         bedrock_messages.append({
        #             "role": "assistant",
        #             "content": [{"text": msg["content"]}]
        #         })
        #
        # # invoke_model用のリクエストペイロード
        # request_payload = {
        #     "messages": bedrock_messages,
        #     "inferenceConfig": {
        #         "maxTokens": 512,
        #         "stopSequences": [],
        #         "temperature": 0.7,
        #         "topP": 0.9
        #     }
        # }
        #
        # print("Calling Bedrock invoke_model API with payload:", json.dumps(request_payload))
        #
        # # invoke_model APIを呼び出し
        # response = bedrock_client.invoke_model(
        #     modelId=MODEL_ID,
        #     body=json.dumps(request_payload),
        #     contentType="application/json"
        # )
        #
        # # レスポンスを解析
        # response_body = json.loads(response['body'].read())
        # print("Bedrock response:", json.dumps(response_body, default=str))
        #
        # # 応答の検証
        # if not response_body.get('output') or not response_body['output'].get('message') or not response_body['output']['message'].get('content'):
        #     raise Exception("No response content from the model")
        #
        # # アシスタントの応答を取得
        # assistant_response = response_body['output']['message']['content'][0]['text']
        # --- ここまでBedrock呼び出し (コメントアウト) ---


        # アシスタントの応答を会話履歴に追加
        # (カスタムAPI呼び出しが成功した場合も、失敗した場合の代替応答もここに来る)
        messages.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        # 成功レスポンスの返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": messages
            })
        }
        
    except Exception as error:
        print("Error:", str(error))
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }
