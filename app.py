# 必要なライブラリをインポートする
import os
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for

# from flask_session import Session # <-- 削除
import vertexai
from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool
from tenacity import retry, stop_after_attempt, wait_exponential

# --- ▼▼▼ 削除 (OAuthフローに不要なライブラリ) ▼▼▼ ---
# from google_auth_oauthlib.flow import Flow
# from google.oauth2.credentials import Credentials
# from google.auth.transport.requests import Request
# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError
# from googleapiclient.http import MediaIoBaseDownload
# from google_auth_httplib2 import AuthorizedHttp
# --- ▲▲▲ 削除ここまで ▲▲▲ ---

# --- ▼▼▼ 追加 (サービスアカウント認証に必要なライブラリ) ▼▼▼ ---
from google.oauth2 import service_account
from google.auth.exceptions import DefaultCredentialsError

# --- ▲▲▲ 追加ここまで ▲▲▲ ---

# --- ▼▼▼ 削除 (Firestore関連) ▼▼▼ ---
# from google.cloud import firestore
# import datetime
# --- ▲▲▲ 削除ここまで ▲▲▲ ---

import gspread
from gspread_dataframe import get_as_dataframe
import io
import traceback
import httplib2  # (gspread が内部で使う可能性)


# --- ▼▼▼ 基本設定 ▼▼▼ ---
PROJECT_ID = "flash-adapter-475404-q6"
LOCATION = "us-east4"
RAG_CORPUS_PATH = (
    "projects/flash-adapter-475404-q6/locations/us-east4/ragCorpora/2227030015734710272"
)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
SERVICE_ACCOUNT_FILE = "service_account.json"


# --- ▼▼▼ Flaskアプリケーションの初期化 ▼▼▼ ---
app = Flask(__name__, template_folder="src")
app.config["SECRET_KEY"] = (
    "your_secret_key_for_csrf_etc"  # (CSRF対策などに使われるため残す)
)

# --- ▼▼▼ 削除 (Flask-Sessionは使わない) ▼▼▼ ---
# app.config["SESSION_TYPE"] = "filesystem"
# Session(app)
# --- ▲▲▲ 削除ここまで ▲▲▲ ---


# --- ▼▼▼ Vertex AIの初期化 (変更なし) ▼▼▼ ---
vertexai.init(project=PROJECT_ID, location=LOCATION)
rag_retrieval_tool = Tool.from_retrieval(
    retrieval=rag.Retrieval(
        source=rag.VertexRagStore(
            rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS_PATH)]
        ),
    )
)
model = GenerativeModel("gemini-2.5-pro", tools=[rag_retrieval_tool])

# --- ▼▼▼ 削除 (Firestore DBクライアントの初期化) ▼▼▼ ---
# try:
#     db = firestore.Client(project=PROJECT_ID)
#     print("Firestoreクライアントの初期化に成功しました。")
# except Exception as e:
#     print(f"Firestoreクライアントの初期化に失敗しました: {e}")
#     db = None
# --- ▲▲▲ 削除ここまで ▲▲▲ ---

# --- ▼▼▼ プロンプトテンプレート (変更なし) ▼▼▼ ---
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
    - 小テストは3問で構成され、1問1点、満点は3点です。
# 成果物
上記の情報を基に、学習者への応答メッセージを1つだけ生成してください。
** 重要 ** 学習者がどのように答えればいいかを考えさせる認知負荷をできる限り軽くするような問いかけをしてください。
"""


# --- ▼▼▼ サービスアカウント認証クライアントのグローバル変数 ▼▼▼ ---
gspread_client = None


def get_gspread_client():
    """
    サービスアカウント認証済みのgspreadクライアントを取得する。
    初回呼び出し時に認証し、グローバル変数にキャッシュする。
    """
    global gspread_client
    if gspread_client:
        return gspread_client

    try:
        print(f"{SERVICE_ACCOUNT_FILE} を使って認証を開始します...")
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        gspread_client = gspread.authorize(creds)
        print("gspread サービスアカウント認証に成功しました。")
        return gspread_client
    except FileNotFoundError:
        print(f"エラー: {SERVICE_ACCOUNT_FILE} が見つかりません。")
        return None
    except DefaultCredentialsError:
        print("エラー: 認証情報が無効です。")
        return None
    except Exception as e:
        print(f"gspreadクライアント認証中にエラー: {e}")
        return None


# --- ▼▼▼ スプレッドシート読み込み関数 (変更なし) ▼▼▼ ---
def get_spreadsheet_by_id_as_dataframe(gspread_client, file_id, worksheet_name=None):
    """
    gspreadを使い、スプレッドシートIDで直接ファイルを開き、
    指定されたワークシートをDataFrameとして返す。
    """
    try:
        # 1. gspread でスプレッドシートを開く
        print(f"gspread で ID: {file_id} を読み込み開始...")
        spreadsheet = gspread_client.open_by_key(file_id)
        print(f"gspread で '{spreadsheet.title}' をオープン完了。")

        # 2. ワークシートを選択
        if worksheet_name:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.get_worksheet(0)
            print(
                f"ワークシート名が指定されなかったため、最初のシート '{worksheet.title}' を読み込みます。"
            )

        # 3. DataFrameとして取得
        print(f"gspread で '{worksheet.title}' をDataFrameに変換開始...")
        df = get_as_dataframe(worksheet)
        print(f"gspread で '{worksheet.title}' をDataFrameに変換完了。")

        if df.empty:
            print(f"ワークシート '{worksheet.title}' は空です。")
            if list(df.columns):
                return df
            else:
                return None

        df = df.dropna(how="all")
        print(f"ID: {file_id} の '{worksheet.title}' の読み込みに成功しました。")
        return df

    except gspread.exceptions.APIError as error:
        print(f"gspread APIエラー (ID: {file_id}): {error}")
        print(
            " -> もし 'PERMISSION_DENIED' なら、Google Cloudで 'Google Sheets API' が有効か、OAuth同意画面のスコープに 'spreadsheets.readonly' があるか確認してください。"
        )
        return None
    except gspread.exceptions.WorksheetNotFound:
        print(
            f"エラー: ワークシート '{worksheet_name}' が (ID: {file_id}) に見つかりません。"
        )
        return None
    except Exception as e:
        print(
            f"ID: {file_id} のスプレッドシート読み込み中に予期せぬエラーが発生しました: {e}"
        )
        traceback.print_exc()
        return None


# --- ▼▼▼ 削除 (Firestore ヘルパー関数) ▼▼▼ ---
# def get_chat_history(session_id):
#     (...)
# def save_chat_message(session_id, author, message):
#     (...)
# --- ▲▲▲ 削除ここまで ▲▲▲ ---


# --- ▼▼▼ Flask ルート設定 (デプロイ・デコイ版) ▼▼▼ ---


@app.route("/")
def index():
    """
    チャット画面 (index.html) を表示する。
    """
    return render_template("index.html")


# --- ▼▼▼ 削除 (get_history ルート) ▼▼▼ ---
# @app.route("/get_history", methods=["POST"])
# def get_history():
#    (...)
# --- ▲▲▲ 削除ここまで ▲▲▲ ---


@app.route("/chat", methods=["POST"])
def chat():
    print("チャットリクエストを受信しました。")
    try:
        user_message = request.json.get("message")
        # session_id = request.json.get("session_id") # <-- 削除

        if not user_message:
            return jsonify({"error": "メッセージがありません"}), 400
        # if not session_id:
        #     return jsonify({"error": "セッションIDがありません"}), 400

        # --- ▼▼▼ 履歴管理 (デコイ：常に空) ▼▼▼ ---
        chat_history = []  # 常に空の履歴
        # --- ▲▲▲ 履歴管理ここまで ▲▲▲ ---

        # --- ▼▼▼ 認証ロジック (サービスアカウント) ▼▼▼ ---
        client = get_gspread_client()
        if not client:
            return jsonify({"error": "サービスアカウント認証エラー"}), 500
        # --- ▲▲▲ 認証ロジックここまで ▲▲▲ ---

        target_user_id = 343

        # --- 視聴ログの取得 (IDで直接指定) ---
        log_file_id = "1bR6rfFwXzBi-CB6Beg0AlsK8rU2UpaapEjgTi4MYFGE"
        log_df = get_spreadsheet_by_id_as_dataframe(
            client, log_file_id, worksheet_name="No.1"
        )
        lecture_log_data = (
            log_df.to_string()
            if log_df is not None
            else "視聴ログが見つかりませんでした。"
        )

        # --- 小テスト結果の取得 (IDで直接指定) ---
        quiz_file_id = "1PKmB_IdMO3BmHVDHwHLxpqwdk1BsnHFEU-VdXpXGsqw"
        quiz_df = get_spreadsheet_by_id_as_dataframe(
            client, quiz_file_id, worksheet_name="フォームの回答 1"
        )
        if quiz_df is not None:
            quiz_df["idを入力してください"] = pd.to_numeric(
                quiz_df["idを入力してください"], errors="coerce"
            )
            user_quiz_result = quiz_df[
                quiz_df["idを入力してください"] == target_user_id
            ]
            quiz_result_data = (
                f"小テストNo.1: 総得点 {user_quiz_result['スコア'].iloc[0]}"
                if not user_quiz_result.empty
                else "テスト結果が見つかりませんでした。"
            )
        else:
            quiz_result_data = "テスト結果ファイルが見つかりませんでした。"

        # --- AI呼び出しロジック (変更なし) ---
        prompt = SYSTEM_PROMPT.format(
            history="\n".join(chat_history),  # AIには空の履歴を渡す
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
        # --- AI呼び出しここまで ---

        # --- ▼▼▼ 履歴管理 (デコイ：何もしない) ▼▼▼ ---
        # save_chat_message(session_id, "チューター", bot_response)
        # --- ▲▲▲ 履歴管理ここまで ▲▲▲ ---

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
    # Gunicorn (デプロイ時) から呼び出される際は、このブロックは実行されない
    # ローカルテスト時のみ実行される
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
