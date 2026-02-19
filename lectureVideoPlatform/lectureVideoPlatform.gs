function doGet(e) {
  // HtmlServiceクラスを用いて、GASエディタ内のファイルからHtmlTemplateオブジェクトを作成する
  // createTemplateFromFileの引数には対象のHTMLファイルのファイル名を指定する（拡張子不要）
  let indexHtml = HtmlService.createTemplateFromFile('watchingVideoPlatform');

  // evaluateメソッドによってHtmlOutputオブジェクト（レスポンスデータ）を作成する
  return indexHtml.evaluate()
          .setTitle('watchingVideoPlatform')
          .addMetaTag('viewport', 'width=device-width, initial-scale=1');  
}
        
function recordLog(participant_id, currentTime, action, duration) {
  console.log("recordLog関数に入りました");
  const sheet = SpreadsheetApp.openById('1bR6rfFwXzBi-CB6Beg0AlsK8rU2UpaapEjgTi4MYFGE');
  const timestamp = new Date();
  sheet.appendRow([
    timestamp,
    participant_id,
    currentTime,
    action,
    duration
  ]);
}