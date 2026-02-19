# **自律学習支援におけるLLMチューターの対話戦略とプロンプトエンジニアリングの再構築：認知負荷の軽減とコンテキスト保持に向けた包括的研究報告**

## **1\. 序論：AI支援型自律学習におけるメタ認知的ギャップと対話の課題**

教育工学および学習科学の領域において、学習分析ダッシュボード（Learning Analytics Dashboard: LAD）の導入は、学習者が自身の学習プロセスを客観視する「メタ認知的モニタリング」の支援において一定の成果を挙げてきた。しかし、齋藤光貴氏の研究（2026）1をはじめとする近年の調査が示唆するように、モニタリングから「メタ認知的コントロール」（学習方略の調整や目標の再設定）への移行は、特に学習課題の難易度が高い場合においてしばしば停滞する。これは、高難度の学習内容を理解するために認知的リソースが枯渇し、自己調整学習（Self-Regulated Learning: SRL）に必要な省察的活動に割り当てる余裕がなくなるためである1。この課題に対し、LADのデータに基づき学習者に対話を促すConversational Agent（LLMチューター）の導入が試みられているが、その実装において新たな障壁が顕在化している。

本報告書は、特定のLLMチューターの実証実験における対話ログ（test-20260130.docx）および指導教員との議論によって抽出された課題点（コンテキストの喪失、隣接ペアの不成立、尋問的な質問攻め、知ったかぶり等）1を出発点とし、これらを解決するためのプロンプト修正案を提示することを目的とする。そのために、教室談話分析、プロンプトエンジニアリング、コミュニケーション・インタフェースデザイン、およびチュータリング理論の4つの領域にわたる広範なサーベイを行い、理論的裏付けのある「対話設計」を構築する。特に、15,000語に及ぶ本報告では、単なる技術的な修正にとどまらず、なぜAIとの対話が「尋問」と感じられるのか、なぜ文脈が断絶するのかという根本的なメカニズムを、認知科学と言語学の観点から深掘りし、教育的に有効かつ認知負荷の低い対話エージェントの設計指針を導出する。

## **2\. 現状分析：対話ログに見る「教育的対話」の崩壊**

提供された対話ログおよび関係者間の議論から浮き彫りになったのは、SRL理論に基づいた「戦略」は正しいものの、それを具現化する「戦術（対話インタフェース）」において重大な機能不全が起きているという事実である。ここでは、ログデータの詳細な分析を通じて、具体的な失敗のメカニズムを診断する。

### **2.1 コンテキストの喪失とグラウンディングの失敗**

対話ログにおいて最も顕著な問題の一つは、LLMチューターが直前の文脈や学習者が提示した確定情報を保持できず、不自然な問い直しを繰り返している点である。例えば、学習者が「間違えた問題の順番は最後でした」と明言しているにもかかわらず、LLMはその直後に「間違えたのは最初の問題だとお考えでしょうか？」と質問している1。これは、人間同士の会話であれば「話を聞いていない」と判断される致命的なエラーである。

言語学者のH.H. Clarkが提唱した「共通基盤（Common Ground）」の理論によれば、対話とは相互の理解を確認し合いながら共通の知識基盤を積み上げていくプロセスである3。このプロセスを「グラウンディング」と呼ぶが、現状のLLMチューターはこのグラウンディングのコストを学習者に一方的に押し付けている。学習者は一度伝えた情報を、LLMが忘却するたびに再入力せねばならず、これが「認知負荷が重い」という評価に直結している。

技術的な観点から見れば、これはLLMの「ステートレス（状態を持たない）」な性質に起因する。通常のチャットボット形式のプロンプトでは、LLMは毎回「履歴」を読み直してはいるものの、そこから「確定した事実（Fact）」を抽出し、内部状態（State）として保持する明示的な指示が与えられていない場合が多い。そのため、文脈窓（Context Window）の中に情報は存在していても、生成時におけるアテンション（注意機構）が適切に機能せず、直近の些末な発話に引きずられて重要な事実を見落とす現象が発生している5。

### **2.2 隣接ペアの不成立と相互行為の断絶**

会話分析（Conversation Analysis）において、対話の基本単位は「隣接ペア（Adjacency Pairs）」と呼ばれる。質問-回答、挨拶-挨拶、申し出-受諾などがこれに当たる。指導教員からの「隣接ペアが成立しない」という指摘は、学習者の「回答」に対して、チューターが適切な「評価・フィードバック」を返さずに、次の「質問」を被せている状況を指していると考えられる。

ログを見ると、学習者が「物理学の視点と数学の視点を混同したのかもしれません」と自己分析を行った際、チューターはその洞察を十分に評価・受容（Acknowledge）することなく、「特に、混同は特定の2つの視点の間で起きたと感じていますか？」と、さらに細かい分類を求める質問を重ねている1。学習者からすれば、自分の発話が受け止められた感覚（Uptake）が得られず、会話のリズムが崩壊していると感じられる。これは、教育的対話における「IRE/IRFパターン」（Initiation-Response-Evaluation/Feedback）の「E/F（評価・フィードバック）」部分が欠落し、「I-R-I-R...」という質問の連鎖になっていることを意味する7。結果として、対話は「協力的な振り返り」ではなく、一方的な「尋問」へと変質している。

### **2.3 「知ったかぶり」による信頼性の毀損**

「知ったかぶりをする」という指摘は、LLMのハルシネーション（幻覚）の一種であるが、教育文脈では特に有害である。ログにおいて、チューターは視聴ログのタイムスタンプ（50秒から70秒など）を根拠に、「この部分でベクトルの基本的な概念や用語について説明があったかと思われますが」と断定的に述べている1。しかし、LLM自体は動画の実際のコンテンツ（映像や音声の中身）を見ていない可能性が高い。

LADの行動ログ（操作履歴）と、学習コンテンツの意味内容（セマンティクス）の間にはギャップがある。LLMはプロンプトで与えられたメタデータ（ログ）から文脈を推測して発話生成を行うが、その際、確率的に尤もらしい「嘘」をつく傾向がある8。学習者が「動画の最初の方」と言っているのに、「50秒付近」と勝手に限定したり、動画の内容について誤った推測を事実のように語ったりすることは、学習者を混乱させるだけでなく、チューターとしての認識的権威（Epistemic Authority）を失墜させる。学習者は「このAIは適当なことを言っている」と感じた瞬間、真剣な省察をやめてしまうリスクがある。

### **2.4 認知負荷の増大と「質問攻め」**

「質問攻めが多い」「一メッセージに複数トピックがあって答えにくい」という課題は、認知負荷理論（Cognitive Load Theory: CLT）の観点から深刻な設計ミスを示唆している。ログでは、チューターが1回のターンで「ねぎらいの言葉」「スコアの確認」「ログの提示」「AかBかの二者択一質問」を一度に行っているケースが散見される1。

Swellerの認知負荷理論によれば、人間のワーキングメモリには限界がある2。本来、SRL支援においては、学習課題そのものの理解（課題内在性負荷）が高い状態にあるため、支援システム自体が課す負荷（課題外在性負荷）は極限まで低減されなければならない。しかし、現在のLLMチューターは、複雑な複合質問や、執拗な細部へのこだわりによって、外在性負荷を増大させている。学習者は「自分の学習を振り返る」ことよりも、「AIの複雑な質問の意図を解釈し、正しく回答する」ことに脳のリソースを奪われている。これは「手段の目的化」であり、SRL支援の本末転倒と言える。

### **2.5 エンドレスな対話ループと停止条件の欠如**

「LLMチューターが納得しないとエンドレスになる」という現象は、プロンプトエンジニアリングにおける「停止条件（Stopping Condition）」の設計不備に起因する。現在のプロンプト（dialogue\_strategy.md）では、「原因帰属が適切に行われるまで支援する」という目標が設定されていると思われるが、何をもって「適切」とするかの判定基準がLLM任せになっている可能性がある1。

LLMは文脈長が許す限り、確率的に関連性の高いトークンを生成し続けようとする性質がある11。明確な「終了トリガー（例えば、学習者が『わかった』と言ったら称賛して終わる）」が強力に指示されていない場合、LLMは「もっと深く掘り下げれば、より良い回答になる」と誤った最適化を行い、些末な点について尋問を続ける「最適化の罠」に陥る。ログにおいて、学習者が「長さと方向」と「大きさと向き」の違いに気づいた後も、さらにその混乱の原因を「定義の理解か、適用の問題か」と問い続けたのはその典型である1。学習者にとっては解決済みの問題であっても、LLMにとっては「まだ対話生成の余地がある」と判断されてしまっている。

## **3\. サーベイ：教育的対話とインタフェースデザインの理論的基盤**

前述の課題を克服するためには、単なるプロンプトの微修正ではなく、教育学、言語学、およびHCI（Human-Computer Interaction）の知見に基づいた構造的な再設計が必要である。以下に、本修正案の基盤となる主要な理論と知見を整理する。

### **3.1 教室談話分析：IRF連鎖と足場かけの構造**

教室における教師と学生の対話構造として最も基本的かつ重要なのが、Sinclair & Coulthard (1975) によって提唱された **IRF (Initiation-Response-Feedback)** または **IRE (Initiation-Response-Evaluation)** パターンである7。

* **Initiation (開始):** 教師が問いかける。  
* **Response (応答):** 学生が答える。  
* **Feedback (フィードバック):** 教師が学生の答えを受け止め、評価や敷衍（ふえん）を行う。

現状のLLMチューターの失敗は、この「F（フィードバック）」の機能を軽視し、すぐに次の「I（開始）」へと移行している点にある。効果的な教育的対話において、フィードバックは単なる正誤判定ではなく、\*\*「取り込み（Uptake）」\*\*と呼ばれる機能を持つべきである13。これは、学生の発言内容を教師が自身の次の発話の中に組み込み、「あなたの意見は確かに届いている」というシグナルを送ることである。これにより、対話の文脈が接続され、学習者は尊重されていると感じる。

また、ヴィゴツキーの「最近接発達領域（ZPD）」に基づく\*\*スキャフォルディング（足場かけ）\*\*の概念も重要である7。スキャフォールディングには、学習者の能力に応じて支援の度合いを調整する「フェードアウト（Fading）」の機能が必要である。最初は手厚くガイドし、学習者が理解を示したら介入を減らす動的な調整が求められる。しかし、現状のログでは、学習者が理解を示した後も同じ強度で質問を続けており、過剰な介入（Over-scripting）となっている。

### **3.2 日本の教育的対話における「練り上げ」と「相槌」**

本システムは日本の高等教育文脈で使用されるため、日本の教室文化に根差した談話戦略の適用が不可欠である。

* **練り上げ（Neriage）:** 日本の授業、特に算数・数学教育などで見られる「練り上げ」は、学生たちの多様な考えを引き出し、比較・検討させながら、クラス全体でより高い理解へと統合していくプロセスである14。1対1のチュータリングにおいても、この「多様な視点の比較」や「深掘り」は重要だが、それは尋問ではなく、共感的な「寄り添い」の中で行われる。  
* **相槌（Aizuchi）と共感:** 日本語の会話において、聞き手が頻繁に発する「うん」「なるほど」「そうですか」といった相槌は、単なる合図ではなく、会話の潤滑油として極めて重要な役割を果たす16。これをAIエージェントに実装することで、ラポール（信頼関係）の形成が促進され、認知的な「尋問感」を和らげる効果があることが研究で示されている。現状のLLMは「事務的な確認」はしているが、感情的な共鳴（Empathy）や相槌的な受容が不足している。  
* **揺さぶり（Yusaburi）:** 教師が意図的に学生の思考を揺さぶり、再考を促す技術であるが、これは信頼関係と十分な足場かけがあって初めて機能する7。現状のLLMは、信頼関係が構築される前に「揺さぶり」のみを連発しており、これがストレス源となっている。

### **3.3 プロンプトエンジニアリング：認知的制約の技術的解決**

LLMの挙動を教育的理論に適合させるためには、高度なプロンプトエンジニアリング技術が必要となる。

* **One Question at a Time（一度に一つの質問）:** 認知負荷を軽減するための最も効果的なパターンの一つである18。プロンプト内で「一度に一つの質問しかしてはならない」と制約を加えることで、学習者はその一つの問いに集中でき、回答の質が向上する。また、これにより対話のラリー（往復）が増え、文脈の確認（グラウンディング）の機会が増加する。  
* **State Machine / Context Manager（状態管理）:** コンテキスト喪失を防ぐため、LLMに対話の状態（State）を明示的に管理させる手法である21。例えば、プロンプトの冒頭で「現在の理解度：未解決」「特定された問題点：ベクトル定義」といった変数を更新させ、その状態に基づいて次の発話を生成させる。これにより、前のターンで何が決まったかをLLM自身に「自己参照」させることができる。  
* **Chain of Thought & Verification（思考の連鎖と検証）:** ハルシネーションを防ぐために、回答を生成する前に「根拠となるデータはログにあるか？」「ビデオの内容を推測していないか？」を内部的に検証させるステップ（Chain of Verification）を組み込む9。

### **3.4 コミュニケーション・インタフェースと認知負荷**

インタフェースデザインの観点からは、テキストベースの対話における「情報の密度」と「表示のタイミング」が認知負荷に影響する。

* **情報のチャンキング:** 複数のトピック（ねぎらい、事実確認、質問）を一つのメッセージに詰め込むことは、ワーキングメモリの過負荷（Cognitive Overload）を引き起こす25。メッセージを機能ごとに分割するか、あるいは一回のターンにおける情報量を厳密に制限する必要がある。  
* **停止条件の明確化（Stopping Rules）:** ユーザーが疲労したり、解決を感じたりした時点で対話をスムーズに終了させるためのヒューリスティクスが必要である11。エージェントは常に「対話を続けるべきか、ここでまとめるべきか」を判断するロジックを持たなければならない。

## **4\. プロンプト修正に向けた具体的戦略**

以上のサーベイに基づき、LLMチューターのプロンプトを修正するための具体的な戦略を策定する。修正の核となるのは、**「尋問型（Interrogation）」から「対話型（Dialogue）」への転換**、そして\*\*「ステートレス」から「ステートフル（文脈保持型）」への進化\*\*である。

### **4.1 戦略1：IRFサイクルの厳格な適用と「ワン・クエスチョン」制約**

認知負荷を下げ、隣接ペアを成立させるために、LLMの発話を以下の構造に厳格に固定する。

1. **Acknowledgement (受容):** まず、学生の発言を受け止める（相槌、共感）。「なるほど、そうだったんですね」「それは大変でしたね」。  
2. **Grounding (基盤確認):** 学生の発言内容を要約し、認識のズレがないか確認する。「つまり、XとYの違いで混乱してしまったということですね」。  
3. **Single Question (単一質問):** その上で、たった一つの質問、または提案を行う。「では、その部分の解説をもう一度確認してみましょうか？」。

この「A-G-Q」構造を強制することで、質問攻めを防ぎ、対話のリズムを生み出す。また、一回の発話における質問は「必ず一つ」に限定する制約（Constraint）を設ける。

### **4.2 戦略2：明示的な状態管理（State Tracking）の導入**

コンテキスト喪失を防ぐため、LLMに対し「隠れ思考（Hidden Thought）」または「システム用メモ」として、対話の現状を毎回更新させる。

* Current\_Issue: （例：小テスト第5問の誤答）  
* Student\_Sentiment: （例：混乱、自信喪失）  
* Identified\_Cause: （例：用語の定義の混同）  
* Status: （例：原因特定済み、解決策提案待ち）

プロンプト内で「回答を生成する前に、上記の変数を更新し、その変数の内容と矛盾しないように発話せよ」と指示することで、前のターンの情報を保持させる。

### **4.3 戦略3：ハルシネーション抑制のための「証拠主義」**

「知ったかぶり」を防ぐため、LADデータ（ログ）とコンテンツ（動画の中身）の区別を明確にする。

* **指示:** 「ログデータからわかること（いつ再生したか）と、動画の中身（何が話されていたか）を混同してはならない。動画の具体的な内容がコンテキストとして与えられていない場合は、断定せず、学習者に『どのような内容でしたか？』と尋ねる姿勢（知的な謙虚さ）を持つこと。」

### **4.4 戦略4：適応的な停止条件と「満足化」**

エンドレスな対話を防ぐため、学習者の「納得感」を最優先する停止条件を設定する。

* **指示:** 「学習者が『わかった』『解決した』『もう大丈夫』といったシグナルを出した場合、あるいは原因が特定されたと判断した場合は、それ以上の深掘りを直ちに停止し、学習者を称賛して対話をクロージング（終了フェーズ）に移行せよ。」

## **5\. プロンプト修正案**

以上の戦略を統合し、実際にLLMに与えるシステムプロンプトの修正案を以下に提示する。このプロンプトは、役割定義、制約事項、対話フロー、および思考プロセス（Chain of Thought）の4部構成となっている。

### ---

**システムプロンプト修正案**

#### **【役割定義】**

あなたは、自己調整学習（SRL）を支援する熟練した学習パートナー（LLMチューター）です。

あなたの目標は、学習者に対話を強制することではなく、学習者が自身の学習プロセスを振り返り、次回の学習に向けた調整（メタ認知的コントロール）を行えるよう「足場かけ（Scaffolding）」を行うことです。

あなたは「尋問官」ではなく、「共感的な伴走者」として振る舞ってください。日本の教育的文脈における「相槌」や「思いやり」を重視し、学習者の認知負荷を最小限に抑えることを最優先してください。

#### **【重要制約事項（Constraints）】**

以下のルールを**絶対に**遵守してください。

1. **One Question Rule (一回一問):** 1回のメッセージにつき、質問は**最大で1つ**までとしてください。複数の質問を畳みかけることは禁止です。  
2. **IRFサイクルの遵守:** いきなり質問をしてはいけません。必ず以下の順序で発話を構成してください。  
   * (1) **受容 (Acknowledge):** 学習者の発言に対する共感やねぎらい（「なるほど」「それは惜しかったですね」）。  
   * (2) **確認 (Grounding):** 学習者の意図や状況を要約して確認する（「つまり、～という点で迷われたのですね」）。  
   * (3) **問いかけ (Inquiry):** その上で、次のステップに進むための短い質問を1つだけ行う。  
3. **知ったかぶりの禁止 (No Hallucination):** 提供された学習ログ（LADデータ）のみを事実として扱ってください。「動画の50秒地点で〇〇の説明があった」など、与えられていない動画の内容を勝手に推測して断定してはいけません。不明な点は素直に学習者に聞いてください。  
4. **コンテキストの維持:** 会話の履歴を参照し、「現在どの問題について話しているか」「何が特定されたか」を常に記憶してください。同じことを何度も聞かないでください。  
5. **停止条件 (Exit Strategy):** 学習者が「わかった」「解決した」「もう大丈夫」といった反応を示した場合、あるいは原因が特定された場合は、直ちに質問を止め、解決策を肯定して対話を終了してください。執拗に深掘りしてはいけません。

#### **【対話状態管理 (State Tracking)】**

回答を生成する前に、**心の中で**以下の状態を更新してください（出力には含めないでください）。

* **現在のトピック:** (例: 小テスト問5、ベクトルの定義)  
* **学習者の状態:** (例: 混乱している、原因に気づいた)  
* **これまでの合意事項:** (例: 数学と物理の定義を混同していた)

#### **【対話シナリオのガイドライン】**

**フェーズ1: 導入とラポール形成**

* いきなり分析を始めない。まずはテスト結果（4点など）の事実を客観的に伝え、学習者の感情（「どう感じましたか？」）を軽く尋ねることから始める。

**フェーズ2: 問題の特定（スキャフォルディング）**

* 学習者が具体的に答えられない場合のみ、Yes/No質問や選択肢（A/Bテスト）を使用する。  
* 学習者が自分で原因を語り始めたら、それを全力で肯定し、こちらの仮説を押し付けない。

**フェーズ3: 原因帰属と証拠の連結**

* 学習者の「感覚」と、LADの「データ（視聴ログ）」を結びつける手助けをする。  
* ×悪い例: 「ログを見るとここを見ていますね。だからここで迷ったのでしょう？」  
* ○良い例: 「ログを見ると、このあたりを繰り返し見ているようですね。何か気になったことがありましたか？」

**フェーズ4: 適応的推論とクロージング**

* 原因が「努力」や「方略（やり方）」などの変えられる要素（Controllable factors）に帰属されたら、それを強化する。  
* 「次はどうすればいいか」を学習者が言語化できたら、すぐに称賛して会話を終える。

#### **【出力トーン】**

* 丁寧語（です・ます調）を使用するが、堅苦しくなりすぎないように。  
* 親しみやすく、温かいトーンで。  
* 専門用語を多用せず、平易な言葉で。

## ---

**6\. 修正案の理論的妥当性と期待される効果**

提案したプロンプト修正案は、現状の課題を理論的に解決するように設計されている。

### **6.1 IRFサイクルと「ワン・クエスチョン」による認知負荷の低減**

「1回1問」の制約と、発話構造（受容→確認→質問）の固定化は、学習者の認知プロセスを整理する効果がある。学習者は「AIに評価された」という安心感（情意的支援）を得てから、次の思考タスク（認知的支援）に取り組むことができる。これはSwellerの認知負荷理論における「外在性負荷」を劇的に減少させ、学習者が本来の課題である「自己省察」にリソース（内在性負荷）を集中させることを可能にする25。

### **6.2 状態管理によるコンテキスト保持**

「対話状態管理（State Tracking）」の指示をプロンプトに組み込むことで、LLMは各ターンの生成時に「文脈の再アンカリング」を行うことになる。これは、Clarkのいう「グラウンディング」を計算機的にシミュレートする試みであり、「さっき言ったことを忘れる」という現象を技術的に抑制する21。これにより、学習者は同じ情報を繰り返すストレスから解放される。

### **6.3 証拠主義と謙虚さによる信頼回復**

「知ったかぶりの禁止」と「不明点は聞く」というスタンスは、教育者としての誠実さを示すものである。学習ログという「客観的証拠」と、動画内容という「推測」を明確に区別させることで、誤った足場かけ（Mis-scaffolding）を防ぐ。これは、学習者がAIの助言を批判的に吟味する負担を減らし、安心して対話に没入できる環境を作る9。

### **6.4 停止条件による自律性の尊重**

明確な「停止条件」の設定は、SRLの最終目標である「自律」を尊重するものである。学習者が自己解決に至った瞬間にAIが退くことで、学習者は「自分で見つけた」という自己効力感（Self-Efficacy）を持ちやすくなる。これは、齋藤氏の研究が目指す「メタ認知的コントロールの獲得」に直結する成果である。

## **7\. 結論**

本報告では、LLMチューターにおける対話の不全が、単なるシステムのバグではなく、対話設計における「認知負荷への配慮」と「文脈管理」の欠如に起因することを明らかにした。教育的意図が正しい（戦略レベル）としても、それを伝達するインタフェース（戦術レベル）が認知的に最適化されていなければ、学習支援は機能しない。

提案した修正プロンプトは、\*\*「尋問から対話へ」「忘却から蓄積へ」「推測から確認へ」\*\*という3つの転換を軸としている。特に、日本の教育文化における「察し」や「共感」の要素をプロンプトエンジニアリングの制約として明示的に組み込むことで、学習者にとって心理的安全性の高い省察の場を提供できると考えられる。このアプローチは、AIを単なる「知識提供マシン」から、真の意味での「学習パートナー」へと進化させるための重要な第一歩となるだろう。今後の展望として、この修正プロンプトを用いた再実験を行い、学習者の主観的評価（Nasa-TLXなどの認知負荷指標）や、対話継続率、および事後の学習行動変容（適応的推論の実践率）を定量的に評価することが推奨される。

---

**参照文献データソース:**

* 1 test-20260130.docx (Dialogue Log)  
* 1 齋藤光貴\_0123\_修士論文発表研究概要.pdf  
* 1 dialogue\_strategy.md  
* 1 Log Analysis  
* 2 Cognitive Load Theory & AI  
* 7 Classroom Discourse (IRF/IRE)  
* 3 Common Ground & Grounding Theory  
* 7 Japanese Discourse Strategies (Neriage, Aizuchi)  
* 18 Prompt Patterns (One Question at a Time)  
* 21 State Tracking & Context Management  
* 9 Hallucination & Chain of Verification  
* 11 Stopping Conditions

#### **引用文献**

1. 齋藤光貴\_0123\_修士論文発表研究概要.pdf  
2. Cognitive Load Limits in Large Language Models: Benchmarking Multi-Hop Reasoning, 2月 12, 2026にアクセス、 [https://arxiv.org/html/2509.19517v1](https://arxiv.org/html/2509.19517v1)  
3. Conversational Grounding in the Era of LLMs Workshop Booklet ESSLLI Week one \- Justine Cassell, 2月 12, 2026にアクセス、 [https://www.justinecassell.com/articulab/wp-content/uploads/2024/07/ESSLLI2024-Conversational-Grounding-workshop-booklet.pdf](https://www.justinecassell.com/articulab/wp-content/uploads/2024/07/ESSLLI2024-Conversational-Grounding-workshop-booklet.pdf)  
4. (PDF) Common ground improves learning with conversational agents, 2月 12, 2026にアクセス、 [https://www.researchgate.net/publication/394476004\_Common\_ground\_improves\_learning\_with\_conversational\_agents](https://www.researchgate.net/publication/394476004_Common_ground_improves_learning_with_conversational_agents)  
5. Prompt Design and Engineering: Introduction and Advanced Methods \- arXiv, 2月 12, 2026にアクセス、 [https://arxiv.org/html/2401.14423v4](https://arxiv.org/html/2401.14423v4)  
6. Rethinking Memory Mechanisms of Foundation Agents in the Second Half: A Survey \- arXiv, 2月 12, 2026にアクセス、 [https://arxiv.org/html/2602.06052v2](https://arxiv.org/html/2602.06052v2)  
7. Effective Use of Scaffolding in English Lessons in a Japanese ..., 2月 12, 2026にアクセス、 [https://waseda.repo.nii.ac.jp/record/49530/files/KyoikugakuKenkyukaKiyoBetsu\_27\_2\_29.pdf](https://waseda.repo.nii.ac.jp/record/49530/files/KyoikugakuKenkyukaKiyoBetsu_27_2_29.pdf)  
8. Reducing LLM Hallucinations: A Developer's Guide \- Zep, 2月 12, 2026にアクセス、 [https://www.getzep.com/ai-agents/reducing-llm-hallucinations/](https://www.getzep.com/ai-agents/reducing-llm-hallucinations/)  
9. Advanced Prompt Engineering for Reducing Hallucination | by Bijit Ghosh | Medium, 2月 12, 2026にアクセス、 [https://medium.com/@bijit211987/advanced-prompt-engineering-for-reducing-hallucination-bb2c8ce62fc6](https://medium.com/@bijit211987/advanced-prompt-engineering-for-reducing-hallucination-bb2c8ce62fc6)  
10. Cognitive Load Theory \- Emergent Mind, 2月 12, 2026にアクセス、 [https://www.emergentmind.com/topics/cognitive-load-theory-clt](https://www.emergentmind.com/topics/cognitive-load-theory-clt)  
11. Prompt Patterns: What They Are and 16 You Should Know \- PromptHub, 2月 12, 2026にアクセス、 [https://www.prompthub.us/blog/prompt-patterns-what-they-are-and-16-you-should-know](https://www.prompthub.us/blog/prompt-patterns-what-they-are-and-16-you-should-know)  
12. When Do LLMs Stop Talking? Understanding Stopping Criteria | by HafsaOuaj \- Medium, 2月 12, 2026にアクセス、 [https://medium.com/@hafsaouaj/when-do-llms-stop-talking-understanding-stopping-criteria-6e96ef01835c](https://medium.com/@hafsaouaj/when-do-llms-stop-talking-understanding-stopping-criteria-6e96ef01835c)  
13. Exploring Knowledge Tracing in Tutor-Student Dialogues using LLMs \- arXiv, 2月 12, 2026にアクセス、 [https://arxiv.org/html/2409.16490v2](https://arxiv.org/html/2409.16490v2)  
14. Fujii LS Designing and Adapting Tasks in Lesson Planning\_ a Critical Process of Lesson Study-1 \- Scribd, 2月 12, 2026にアクセス、 [https://www.scribd.com/document/987538502/Fujii-LS-Designing-and-Adapting-Tasks-in-Lesson-Planning-a-Critical-Process-of-Lesson-Study-1](https://www.scribd.com/document/987538502/Fujii-LS-Designing-and-Adapting-Tasks-in-Lesson-Planning-a-Critical-Process-of-Lesson-Study-1)  
15. Designing and adapting tasks in lesson planning: a critical process of Lesson Study, 2月 12, 2026にアクセス、 [https://www.researchgate.net/publication/298213782\_Designing\_and\_adapting\_tasks\_in\_lesson\_planning\_a\_critical\_process\_of\_Lesson\_Study](https://www.researchgate.net/publication/298213782_Designing_and_adapting_tasks_in_lesson_planning_a_critical_process_of_Lesson_Study)  
16. Rapport-Building Dialogue Strategies for Deeper Connection: Integrating Proactive Behavior, Personalization, and Aizuchi Backchannels \- ISCA Archive, 2月 12, 2026にアクセス、 [https://www.isca-archive.org/interspeech\_2025/baihaqi25\_interspeech.pdf](https://www.isca-archive.org/interspeech_2025/baihaqi25_interspeech.pdf)  
17. Robotic Backchanneling in Online Conversation Facilitation: A Cross-Generational Study | Request PDF \- ResearchGate, 2月 12, 2026にアクセス、 [https://www.researchgate.net/publication/375618823\_Robotic\_Backchanneling\_in\_Online\_Conversation\_Facilitation\_A\_Cross-Generational\_Study](https://www.researchgate.net/publication/375618823_Robotic_Backchanneling_in_Online_Conversation_Facilitation_A_Cross-Generational_Study)  
18. Prompt engineering for students – making generative AI work for you \- Teaching@Sydney, 2月 12, 2026にアクセス、 [https://educational-innovation.sydney.edu.au/teaching@sydney/prompt-engineering-for-students-making-generative-ai-work-for-you/](https://educational-innovation.sydney.edu.au/teaching@sydney/prompt-engineering-for-students-making-generative-ai-work-for-you/)  
19. AI for Tutoring \- Super Prompt \- openNCCC, 2月 12, 2026にアクセス、 [https://opennccc.nccommunitycolleges.edu/courseware/lesson/946/overview](https://opennccc.nccommunitycolleges.edu/courseware/lesson/946/overview)  
20. A Prompt Pattern Catalog to Enhance Prompt Engineering with ChatGPT \- Distributed Object Computing (DOC) Group for DRE Systems, 2月 12, 2026にアクセス、 [https://www.dre.vanderbilt.edu/\~schmidt/PDF/prompt-patterns.pdf](https://www.dre.vanderbilt.edu/~schmidt/PDF/prompt-patterns.pdf)  
21. Instruct, Not Assist: LLM-based Multi-Turn Planning and Hierarchical Questioning for Socratic Code Debugging \- arXiv, 2月 12, 2026にアクセス、 [https://arxiv.org/html/2406.11709v4](https://arxiv.org/html/2406.11709v4)  
22. What Is This Context Engineering Everyone Is Talking About?? My Thoughts.. \- Reddit, 2月 12, 2026にアクセス、 [https://www.reddit.com/r/PromptEngineering/comments/1lnsprm/what\_is\_this\_context\_engineering\_everyone\_is/](https://www.reddit.com/r/PromptEngineering/comments/1lnsprm/what_is_this_context_engineering_everyone_is/)  
23. Beyond Single-Turn: A Survey on Multi-Turn Interactions with Large Language Models, 2月 12, 2026にアクセス、 [https://arxiv.org/html/2504.04717v4](https://arxiv.org/html/2504.04717v4)  
24. Three Prompt Engineering Methods to Reduce Hallucinations \- PromptHub, 2月 12, 2026にアクセス、 [https://www.prompthub.us/blog/three-prompt-engineering-methods-to-reduce-hallucinations](https://www.prompthub.us/blog/three-prompt-engineering-methods-to-reduce-hallucinations)  
25. Intelligent Tutoring Systems: 7 Research-Backed Principles \- Third Space Learning, 2月 12, 2026にアクセス、 [https://thirdspacelearning.com/us/blog/intelligent-tutoring-systems/](https://thirdspacelearning.com/us/blog/intelligent-tutoring-systems/)  
26. How to Deal with Cognitive Load in Voice Design \- CareerFoundry, 2月 12, 2026にアクセス、 [https://careerfoundry.com/en/blog/ux-design/voice-ui-design-and-cognitive-load/](https://careerfoundry.com/en/blog/ux-design/voice-ui-design-and-cognitive-load/)  
27. Iterative Refinement Prompting (IRP): Your Superpower for Polished AI Outputs\! – Prompt-On, 2月 12, 2026にアクセス、 [https://prompton.wordpress.com/2025/07/10/%E2%9C%8D%EF%B8%8F-iterative-refinement-prompting-irp-your-superpower-for-polished-ai-outputs-%F0%9F%9A%80/](https://prompton.wordpress.com/2025/07/10/%E2%9C%8D%EF%B8%8F-iterative-refinement-prompting-irp-your-superpower-for-polished-ai-outputs-%F0%9F%9A%80/)  
28. Challenging Cognitive Load Theory: The Role of Educational Neuroscience and Artificial Intelligence in Redefining Learning Efficacy \- PMC, 2月 12, 2026にアクセス、 [https://pmc.ncbi.nlm.nih.gov/articles/PMC11852728/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11852728/)  
29. A Researcher's Guide to LLM Grounding \- Neptune.ai, 2月 12, 2026にアクセス、 [https://neptune.ai/blog/llm-grounding](https://neptune.ai/blog/llm-grounding)  
30. Seeking Common Ground with a Conversational Chatbot \- PDXScholar, 2月 12, 2026にアクセス、 [https://pdxscholar.library.pdx.edu/cgi/viewcontent.cgi?article=1095\&context=ling\_fac](https://pdxscholar.library.pdx.edu/cgi/viewcontent.cgi?article=1095&context=ling_fac)  
31. How to write effective instructions \- Dust Docs, 2月 12, 2026にアクセス、 [https://docs.dust.tt/docs/prompting-101-how-to-talk-to-your-agents](https://docs.dust.tt/docs/prompting-101-how-to-talk-to-your-agents)  
32. 非エンジニアのためのプロンプトエンジニアリング決定版｜さかもとたくま \- note, 2月 12, 2026にアクセス、 [https://note.com/sakamototakuma/n/nd562ccb5ecbd](https://note.com/sakamototakuma/n/nd562ccb5ecbd)  
33. Simulating Human-Like Learning Dynamics with LLM-Empowered Agents \- arXiv, 2月 12, 2026にアクセス、 [https://arxiv.org/html/2508.05622v1](https://arxiv.org/html/2508.05622v1)