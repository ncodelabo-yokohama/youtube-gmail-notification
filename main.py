# YouTube最新動画通知システム
# YouTubeチャンネルの最新動画をチェックし、新しい動画があればGmailで通知を送信するスクリプト

# 標準ライブラリのインポート
import json      # JSONファイルの読み書きに使用
import smtplib   # SMTPプロトコルを使ってメール送信を行うライブラリ
import os        # 環境変数の取得に使用

# メール送信用のライブラリ
from email.mime.multipart import MIMEMultipart  # マルチパート形式のメールメッセージを作成
from email.mime.text import MIMEText            # テキスト形式のメール本文を作成

# 外部ライブラリのインポート
from dotenv import load_dotenv           # .envファイルから環境変数を読み込む
import googleapiclient.discovery        # Google API（YouTube Data API v3）にアクセスするためのクライアント

# 環境変数の設定
# .envファイルから環境変数を読み込む（API_KEYなどの機密情報を安全に管理）
load_dotenv()

# YouTube Data API v3のAPIキーを環境変数から取得
# Google Cloud Consoleで取得したAPIキーを.envファイルに「API_KEY=your_api_key」として保存
API_KEY = os.environ.get("API_KEY")

# 監視対象チャンネルと最新動画IDを保存するJSONファイル名
# フォーマット: {"チャンネルID": {"latestVideoId": "最新動画ID"}, ...}
json_file_name = "data.json"

# Gmail SMTP設定
# 注意: 実際の使用時は以下の値を適切なメールアドレスとアプリパスワードに変更する必要があります
from_email = "送信元のメールアドレス"      # 通知メールの送信元アドレス
from_password = "取得したアプリパスワード"   # Gmailの2段階認証で生成したアプリパスワード（通常のパスワードではない）
to_email = "送信先のメールアドレス"        # 通知メールの送信先アドレス

# Gmail SMTPサーバーへの接続設定
# smtp.gmail.com:587 はGmailの標準SMTP設定（TLS暗号化対応）
gmail_server = smtplib.SMTP("smtp.gmail.com", 587)

# YouTube Data API v3クライアントの初期化
# APIキーを使用してYouTube APIにアクセスするためのクライアントオブジェクトを作成
# このオブジェクトを通じてチャンネル情報や動画情報を取得できる
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

def fetch_latest_video(channel_id: str):
    """
    指定されたチャンネルから最新の動画ID、タイトル、URLを取得
    
    Args:
        channel_id (str): YouTubeチャンネルID
    
    Returns:
        tuple: (video_id, title, url) または (None, None, None)
    """
    try:
        # ステップ1: 指定されたチャンネルIDの基本情報を取得
        # part="contentDetails"でチャンネルのコンテンツ詳細情報を要求
        req = youtube.channels().list(part="contentDetails", id=channel_id)
        response = req.execute()
        
        # チャンネルが存在するかチェック
        if not response["items"]:
            print(f"チャンネルID {channel_id} が見つかりません")
            return None, None, None
        
        # ステップ2: チャンネルのアップロード動画プレイリストIDを取得
        # YouTubeでは各チャンネルに自動的に「アップロード動画」プレイリストが作成される
        # このプレイリストには、そのチャンネルがアップロードした全ての動画が時系列順で格納されている
        uploads_playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # ステップ3: アップロードプレイリストから最新の動画（1件）を取得
        # part="snippet"で動画の基本情報（タイトル、動画IDなど）を要求
        # maxResults=1で最新の1件のみを取得（最も効率的）
        playlist_req = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=1
        )
        playlist_response = playlist_req.execute()
        
        # プレイリストに動画が存在するかチェック
        if playlist_response["items"]:
            # 最新動画の情報を抽出
            latest_item = playlist_response["items"][0]
            video_id = latest_item["snippet"]["resourceId"]["videoId"]  # 動画の一意識別子
            title = latest_item["snippet"]["title"]                     # 動画タイトル
            url = f"https://www.youtube.com/watch?v={video_id}"          # 動画の視聴URL
            
            return video_id, title, url
        else:
            print(f"チャンネル {channel_id} に動画が見つかりません")
            return None, None, None
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return None, None, None
    

def update_json_data(channel_id: str, new_video_id: str):
    """
    JSONファイル内の指定チャンネルの最新動画IDを更新する関数
    
    Args:
        channel_id (str): 更新対象のチャンネルID
        new_video_id (str): 新しい動画ID
    """
    try:
        # 現在のJSONデータを読み込み
        with open(json_file_name, "r", encoding="utf-8") as file:
            json_data = json.load(file)
        
        # 指定チャンネルの動画IDを更新
        if channel_id in json_data:
            json_data[channel_id]["latestVideoId"] = new_video_id
            
            # 更新されたデータをJSONファイルに書き込み
            with open(json_file_name, "w", encoding="utf-8") as file:
                json.dump(json_data, file, ensure_ascii=False, indent=4)
            
            print(f"チャンネル {channel_id} の最新動画IDを {new_video_id} に更新しました")
        else:
            print(f"チャンネル {channel_id} がJSONファイルに見つかりません")
            
    except Exception as e:
        print(f"JSON更新中にエラーが発生しました: {e}")


def post_gmail(title: str, url: str):
    """
    新しい動画の通知メールをGmail経由で送信する関数
    
    Args:
        title (str): 動画のタイトル
        url (str): 動画のURL
    
    Note:
        SMTPサーバーとの接続、認証、メール送信、切断を一連の流れで実行
    """
    # メールメッセージオブジェクトの作成
    # MIMEMultipartを使用することで、テキストや添付ファイルなど複数の部分を含むメールを作成可能
    msg = MIMEMultipart()
    
    # メールヘッダーの設定
    msg["From"] = from_email     # 送信者アドレス
    msg["To"] = to_email         # 受信者アドレス
    msg["Subject"] = "新しい動画/ショートがアップロードされました"  # 件名
    
    # メール本文の作成と添付
    # MIMETextでプレーンテキスト形式の本文を作成
    # \nで改行を含む本文を作成し、動画タイトルとURLを含める
    msg.attach(MIMEText(f"新しい動画がアップロードされました。\nタイトル：{title}\nリンク：{url}", "plain"))
    
    try:
        # SMTP接続とメール送信の処理
        gmail_server.starttls()                              # TLS暗号化を開始（セキュリティ強化）
        gmail_server.login(from_email, from_password)        # Gmailサーバーにログイン認証
        content = msg.as_string()                            # メールオブジェクトを文字列形式に変換
        gmail_server.sendmail(from_email, to_email, content) # メール送信実行
        gmail_server.quit()                                  # SMTPサーバーとの接続を正常終了
        print("メールを送信")
    except Exception as error:
        # メール送信時のエラーハンドリング
        # 認証失敗、ネットワークエラー、サーバーエラーなどをキャッチ
        print(f"メールの送信に失敗：{error}")
    

# メイン処理部分
# スクリプトが直接実行された場合のみ以下の処理を実行（モジュールとしてインポートされた場合は実行されない）
if __name__ == "__main__":
    # JSONファイルから監視対象チャンネルリストを読み込み
    # ファイルが存在しない場合やフォーマットが不正な場合はエラーが発生する
    with open(json_file_name, "r", encoding="utf-8") as file:
        # JSONデータを辞書形式で読み込み
        # 期待フォーマット: {"チャンネルID1": {"latestVideoId": "最新動画ID1"}, "チャンネルID2": {"latestVideoId": "最新動画ID2"}, ...}
        jsonData = json.load(file)
        
        # 各チャンネルに対して最新動画チェック処理を実行
        for channel_id, channel_data in jsonData.items():
            # JSONから保存されている最新動画IDを取得
            stored_video_id = channel_data.get("latestVideoId", "")
            print(f"チャンネル {channel_id} の最新動画を取得中...")
            
            # 指定チャンネルの最新動画情報を取得
            # 戻り値: (動画ID, タイトル, URL) または (None, None, None)
            video_id, title, url = fetch_latest_video(channel_id)
            
            # 動画情報の取得に成功した場合
            if video_id:
                # 取得した動画IDと保存されている動画IDを比較
                if video_id != stored_video_id:
                    # 新しい動画が見つかった場合
                    print(f"新しい動画を発見: {title}")
                    print(f"前回の動画ID: {stored_video_id}")
                    print(f"新しい動画ID: {video_id}")
                    
                    # メール送信
                    post_gmail(title=title, url=url)
                    
                    # JSONファイルの動画IDを更新
                    update_json_data(channel_id, video_id)
                else:
                    # 動画IDが同じ場合（新しい動画なし）
                    print(f"チャンネル {channel_id}: 新しい動画はありません")
            else:
                # 動画情報の取得に失敗した場合（チャンネルが見つからない、APIエラーなど）
                print(f"チャンネル {channel_id} の動画取得に失敗しました")
            
            print("-" * 50)  # 視覚的な区切り線を表示
