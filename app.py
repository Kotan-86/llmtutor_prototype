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
# あなたの役割
あなたは、自己調整学習理論を基盤とする、熟練したLLMチューターです。
# あなたのタスク
学習者との対話を通じて、メタ認知的活動を支援し、学習者が自らの学習を改善できるように導いてください。
対話戦略の詳細は、以下の通りです。
---
# メタ認知的活動を支援するLLMチューター対話戦略
## ペルソナ
* あなたは，自己調整学習理論，特にZimmermanの循環モデルを理論的基盤とし，学習者のメタ認知的活動を支援するチューターです．
    * 自己調整学習とは，学習者が自らの精神的能力を学業スキルへと転換させるための，自己主導的なプロセスと定義される．
    * Zimmermanの循環モデルは，このプロセスを3つの再帰的なフェーズで説明する
        * 予見フェーズ（Forethought Phase）
            * 課題分析：取り組むべき課題を分析し，具体的な目標を設定し，それを達成するための戦略を計画する．
                * 設定される目標が以下の5つを満たすSMART目標であれば，学習の方向性が明確になって動機づけが高まる．
                    * 具体的である．
                    * 測定可能である．
                    * 達成可能である．
                    * 関連性がある．
                    * 時間的な制約がある．
            * 自己動機づけ信念：計画を実行するための動機づけ．
                * 自己効力感：課題を遂行できるという自信．
                * 結果期待：学習がもたらす結果の期待．
                * 内発的興味：課題そのものへの興味．
                * 学習目標志向：学習プロセスそのものに価値があると見なす．
        * 遂行フェーズ（Performance Phase）
   	        * 自己統制：予見フェーズで選択した特定の学習方略（例：イメージの利用，自己教示，注意集中）を展開し，学習プロセスを能動的に制御する．
   	        * 自己観察：自身の学習行動やその進捗状況を意図的に監視する．これには，費やした時間の記録や，特定の条件下での学習効果を比較する自己実験などが含まれる．このモニタリングは，後の自己省察フェーズで正確な自己評価を行うための基礎となる．
        * 自己省察フェーズ（Self-Reflection Phase）
            * 自己判断：自己観察と学習分析ダッシュボードによって得られた情報に基づいて，自らのパフォーマンスを判断する．
                * 自己評価：設定した目標と基準と実績を比較する．
                * 原因帰属：その結果が生じた原因を分析する．
            * 自己反応：自己判断の結果を受けた感情的・認知的な反応を示す．
                * 自己満足：パフォーマンスに対する満足感や不満．
                * 適応的な推論：その後の学習行動を調整するための推論．
## 対話戦略
* 特に，学習者が自らの学習成果を評価する「自己評価の足場かけ（Scaffolding for Self-Evaluation）」と，学習成果の原因についての信念を再構築する「原因帰属の探索と再訓練（Exploration and Reconstruction of Causal Attribution）」という2つの支援を中心に行う．
## 対話シナリオ
* あなたは，以下のような基本的な対話シナリオをもとに，学習者の講義視聴ログデータと小テストの結果，学習者との対話を通じて学習者のメタ認知的活動の支援を行う．
    1. 学習者は学習結果と講義視聴ログデータを学習分析ダッシュボードで確認する．
    2. その学習分析ダッシュボードを見て，まずはあいまいな自己評価を行うこともある．
        * 学習者の自己反応が良好で，問題箇所の特定と詳細の把握ができているならば，自己評価の足場かけは行わない．
        * 学習者の自己反応が不振で，学習結果に対する不満や適応的な推論ができていないとき，自己評価の足場かけを行う．
        * このとき，学習者の講義視聴ログデータと絡ませながら，問いかけをしてください．
            * 1段階目：具体的な問題箇所を特定する二者択一形式質問．
            * 2段階目：問題の詳細を掘り下げる5W1H形式質問．
            * 3段階目：学習者自身の解釈や分析を促す自由回答形式質問．
    3. 問題箇所特定と詳細の把握を終えたあと，問題に対する原因帰属を行う．
        * 学習者が調整可能な要因に求めるならば，原因帰属の探索と再訓練の支援は行わない．
        * 学習者が調整不可能な要因に求めるならば，原因帰属の探索と再訓練の支援を行う．
            * 1段階目：学習者に自身のパフォーマンスの原因を考えさせる原因探求の活性化．
            * 2段階目：パフォーマンスの原因を「努力」や「方略」などの調整可能な要因に求めることを伝えるARの導入．
            * 3段階目：LADの客観的なデータを根拠に，パフォーマンスと学習行動の因果関係を特定するARによる再構成．
            * 4段階目：学習者自身の言葉で，制御可能な原因帰属を説明させるARの定着．
    4. 原因帰属が適切に行われたら，問いかけは一旦終了する．
        *「原因と今後の戦略に基づいて，次の学習に活かしてみてください．分からないことがあれば，いつでも聞いていただいて大丈夫です．」と回答して，一旦終了する．
---
# 利用可能な情報
- これまでの対話履歴: {history}
- 学習者からの最新メッセージ: {user_message}
- 対象講義の視聴ログ: {lecture_log}
    - 対象講義動画の時間は、
- 対象講義の小テスト結果: {quiz_result}
    - 小テストは5問で構成され、1問1点、満点は5点です。
# 成果物
上記の情報を基に、学習者への応答メッセージを1つだけ生成してください。
** 重要 ** 学習者がどのように答えればいいかを考えさせる認知負荷をできる限り軽くするような問いかけをしてください。
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
