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

(#comment
 "($pylocal [KEY=VALUE]) は、"
 "(@python ...) で使用可能な変数名(KEY)を文字列(VALUE)で設定します。"
 "($pylocal [KEY]) で文字列(VALUE)を取得します。")

($pylocal
 [TITLE="サンプル"]
 [TEST="テスト"]
 )

(html[lang=ja]
 (head
  (meta [charset=utf-8])
  (title ($pylocal [TITLE]))

  (@comment "このコメントは取り込まれて ＜！-- や --＞ なども反映するので注意")
  (#comment "このコメントは反映されない")

  (#comment """[ があると ]""" までを一括りとして反映する. "{path}" と表記してファイルも反映可能)
  (style """[
     body {
       background-color: snow;
     }
   ]"""))

 (#comment "#ruby で辞書を事前登録")
 (#ruby
  (@ruby "辞書:じ,しょ")
  (@ruby "自動的:じ,どう,てき")
  (@ruby "使用:し,よう")
  (@ruby "文字列:も,じ,れつ")
  (@ruby "生成:せい,せい")
  (@ruby "抽出:ちゅう,しゅつ")
  (@ruby "表記:ひょう,き"))

 (#comment
  "(#ruby [dict=file] でも辞書を事前登録可)"
  "辞書ファイルは (@ruby ... ) の中を並べた"

"""[

# コメント

辞書:じ,しょ
自動的:じ,どう,てき
使用:し,よう
文字列:も,じ,れつ
生成:せい,せい
抽出:ちゅう,しゅつ
表記:ひょう,き

]"""

   "の形式になります。")

 (body
  (h1 ($pylocal [TEST]))

  (@comment "--> <p>@comment による悪戯</p> <!--")
  (p クォートしなくても大丈夫だけど(br)空白や記号により意図しない結果になる場合あり)

  (#comment "ツールと同じプロセスで python が実行される")
  (@python "def test(): return 'OK'")

  (#comment "@ruby で <ruby> の生成")
  (p (ruby "漢字" (rp "(")(rt "かんじ")(rp ")")) "や"
     (ruby "漢" (rp "(")(rt "かん")(rp ")") "字" (rp "(")(rt "じ")(rp ")")) "は" (br)
     (@ruby "漢字:かんじ") "や" (@ruby "漢字:かん,じ") "表記になり、" (br)
     "コロンがないと、最後の" (@ruby "漢字") "が使用される")
  (p ($ruby "$rubyでは辞書にある文字列を自動的に抽出して<ruby>を生成する"))

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

  (pre """[
// <pre>...</pre>
]""")

  (script """[
     // JavaScript: <予定>
     // End:
   ]""")))
```

出力ファイル

```HTML:
<!DOCTYPE html>
<html lang="ja">
  <head>
    <meta charset="utf-8">
    <title>サンプル</title>
    <!-- このコメントは取り込まれて ＜！-- や --＞ なども反映するので注意 -->
    <style>
      body {
        background-color: snow;
      }
    </style>
  </head>
  <body>
    <h1>テスト</h1>
    <!-- --> <p>@comment による悪戯</p> <!-- -->
    <p>クォートしなくても大丈夫だけど<br>空白や記号により意図しない結果になる場合あり</p>
    <p><ruby>漢字<rp>(</rp><rt>かんじ</rt><rp>)</rp></ruby>や<ruby>漢<rp>(</rp><rt>かん</rt><rp>)</rp>字<rp>(</rp><rt>じ</rt><rp>)</rp></ruby>は<br><ruby>漢字<rp>(</rp><rt>かんじ</rt><rp>)</rp></ruby>や<ruby>漢<rp>(</rp><rt>かん</rt><rp>)</rp>字<rp>(</rp><rt>じ</rt><rp>)</rp></ruby>表記になり、<br>コロンがないと、最後の<ruby>漢<rp>(</rp><rt>かん</rt><rp>)</rp>字<rp>(</rp><rt>じ</rt><rp>)</rp></ruby>が使用される</p>
    <p>$rubyでは<ruby>辞<rp>(</rp><rt>じ</rt><rp>)</rp>書<rp>(</rp><rt>しょ</rt><rp>)</rp></ruby>にある<ruby>文<rp>(</rp><rt>も</rt><rp>)</rp>字<rp>(</rp><rt>じ</rt><rp>)</rp>列<rp>(</rp><rt>れつ</rt><rp>)</rp></ruby>を<ruby>自<rp>(</rp><rt>じ</rt><rp>)</rp>動<rp>(</rp><rt>どう</rt><rp>)</rp>的<rp>(</rp><rt>てき</rt><rp>)</rp></ruby>に<ruby>抽<rp>(</rp><rt>ちゅう</rt><rp>)</rp>出<rp>(</rp><rt>しゅつ</rt><rp>)</rp></ruby>して&lt;ruby&gt;を<ruby>生<rp>(</rp><rt>せい</rt><rp>)</rp>成<rp>(</rp><rt>せい</rt><rp>)</rp></ruby>する</p>
    <p>Python Test - exec(): OK</p>
    <p>Python Test - run(): OK</p>
    <table border="1" style="text-align: center">
      <tr><td>1 * 1 = 1</td><td>1 * 2 = 2</td><td>1 * 3 = 3</td></tr>
      <tr><td>2 * 1 = 2</td><td>2 * 2 = 4</td><td>2 * 3 = 6</td></tr>
      <tr><td>3 * 1 = 3</td><td>3 * 2 = 6</td><td>3 * 3 = 9</td></tr>
    </table>
    <p>when が実行された</p>
    <p>unless が実行された</p>
    <pre>
// &lt;pre&gt;...&lt;/pre&gt;
    </pre>
    <script>
      // JavaScript: <予定>
      // End:
    </script>
  </body>
</html>
```
