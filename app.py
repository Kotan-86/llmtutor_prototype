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
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import gspread
from gspread_dataframe import get_as_dataframe
import io
import traceback
import httplib2
from google_auth_httplib2 import AuthorizedHttp

# SSL証明書なしのローカル環境で実行するための設定（開発時のみ）
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# --- ▼▼▼ 基本設定 ▼▼▼ ---
PROJECT_ID = "flash-adapter-475404-q6"
LOCATION = "us-east4"
RAG_CORPUS_PATH = (
    "projects/flash-adapter-475404-q6/locations/us-east4/ragCorpora/2227030015734710272"
)
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

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


def get_authenticated_credentials():
    """
    セッションから認証情報を取得し、必要ならリフレッシュして返す。
    失敗した場合は None を返す。
    """
    creds = None
    if "credentials" in session:
        print("セッションから認証情報を取得しています。")
        try:
            creds = Credentials.from_authorized_user_info(
                session["credentials"],
                scopes=SCOPES,
            )
        except Exception as e:
            print(f"認証情報の読み込み中にエラーが発生しました: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print(
                    "アクセストークンの有効期限が切れているため、リフレッシュを試みます。"
                )
                creds.refresh(Request())
                session["credentials"] = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                }
                print("トークンのリフレッシュに成功しました。")
            except Exception as e:
                print(f"トークンのリフレッシュ中にエラーが発生しました: {e}")
                return None
        else:
            return None

    if not creds or not creds.valid:
        return None

    print("Google APIの認証に成功しました。")
    return creds


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


def get_spreadsheet_by_id_as_dataframe(creds, file_id, worksheet_name=None):
    """
    gspreadを使い、スプレッドシートIDで直接ファイルを開き、
    指定されたワークシートをDataFrameとして返す。
    """
    try:
        # 1. gspread でスプレッドシートを開く
        print(f"gspread で ID: {file_id} を認証・読み込み開始...")
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(file_id)  # ★ IDで直接開く
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
            # ( ... 既存のロジックと同じ ... )
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
        # ★ gspread も内部で httplib2 を使うため、ここでタイムアウトする可能性も残っています
        print(
            f"ID: {file_id} のスプレッドシート読み込み中に予期せぬエラーが発生しました: {e}"
        )
        traceback.print_exc()
        return None


def get_spreadsheet_as_dataframe(creds, drive_service, file_name, worksheet_name=None):
    try:
        # 1. Drive APIでスプレッドシートのIDを検索
        # ★ どのファイルの検索を開始したかログに出す
        print(f"Drive API で '{file_name}' を検索開始...")
        query = f"name='{file_name}' and trashed=false and mimeType='application/vnd.google-apps.spreadsheet'"
        results = (
            drive_service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()  # <-- ここでタイムアウトしている
        )
        # ★ 検索が完了したことをログに出す
        print(f"Drive API で '{file_name}' を検索完了。")
        items = results.get("files", [])

        if not items:
            print(f"スプレッドシートが見つかりません: {file_name}")
            return None

        file_id = items[0].get("id")

        # 2. gspread でスプレッドシートを開く
        # ★ gspreadでの処理開始をログに出す
        print(f"gspread で '{file_name}' (ID: {file_id}) を認証・読み込み開始...")
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(file_id)
        print(f"gspread で '{file_name}' をオープン完了。")

        # 3. ワークシートを選択
        if worksheet_name:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.get_worksheet(0)
            print(
                f"ワークシート名が指定されなかったため、最初のシート '{worksheet.title}' を読み込みます。"
            )

        # 4. DataFrameとして取得
        # ★ DataFrameへの変換開始をログに出す
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

        print(f"'{file_name}' の '{worksheet.title}' の読み込みに成功しました。")
        return df

    except HttpError as error:
        # ★ どのファイルでエラーが出たか明記する
        print(f"'{file_name}' のDrive API検索中にHttpErrorが発生しました: {error}")
        return None
    except gspread.exceptions.WorksheetNotFound:
        print(
            f"エラー: ワークシート '{worksheet_name}' が '{file_name}' に見つかりません。"
        )
        return None
    except Exception as e:
        # ★ どのファイルでエラーが出たか明記する
        print(
            f"'{file_name}' のスプレッドシート読み込み中に予期せぬエラーが発生しました: {e}"
        )
        traceback.print_exc()
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

        creds = get_authenticated_credentials()
        if not creds:
            # 認証情報が無効になっている可能性
            return jsonify({"error": "authentication_required"}), 401

        # Drive APIサービスも構築（スプレッドシート検索のため）
        # try:
        #     # 1. タイムアウトを60秒に設定した「素の」http オブジェクトを作成
        #     http_client_base = httplib2.Http(timeout=60)
        #     # 2. 認証情報(creds)と素のhttpオブジェクトを組み合わせて、
        #     #    「認証済み」かつ「タイムアウト設定済み」の http オブジェクトを作成
        #     authorized_http_client = AuthorizedHttp(creds, http_client_base)
        #     # 3. 認証済みの http オブジェクトを使って service を構築
        #     drive_service = build("drive", "v3", http=authorized_http_client)
        # except HttpError as error:
        #     print(f"Driveサービス構築中にエラー: {error}")
        #     return jsonify({"error": "Driveサービス構築エラー"}), 500

        target_user_id = 343

        # --- 視聴ログの取得 (IDで直接指定) ---
        log_file_id = (
            "1bR6rfFwXzBi-CB6Beg0AlsK8rU2UpaapEjgTi4MYFGE"  # ★ ステップB-1で取得したID
        )
        # (注: "シート1" の部分は、実際のワークシート名に合わせてください)
        log_df = get_spreadsheet_by_id_as_dataframe(
            creds, log_file_id, worksheet_name="No.1"
        )
        lecture_log_data = (
            log_df.to_string()
            if log_df is not None
            else "視聴ログが見つかりませんでした。"
        )

        # --- 小テスト結果の取得 (IDで直接指定) ---
        quiz_file_id = "1PKmB_IdMO3BmHVDHwHLxpqwdk1BsnHFEU-VdXpXGsqw"
        quiz_df = get_spreadsheet_by_id_as_dataframe(
            creds, quiz_file_id, worksheet_name="フォームの回答 1"
        )
        if quiz_df is not None:
            # CSV読み込み時と同じデータ型変換と絞り込み
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

        # --- 以降のAI呼び出しロジックは変更なし ---
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
