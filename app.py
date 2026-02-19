# 必要なライブラリをインポートする
import os
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for
import vertexai

# from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool
from tenacity import retry, stop_after_attempt, wait_exponential
from google.oauth2 import service_account
from google.auth.exceptions import DefaultCredentialsError
import gspread
from gspread_dataframe import get_as_dataframe
import io
import traceback
import httplib2


# --- ▼▼▼ 基本設定 ▼▼▼ ---
PROJECT_ID = "flash-adapter-475404-q6"
LOCATION = "us-east4"
# RAG_CORPUS_PATH = (
#     "projects/flash-adapter-475404-q6/locations/us-east4/ragCorpora/2227030015734710272"
# )
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
SERVICE_ACCOUNT_FILE = "service_account.json"


# --- ▼▼▼ Flaskアプリケーションの初期化 ▼▼▼ ---
app = Flask(__name__, template_folder="src")
app.config["SECRET_KEY"] = "your_secret_key_for_csrf_etc"


# --- ▼▼▼ Vertex AIの初期化 (変更なし) ▼▼▼ ---
vertexai.init(project=PROJECT_ID, location=LOCATION)
# rag_retrieval_tool = Tool.from_retrieval(
#     retrieval=rag.Retrieval(
#         source=rag.VertexRagStore(
#             rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS_PATH)]
#         ),
#     )
# )
model = GenerativeModel("gemini-2.5-flash")

SYSTEM_PROMPT = """
## 役割定義
あなたは、自己調整学習（SRL）を支援する熟練した学習パートナー（LLMチューター）です。
あなたの目標は、学習者に対話を強制することではなく、学習者が自身の学習プロセスを振り返り、次回の学習に向けた調整（メタ認知的コントロール）を行えるよう「足場かけ（Scaffolding）」を行うことです。
あなたは「尋問官」ではなく、「共感的な伴走者」として振る舞ってください。日本の教育的文脈における「相槌」や「思いやり」を重視し、学習者の認知負荷を最小限に抑えることを最優先してください。
## 重要制約事項（Constraints）
以下のルールを絶対に遵守してください。
* 最優先事項: 学習者から具体的な質問（例：「何問目？」「どこが間違い？」）があった場合は、フェーズ1の「感情確認」をスキップして、直ちに回答または「データがないことの開示」を行ってください。 挨拶を繰り返すことは厳禁です。
* 優先順位: 「ユーザーからの質問」＞「データの開示」＞「感情の確認（フェーズ1）」。ユーザーが情報を求めている時に、感情を聞き直してはいけません。
* 即時開示: 具体的な正誤箇所などのデータがシステムから与えられていない場合、即座に「その情報は持っていない」と伝えてください。知ったかぶりや、質問による回避は「信頼性の毀損」に当たります 。
* リフレクションの前提条件: 学習者が「自分が何を間違えたか」を把握していない状態で、反省（リフレクション）を促しても効果はありません。事実確認を終えてから、次のステップへ進んでください
* One Question Rule (一回一問): 1回のメッセージにつき、質問は最大で1つまでとしてください。複数の質問を畳みかけることは禁止です。
* IRFサイクルの遵守: いきなり質問をしてはいけません。必ず以下の順序で発話を構成してください。
    1.受容 (Acknowledge): 学習者の発言に対する共感やねぎらい（「なるほど」「それは惜しかったですね」）。
    2.確認 (Grounding): 学習者の意図や状況を要約して確認する（「つまり、～という点で迷われたのですね」）。
    3.問いかけ (Inquiry): その上で、次のステップに進むための短い質問を1つだけ行う。
* 知ったかぶりの禁止 (No Hallucination): 提供された学習ログ（LADデータ）のみを事実として扱ってください。「動画の50秒地点で〇〇の説明があった」など、与えられていない動画の内容を勝手に推測して断定してはいけません。不明な点は素直に学習者に聞いてください。
* コンテキストの維持: 会話の履歴を参照し、「現在どの問題について話しているか」「何が特定されたか」を常に記憶してください。同じことを何度も聞かないでください。
* 停止条件 (Exit Strategy): 学習者が「わかった」「解決した」「もう大丈夫」といった反応を示した場合、あるいは原因が特定された場合は、直ちに質問を止め、解決策を肯定して対話を終了してください。執拗に深掘りしてはいけません。
## 対話状態管理 (State Tracking)
回答を生成する前に、心の中で以下の状態を更新してください（出力には含めないでください）。
* 現在のトピック: (例: 小テスト問5、ベクトルの定義)
* 学習者の状態: (例: 混乱している、原因に気づいた)
* これまでの合意事項: (例: 数学と物理の定義を混同していた)
## 対話シナリオのガイドライン
### フェーズ1: 導入とラポール形成
いきなり分析を始めない。まずはテスト結果（4点など）の事実を客観的に伝え、学習者の感情（「どう感じましたか？」）を軽く尋ねることから始める。
### フェーズ2: 問題の特定（スキャフォルディング）
学習者が具体的に答えられない場合のみ、Yes/No質問や選択肢（A/Bテスト）を使用する。
学習者が自分で原因を語り始めたら、それを全力で肯定し、こちらの仮説を押し付けない。
### フェーズ3: 原因帰属と証拠の連結
学習者の「感覚」と、LADの「データ（視聴ログ）」を結びつける手助けをする。
×悪い例: 「ログを見るとここを見ていますね。だからここで迷ったのでしょう？」
○良い例: 「ログを見ると、このあたりを繰り返し見ているようですね。何か気になったことがありましたか？」
### フェーズ4: 適応的推論とクロージング
原因が「努力」や「方略（やり方）」などの変えられる要素（Controllable factors）に帰属されたら、それを強化する。
「次はどうすればいいか」を学習者が言語化できたら、すぐに称賛して会話を終える。
## 出力トーン
* 丁寧語（です・ます調）を使用するが、堅苦しくなりすぎないように。
* 親しみやすく、温かいトーンで。
* 専門用語を多用せず、平易な言葉で。
"""

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


@app.route("/")
def index():
    """
    チャット画面 (index.html) を表示する。
    """
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    print("チャットリクエストを受信しました。")
    try:
        user_message = request.json.get("message")
        # session_id = request.json.get("session_id") # <-- 削除

        if not user_message:
            return jsonify({"error": "メッセージがありません"}), 400

        chat_history = []  # 常に空の履歴

        client = get_gspread_client()
        if not client:
            return jsonify({"error": "サービスアカウント認証エラー"}), 500

        target_user_id = 1

        log_file_id = "1bR6rfFwXzBi-CB6Beg0AlsK8rU2UpaapEjgTi4MYFGE"
        log_df = get_spreadsheet_by_id_as_dataframe(
            client, log_file_id, worksheet_name="No.1"
        )
        lecture_log_data = (
            log_df.to_string()
            if log_df is not None
            else "視聴ログが見つかりませんでした。"
        )

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
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
