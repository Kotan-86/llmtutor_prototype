# 必要なライブラリをインポートする
import os
import pandas as pd
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import vertexai
from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool
from tenacity import retry, stop_after_attempt, wait_exponential
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io
import traceback

# SSL証明書なしのローカル環境で実行するための設定（開発時のみ）
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# --- ▼▼▼ 基本設定 ▼▼▼ ---
PROJECT_ID = "flash-adapter-475404-q6"
LOCATION = "us-east4"
RAG_CORPUS_PATH = (
    "projects/flash-adapter-475404-q6/locations/us-east4/ragCorpora/2227030015734710272"
)
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]  # 定数は大文字で定義

# --- ▼▼▼ Flaskアプリケーションの初期化とセッション設定 ▼▼▼ ---
app = Flask(__name__, template_folder="src")
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# --- ▼▼▼ Vertex AIの初期化とRAG設定 ▼▼▼ ---
vertexai.init(project=PROJECT_ID, location=LOCATION)
rag_retrieval_tool = Tool.from_retrieval(
    retrieval=rag.Retrieval(
        source=rag.VertexRagStore(
            rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS_PATH)]
        ),
    )
)
model = GenerativeModel("gemini-2.5-pro", tools=[rag_retrieval_tool])

# --- ▼▼▼ プロンプトテンプレート ▼▼▼ ---
SYSTEM_PROMPT = """
# あなたの役割
あなたは、自己調整学習理論を基盤とする、熟練したLLMチューターです。
# あなたのタスク
学習者との対話を通じて、メタ認知的活動を支援し、学習者が自らの学習を改善できるように導いてください。
対話戦略の詳細は、あなたの知識ベース（RAG）を参照して応答を生成してください。
# 利用可能な情報
- これまでの対話履歴: {history}
- 学習者からの最新メッセージ: {user_message}
- 対象講義の視聴ログ: {lecture_log}
- 対象講義の小テスト結果: {quiz_result}
# 成果物
上記の情報を基に、学習者への応答メッセージを1つだけ生成してください。
"""


# --- ▼▼▼ Google Drive データ取得ヘルパー関数 (修正済み) ▼▼▼ ---
def get_drive_service():
    creds = None
    if "credentials" in session:
        print("セッションから認証情報を取得しています。")
        # ★★★ ここを'SCOPES='から'scopes='に修正しました ★★★
        try:
            creds = Credentials.from_authorized_user_info(
                session["credentials"],
                scopes=SCOPES,  # キーワード引数は小文字、渡す変数は大文字の定数
            )
        except Exception as e:
            print(f"認証情報の読み込み中にエラーが発生しました: {e}")
        print(creds)
    if not creds or not creds.valid:
        return None
    else:
        print("Google Driveサービスの認証に成功しました。")
    try:
        return build("drive", "v3", credentials=creds)
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def download_file_from_drive(service, file_name):
    try:
        query = f"name='{file_name}' and trashed=false"
        results = (
            service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )
        items = results.get("files", [])
        if not items:
            print(f"ファイルが見つかりません: {file_name}")
            return None
        file_id = items[0].get("id")
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return file_content.getvalue().decode("utf-8-sig")
    except HttpError as error:
        print(f"ファイルのダウンロード中にエラーが発生しました: {error}")
        return None


# --- ▼▼▼ Flask ルート設定 ▼▼▼ ---
@app.route("/")
def index():
    if "credentials" not in session:
        return redirect(url_for("oauth2authorize"))
    session["chat_history"] = []
    return render_template("index.html")


@app.route("/oauth2authorize")
def oauth2authorize():
    flow = Flow.from_client_secrets_file("credentials.json", scopes=SCOPES)
    flow.redirect_uri = url_for("oauth2callback", _external=True)
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    session["state"] = state
    return redirect(authorization_url)


@app.route("/oauth2callback")
def oauth2callback():
    state = session["state"]
    flow = Flow.from_client_secrets_file("credentials.json", scopes=SCOPES, state=state)
    flow.redirect_uri = url_for("oauth2callback", _external=True)
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    return redirect(url_for("index"))


@app.route("/chat", methods=["POST"])
def chat():
    print("チャットリクエストを受信しました。")
    try:
        user_message = request.json.get("message")
        if not user_message:
            return jsonify({"error": "メッセージがありません"}), 400

        chat_history = session.get("chat_history", [])
        drive_service = get_drive_service()
        if not drive_service:
            # 認証情報が無効になっている可能性があるので、再認証を促す
            return jsonify({"error": "authentication_required"}), 401

        target_user_id = 343

        log_file_name = f"講義動画視聴ログ_{target_user_id}_No.1 - No.1.csv"
        log_csv_content = download_file_from_drive(drive_service, log_file_name)
        lecture_log_data = (
            pd.read_csv(io.StringIO(log_csv_content)).to_string()
            if log_csv_content
            else "視聴ログが見つかりませんでした。"
        )

        quiz_file_name = "小テストNo.1.csv"
        quiz_csv_content = download_file_from_drive(drive_service, quiz_file_name)
        if quiz_csv_content:
            quiz_df = pd.read_csv(io.StringIO(quiz_csv_content))
            quiz_df["idを入力してください"] = pd.to_numeric(
                quiz_df["idを入力してください"], errors="coerce"
            )
            user_quiz_result = quiz_df[
                quiz_df["idを入力してください"] == target_user_id
            ]
            quiz_result_data = (
                f"小テストNo.1: 総得点 {user_quiz_result['総得点'].iloc[0]}"
                if not user_quiz_result.empty
                else "テスト結果が見つかりませんでした。"
            )
        else:
            quiz_result_data = "テスト結果ファイルが見つかりませんでした。"

        prompt = SYSTEM_PROMPT.format(
            history="\n".join(chat_history),
            user_message=user_message,
            lecture_log=lecture_log_data,
            quiz_result=quiz_result_data,
        )

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
        )
        def generate_with_retry(prompt_text):
            return model.generate_content(prompt_text)

        response = generate_with_retry(prompt)
        bot_response = response.text

        chat_history.append(f"学習者: {user_message}")
        chat_history.append(f"チューター: {bot_response}")
        session["chat_history"] = chat_history

        return jsonify({"response": bot_response})

    except Exception as e:
        print("エラーが発生しました！")
        traceback.print_exc()
        return (
            jsonify(
                {
                    "error": "サーバー内部でエラーが発生しました。詳細はターミナルを確認してください。"
                }
            ),
            500,
        )


if __name__ == "__main__":
    app.run(debug=True, port=8080)
