# HTML 生成用の記述

HTML の

> <code>&lt; タグ 属性=値 ...&gt;　内容 ... &lt;/タグ&gt;</code>

を置き換えた表記

> <code>(タグ [属性=値] 内容 ...)</code>

から HTML 形式へ変換します。

# サンプル

入力ファイル

```lisp:
(!DOCTYPE html)
(html[lang=ja]
 (head
  (meta [charset=utf-8])
  (title "sample data")

  (@comment "このコメントは取り込まれて ＜！-- や --＞ なども反映するので注意")
  (#comment "このコメントは反映されない")

  (#comment """[ があると ]""" までを一括りとして反映する. "{path}" と表記してファイルも反映可能)
  (style """[
     body {
       background-color: snow;
     }
   ]"""))

 (body
  (@comment "--> <p>@comment による悪戯</p> <!--")
  (p クォートしなくても大丈夫だけど(br)空白や記号により意図しない結果になる場合あり)

  (#comment "ツールと同じプロセスで python が実行される")
  (@python "def test(): return 'OK'")

  (#comment "@ruby で <ruby> の生成")
  (p (ruby "漢字" (rp "(")(rt "かんじ")(rp ")")) "や"
     (ruby "漢" (rp "(")(rt "かん")(rp ")") "字" (rp "(")(rt "じ")(rp ")")) "は" (br)
     (@ruby "漢字:かんじ") "や" (@ruby "漢字:かん,じ") "表記になり、" (br)
     "コロンがないと、最後の" (@ruby "漢字") "が使用される")

  (#comment "以前実行した @python 内容を参照可能")
  (#comment "HTML 変数は実行前に None で初期化されていて、設定すると反映する")
  (p (@python "HTML = f'Python Test - exec(): {test()}'"))

  (#comment "$python では子プロセスとして実行するので @python の内容は使えない")
  ($python """[
     # このプログラムは stdin として送り込まれ、stdout が取り込まれる.
     indent = '  ' * 2
     print(indent + '<p>Python Test - run(): OK</p>')
   ]""")

  (#comment
    '(@while [判定変数 初期化] [更新1] [更新2]... 内容)'
    "初期化と更新は python を呼び出します")
  (table [border=1] [style="text-align: center"]
   (@while [fLine "fLine = True; nLine = 1"] ["nLine +=1; fLine = (nLine <= 3)"]
    (tr (@while [fCol "fCol = True; nCol = 1"] ["nCol += 1; fCol = (nCol <= 3)"]
     (td (@python "HTML = f'{nLine} * {nCol} = {nLine * nCol}'"))))))

  (#comment
    '(@unless [判定変数 初期化] [更新1] [更新2]... 内容)'
    '(@when [判定変数 初期化] [更新1] [更新2]... 内容)'
    "初期化と更新は python を呼び出します")
  (@when [flag "flag = True"] ["flag = False"] (p "when が実行された"))
  (@unless [flag] (p "unless が実行された"))

  (script """[
     // JavaScript: (予定)
     // End:
   ]""")))
```

出力ファイル

```HTML:
<!DOCTYPE html>
<html lang="ja">
  <head>
    <meta charset="utf-8">
    <title>sample data</title>
    <!-- このコメントは取り込まれて ＜！-- や --＞ なども反映するので注意 -->
    <style>
      body {
        background-color: snow;
      }
    </style>
  </head>
  <body>
    <!-- --> <p>@comment による悪戯</p> <!-- -->
    <p>クォートしなくても大丈夫だけど<br>空白や記号により意図しない結果になる場合あり</p>
    <p><ruby>漢字<rp>(</rp><rt>かんじ</rt><rp>)</rp></ruby>や<ruby>漢<rp>(</rp><rt>かん</rt><rp>)</rp>字<rp>(</rp><rt>じ</rt><rp>)</rp></ruby>は<br><ruby>漢<rp>(</rp><rt>かんじ</rt><rp>)</rp></ruby>や<ruby>漢<rp>(</rp><rt>かん</rt><rp>)</rp>字<rp>(</rp><rt>じ</rt><rp>)</rp></ruby>表記になり、<br>コロンがないと、最後の<ruby>漢<rp>(</rp><rt>かん</rt><rp>)</rp>字<rp>(</rp><rt>じ</rt><rp>)</rp></ruby>が使用される</p>
    <p>Python Test - exec(): OK</p>
    <p>Python Test - run(): OK</p>
    <table border="1" style="text-align: center">
      <tr><td>1 * 1 = 1</td><td>1 * 2 = 2</td><td>1 * 3 = 3</td></tr>
      <tr><td>2 * 1 = 2</td><td>2 * 2 = 4</td><td>2 * 3 = 6</td></tr>
      <tr><td>3 * 1 = 3</td><td>3 * 2 = 6</td><td>3 * 3 = 9</td></tr>
    </table>
    <p>when が実行された</p>
    <p>unless が実行された</p>
    <script>
      // JavaScript: (予定)
      // End:
    </script>
  </body>
</html>
```
