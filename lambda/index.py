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
CUSTOM_CHATBOT_API_ENDPOINT = "https://2420-34-169-121-249.ngrok-free.app/generate"
if not CUSTOM_CHATBOT_API_ENDPOINT:
    print("警告: 環境変数 CUSTOM_CHATBOT_API_ENDPOINT が設定されていません。")
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

        # Cognitoで認証されたユーザー情報を取得 (オプション)
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")

        # リクエストボディの解析
        body = json.loads(event['body'])
        message = body['message'] # 最新のユーザーからのメッセージ
        conversation_history = body.get('conversationHistory', []) # これまでの会話履歴

        print("Processing message:", message)
        # print("Using model:", MODEL_ID) # Bedrock用 (コメントアウト)

        # --- ここからカスタムAPI呼び出し ---
        if CUSTOM_CHATBOT_API_ENDPOINT: # エンドポイントが設定されている場合のみ実行

            # 方法1: 会話履歴と最新のメッセージを結合して一つのプロンプトを作成
            prompt_parts = []
            for entry in conversation_history:
                # APIサーバーが期待する形式に合わせて role と content を整形
                # ここでは単純に連結していますが、APIサーバー側のモデルの入力形式に合わせて調整が必要な場合があります。
                # 例えば、特定の区切り文字 (例: "<|user|>", "<|assistant|>") を使うなど。
                # FastAPIサーバーのモデル (google/gemma-2-2b-jpn-it) がどのような形式のプロンプトで
                # 会話の文脈を最もよく理解するかは、モデルのドキュメントや実験で確認が必要です。
                # シンプルな例として、以下のようにします。
                prompt_parts.append(f"{entry['role']}: {entry['content']}")

            prompt_parts.append(f"user: {message}") # 最新のユーザーメッセージを最後に追加
            combined_prompt = "\n".join(prompt_parts)

            # 独自のAPI用のリクエストペイロードを構築
            request_data_dict = {
                'prompt': combined_prompt,
                # 必要であれば、APIサーバーが受け付ける他のパラメータも追加できます
                # 'max_new_tokens': 512, # FastAPIサーバーのデフォルト値と同じ
                # 'temperature': 0.7,  # FastAPIサーバーのデフォルト値と同じ
                # 'top_p': 0.9,        # FastAPIサーバーのデフォルト値と同じ
            }
            request_data = json.dumps(request_data_dict).encode('utf-8')

            print(f"Calling custom chatbot API at {CUSTOM_CHATBOT_API_ENDPOINT} with payload: {request_data.decode('utf-8')}")


            # 独自のAPIを呼び出し (urllib.requestを使用)
            req = urllib.request.Request(
                CUSTOM_CHATBOT_API_ENDPOINT,
                data=request_data,
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                method='POST'
            )
            try:
                with urllib.request.urlopen(req) as response:
                    response_body_str = response.read().decode('utf-8')
                    print("Raw Custom API response string:", response_body_str) # 生のレスポンス文字列をログに出力
                    response_body = json.loads(response_body_str)
                    print("Custom API response JSON:", json.dumps(response_body))

                    # 応答の検証 (API仕様に合わせて変更が必要)
                    # FastAPIサーバーは 'generated_text' キーで応答を返す
                    if not response_body or 'generated_text' not in response_body:
                        raise Exception("Custom APIから 'generated_text' を含む有効な応答が得られませんでした。")

                    # アシスタントの応答を取得
                    assistant_response = response_body['generated_text']

            except urllib.error.HTTPError as e:
                error_body_str = ""
                try:
                    error_body_str = e.read().decode('utf-8') # エラーレスポンスの内容も取得試行
                except Exception as read_err:
                    print(f"Failed to read error body: {read_err}")
                print(f"HTTP Error: {e.code} {e.reason}")
                print(f"Error response body: {error_body_str}")
                # HTTP 422エラーの詳細も表示するように修正
                if e.code == 422:
                    try:
                        error_detail = json.loads(error_body_str)
                        raise Exception(f"Custom API呼び出しでHTTPエラーが発生しました: {e.code} - {json.dumps(error_detail)}")
                    except json.JSONDecodeError:
                         raise Exception(f"Custom API呼び出しでHTTPエラーが発生しました: {e.code} - {error_body_str}")
                else:
                    raise Exception(f"Custom API呼び出しでHTTPエラーが発生しました: {e.code} - {error_body_str}")
            except urllib.error.URLError as e:
                print(f"URL Error: {e.reason}")
                raise Exception(f"Custom APIへの接続に失敗しました: {e.reason}")
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: {e}. Response string was: {response_body_str if 'response_body_str' in locals() else 'Not available'}")
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
        # (省略)
        # --- ここまでBedrock呼び出し (コメントアウト) ---


        # アシスタントの応答を会話履歴に追加するためのリストを準備
        # (この messages リストは、クライアントに返す会話履歴用)
        updated_conversation_history = conversation_history.copy()
        updated_conversation_history.append({
            "role": "user",
            "content": message # 最新のユーザーメッセージ
        })
        updated_conversation_history.append({
            "role": "assistant",
            "content": assistant_response # APIからの応答
        })

        # 成功レスポンスの返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*", # 必要に応じてより厳密に設定
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": updated_conversation_history # 更新された会話履歴
            })
        }

    except Exception as error:
        print(f"Lambda Handler Error: {str(error)}")
        import traceback
        traceback.print_exc() # スタックトレースをCloudWatch Logsに出力

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