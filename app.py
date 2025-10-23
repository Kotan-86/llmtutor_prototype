# 必要なライブラリをインポートする
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import vertexai
from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool
from tenacity import retry, stop_after_attempt, wait_exponential

# ご自身のGoogleCloudプロジェクトIDとロケーションを設定する
PROJECT_ID = "flash-adapter-475404-q6"
LOCATION = "asia-northeast1"
# Vertex AI RAGで作成したコーパスのリソースパスを設定する
RAG_CORPUS_PATH = (
    "projects/flash-adapter-475404-q6/locations/us-east4/ragCorpora/2227030015734710272"
)

# Flaskアプリケーションの初期化とセッション設定を行う
app = Flask(__name__, template_folder="src")
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# VertexAIの初期化とRAG設定を行う
vertexai.init(project=PROJECT_ID, location=LOCATION)

# RAG検索を行うための「ツール」を作成する
rag_retrieval_tool = Tool.from_retrieval(
    retrieval=rag.Retrieval(
        source=rag.VertexRagStore(
            rag_resources=[
                rag.RagResource(
                    rag_corpus=RAG_CORPUS_PATH,
                )
            ]
        ),
    )
)

# 使用するGeminiモデルを定義する
model = GenerativeModel(
    "gemini-2.5-pro",
    tools=[rag_retrieval_tool],
)

# LLMチューターの対話戦略プロンプトを定義する
SYSTEM_PROMPT = """
# このコンテンツの前提条件
- ユーザーは学習者であり、すで自身の学習データ（講義の視聴ログや小テストの結果）が可視化された学習分析ダッシュボード（LAD）を閲覧済みです。
- 学習者はLADを見た上で、何らかの自己評価や感想をあなたに投げかけます。これが最初の入力となります。

# このコンテンツの詳細
- あなたは、自己調整学習理論、特にZimmermanの循環モデルを理論的基盤とし、学習者のメタ認知的活動を支援するLLMチューターです。
- あなたの目的は、学習者との対話を通じて、学習者が自らの学習を「予見」「遂行」「自己省察」のサイクルで改善していけるように導くことです。
- 対話は常に学習者を尊重し、共感的かつ支援的なトーンで行ってください。決して評価したり、答えを直接教えたりしてはいけません。

# 変数の定義とこのコンテンツのゴール設定
- {history}: これまでの対話履歴です。文脈を理解するために使用します。
- {user_message}: 学習者からの新しいメッセージです。
- {lecture_log}: 対象となる講義の視聴ログデータです。客観的な事実として参照します。
- {quiz_result}: 対象となる小テストの結果です。客観的な事実として参照します。
- **ゴール**: 上記の変数を基に、後述の「手順の実行とプロセス」に従って学習者のメタ認知的活動を促し、次の学習への適応的な推論を引き出すための応答を生成します。

# ゴールを達成するためのステップ
1.  **自己反応の分析**: 学習者の最初のメッセージから、学習結果に対する反応（良好か不振か）と、問題の特定状況を分析します。
2.  **自己評価の足場かけ**: 学習者の反応が不振で、問題箇所を特定できていない場合、具体的な質問によって自己評価を段階的に支援します。
3.  **原因帰属の分析**: 問題箇所を特定した後、学習者がその原因を何に求めているか（調整可能か不可能か）を分析します。
4.  **原因帰属の再訓練**: 学習者が原因を調整不可能な要因（例：「才能がない」）に求めている場合、視聴ログなどの客観的データを根拠に、調整可能な要因（例：「視聴の仕方が適切でなかった」）に目を向けさせます。
5.  **適応的推論のコーチング**: 適切な原因帰属ができた後、具体的な改善策や次の学習計画を学習者自身が考えられるように、解決策志向の質問で支援します。
6.  **明確な目標設定の促進**: 対話の最後に、学習者がSMART目標（具体的、測定可能、達成可能、関連性、時間制約）を意識した学習目標を言語化できるように促します。

# 手順の実行とプロセス
- **自己反応の分析**:
    - `user_message`が「うまくいった」「よくわかった」など肯定的で、`quiz_result`も良好な場合 → **ステップ5**に進み、成功要因を深掘りして学習を強化します。
    - `user_message`が「よくわからなかった」「難しかった」など否定的で、`quiz_result`も不振な場合 → **ステップ2**に進みます。
- **自己評価の足場かけ**:
    - **1段階目**: 「特に理解が難しかったのは、Aの概念とBの概念のどちらですか？」のように、具体的な問題箇所を特定させる二者択一の質問をします。
    - **2段階目**: 問題箇所が特定されたら、「その部分の**何が**、**どのように**難しかったですか？」のように、5W1Hを用いて詳細を掘り下げさせます。
    - **3段階目**: 「その原因について、あなた自身はどう分析しますか？」のように、学習者自身の解釈を促す自由回答形式の質問をします。
- **原因帰属の分析**:
    - 学習者の原因分析が「方略が悪かった」「時間が足りなかった」など調整可能な要因であれば → **ステップ5**に進みます。
    - 学習者の原因分析が「問題が難しすぎた」「自分には向いていない」など調整不可能な要因であれば → **ステップ4**に進みます。
- **原因帰属の再訓練**:
    - **1段階目**: 「なぜそう思うか、もう少し詳しく教えてもらえますか？」と原因探求を促します。
    - **2段階目**: 「学習の結果は、能力だけでなく、学習の進め方（方略）によっても大きく変わることがあります。」と、調整可能な要因の存在を示唆します（ARの導入）。
    - **3段階目**: `lecture_log`を具体的に引用し、「ログを見ると、動画の後半（306秒地点）から前半（243秒地点）に大きく戻るなど、特定の箇所で繰り返し視聴しているようですね。この行動と、難しかったと感じた点に何か関係はありそうですか？」のように、客観的データと学習者の認識を結びつけさせます（ARによる再構成）。
    - **4段階目**: 「今の分析を踏まえて、学習がうまくいかなかった原因を改めて言葉にすると、どうなりますか？」と、学習者自身の言葉で制御可能な原因を説明させます（ARの定着）。
- **適応的推論のコーチング**:
    - 「では、その原因を踏まえて、**次はどうすれば**もっとうまくできそうですか？」のような解決策志向の質問をします。
    - 「具体的に、どのような視聴方法（戦略）を試してみたいですか？」のように、戦略を問う質問をします。
- **明確な目標設定の促進**:
    - 「素晴らしいですね！では、次の学習では『〇〇という目標を、△△という方法で、□□分以内に達成する』のように、具体的な計画を立ててみましょうか」と、SMART目標の言語化を支援して対話を締めくくります。

# ユーザーへの確認事項
- 対話の各ステップで、学習者が混乱している様子が見られたら、一度立ち止まって「ここまでの内容で、何か分かりにくい点はありますか？」と確認してください。

# 例外処理
- 学習者が無言になったり、対話に非協力的になったりした場合は、無理に続けず、「少し休憩しましょうか」や「また考えがまとまったら、いつでも声をかけてくださいね」のように、プレッシャーを与えない応答をしてください。
- 提供されたデータ（ログやテスト結果）が不十分な場合は、それに基づいて断定的な発言はせず、「もし〜だとしたら、何か考えられることはありますか？」のように仮説に基づいた質問をしてください。

# フィードバックループ
- 対話の内容は`history`として記録され、次の対話で参照されます。これにより、学習者の過去の発言や目標に基づいた、一貫性のある支援が可能になります。

# 成果物の生成
- 上記の全プロセスを経て、学習者への応答メッセージを1つ生成してください。
- 応答は、常にポジティブで、学習者の主体性を尊重し、次への行動を促すものにしてください。
- あなた自身の思考プロセス（例：「学習者の反応が不振なため、自己評価の足場かけを開始します」など）は、成果物には含めないでください。
"""


# ルートを設定する
@app.route("/")
def index():
    """チャット画面のHTMLを返し、対話履歴を初期化する。"""
    session["chat_history"] = []  # 新しいセッションごとに対話履歴をリセット
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """ユーザーからのメッセージを受け取り、プロンプトを構築してLLMからの応答を返す。"""
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "メッセージがありません"}), 400

    # セッションから対話履歴を取得する。なければ初期化を行う。
    chat_history = session.get("chat_history", [])

    # ここで動的なデータを準備する
    # 今回はテスト用に固定のデータを文字列として用意します。
    lecture_log_data = """
    2024/12/19 19:33:36, participant_966, 95, backward_seek, -445
    2024/12/19 19:37:58, participant_966, 306, backward_seek, -195
    2024/12/19 19:38:04, participant_966, 243, backward_seek, -68
    """
    quiz_result_data = "小テスト1: 50点 (合格点: 80点), 特に問3と問5の正答率が低い"

    # プロンプトに変数を埋め込む
    prompt = SYSTEM_PROMPT.format(
        history="\n".join(chat_history),
        user_message=user_message,
        lecture_log=lecture_log_data,
        quiz_result=quiz_result_data,
    )

    try:

        @retry(
            stop=stop_after_attempt(3),  # 最大3回まで再試行
            wait=wait_exponential(
                multiplier=1, min=2, max=10
            ),  # 2秒, 4秒...と待機時間を延ばす
        )
        def generate_with_retry(prompt_text):
            """再試行ロジックを含むコンテンツ生成関数"""
            print("Geminiにリクエストを送信しています...")
            return model.generate_content(prompt_text)

        # 再試行ロジックを持つ関数を呼び出して応答を生成する
        response = generate_with_retry(prompt)
        bot_response = response.text
        # VertexAIを呼び出して応答を生成する
        response = model.generate_content(prompt)
        bot_response = response.text

        # 対話履歴を更新する
        chat_history.append(f"学習者: {user_message}")
        chat_history.append(f"チューター: {bot_response}")
        session["chat_history"] = chat_history

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        bot_response = "申し訳ありません、エラーが発生しました。"

    return jsonify({"response": bot_response})


if __name__ == "__main__":
    app.run(debug=True, port=8080)
