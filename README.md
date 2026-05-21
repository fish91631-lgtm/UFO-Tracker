# PURSUE 解密檔案追蹤 (UFO Tracker)

每天自動抓取美國國防部 [www.war.gov/UFO/](https://www.war.gov/UFO/) 公開的 UAP / UFO 解密檔案,
提供「英文原文 + 繁體中文翻譯」對照、分類篩選、新增內容自動提醒。

完全免費。不需要任何 API key。

---

## 它怎麼運作?(給 PM 看的版本)

把這個專案想像成一條輸送帶:

```
war.gov/UFO/  ──①每天去抓──►  Python 爬蟲  ──②翻譯成中文──►  data.json
                                                                  │
                                                                  ▼
                                                       ③網頁讀 data.json 顯示
                                                                  │
                                                                  ▼
                                                   ④全世界都能用網址打開
```

- **①爬蟲**:`scraper/scrape.py`(Python 腳本)
- **②翻譯**:用 `deep-translator` 套件呼叫 Google 翻譯(免費),而且**只翻新內容**(老的會快取在 `scraper/cache/translations.json`)
- **③網頁**:`index.html` + `detail.html` + `app.js` + `styles.css`(全靜態,沒有後端)
- **④自動排程 & 上線**:`.github/workflows/daily-update.yml`(GitHub 幫你每天免費跑)

---

## 一步一步部署到 GitHub Pages(完全沒寫過程式也能做)

### 步驟 0 · 準備

- 一個 GitHub 帳號 → 沒有的話到 https://github.com/signup 註冊(免費,5 分鐘搞定)
- 一台能上網的電腦(不需要安裝 Python、Node,什麼都不用裝)

### 步驟 1 · 建立 GitHub repo

1. 登入 GitHub,右上角點 **「+」 → 「New repository」**
2. 填:
   - **Repository name**: `ufo-tracker`(或你喜歡的名字)
   - **Public**(必須選 Public,GitHub Pages 免費版只能用在 Public repo)
   - ✅ 勾 **Add a README file**(隨便給它一個初始檔,等下會覆蓋)
3. 按 **Create repository**

### 步驟 2 · 上傳這個專案的所有檔案

最簡單的方法:

1. 在你剛建立的 repo 頁面,點 **Add file → Upload files**
2. 把整個 `ufo-tracker` 資料夾裡**所有東西**(包含隱藏的 `.github/` 和 `.nojekyll`)拖進去
   - 如果你用的是 Windows 檔案總管看不到 `.github` 資料夾,先到「檢視 → 顯示 → 隱藏項目」打開
   - 如果還是看不到,改用第二種方法:打開檔案總管網址列輸入這個資料夾完整路徑,把資料夾裡的東西全選後拖入瀏覽器
3. 拖完後,滾到頁面下方點 **Commit changes**

> 💡 一定要把 `.github/workflows/daily-update.yml` 這個檔案傳上去,**自動排程才會啟動**。如果你的拖曳沒帶到隱藏資料夾,可以在 repo 頁面點「Add file → Create new file」,檔名直接輸入 `.github/workflows/daily-update.yml`(GitHub 會自動建好資料夾),把該檔內容貼進去。

### 步驟 3 · 啟用 GitHub Pages

1. 在 repo 頁面點上方的 **Settings**
2. 左邊選單往下找,點 **Pages**
3. 在 **Build and deployment → Source** 選 **GitHub Actions**(不要選「Deploy from a branch」)
4. 不用按 Save,選了就會自動套用

### 步驟 4 · 讓 GitHub Actions 有權限寫檔

1. 還是在 **Settings**,左邊選單點 **Actions → General**
2. 滾到最下面 **Workflow permissions**
3. 選 **Read and write permissions**
4. 按 **Save**

### 步驟 5 · 第一次手動觸發(產生 data.json + 翻譯)

1. 回到 repo 首頁,點上方的 **Actions** 頁籤
2. 左邊會看到 **Daily UFO update**,點它
3. 右邊會有一個藍色按鈕 **Run workflow**,按下去 → 再按一次 **Run workflow** 確認
4. 等大概 1〜3 分鐘,工作流會跑完(綠色勾勾)
   - 它會去抓 war.gov 的 CSV → 翻譯 → 把 `data.json` commit 回 repo → 部署到 Pages

### 步驟 6 · 找你的網址

1. 回到 **Settings → Pages**
2. 上方會出現一行綠字:**Your site is live at https://你的帳號.github.io/ufo-tracker/**
3. 點進去就是你的網站!分享這個網址給任何人都能看。

---

## 之後就完全自動了

- 每天 **UTC 02:00(台灣時間早上 10:00)** 會自動跑一次
- 如果有新內容,網站頂部會出現黃色通知條
- 沒有新內容就靜悄悄更新一下時間戳

不想等到隔天?隨時可以回到 Actions 頁籤手動按一次 **Run workflow**。

---

## 你之後會用到的常見操作

### 想改成早一點/晚一點自動跑?
打開 `.github/workflows/daily-update.yml`,找到這行:
```yaml
- cron: "0 2 * * *"   # 0 分 2 點(UTC)
```
改 cron 時間就好。GitHub 用的是 **UTC**,台灣時間 = UTC + 8 小時。

### 想暫停每天自動更新?
進 Actions 頁籤 → 左邊點 **Daily UFO update** → 右上角 **⋯ → Disable workflow**。

### 翻譯怪怪的想重翻一筆?
打開 `scraper/cache/translations.json`,搜尋那段英文,把它整個 key/value 刪掉再 commit,下次跑的時候就會重新翻。

### 想換成 Claude API 翻譯(品質更高,要付費)?
跟我說一聲,我給你改好的 `scrape.py`。

---

## 專案檔案結構

```
ufo-tracker/
├── README.md                       ← 你正在看
├── .nojekyll                       ← 告訴 GitHub Pages 不要用 Jekyll 處理
├── index.html                      ← 列表頁
├── detail.html                     ← 詳情頁
├── app.js                          ← 前端邏輯
├── styles.css                      ← 樣式
├── data.json                       ← 爬蟲產生(每天更新)
├── scraper/
│   ├── scrape.py                   ← 主爬蟲
│   ├── requirements.txt            ← Python 套件清單
│   └── cache/                      ← 自動產生
│       ├── state.json              ← 記錄看過哪些 ID
│       └── translations.json       ← 翻譯快取(只翻一次)
└── .github/
    └── workflows/
        └── daily-update.yml        ← 每日排程
```

---

## 名詞小辭典(給 IC 設計 PM 的速查)

| 術語 | 中文 | 一句話解釋 |
|------|------|----------|
| Repo (repository) | 程式碼倉庫 | 一個專案在 GitHub 上的家 |
| Commit | 提交 | 把改動「存檔」並寫一段說明訊息 |
| Push | 推送 | 把本地的 commit 上傳到 GitHub |
| GitHub Pages | 網頁代管 | GitHub 幫你把 repo 裡的網頁免費架在網路上 |
| GitHub Actions | 自動化機器人 | GitHub 提供的免費伺服器,可以按你寫的劇本(`.yml`)定時跑事情 |
| Workflow | 工作流 | 一段自動化劇本(這專案的 `daily-update.yml` 就是) |
| Cron | 定時排程 | 一種寫「每天/每週/幾點」的格式,例:`0 2 * * *` = 每天 02:00 |
| Static site | 靜態網站 | 只有 HTML/CSS/JS,沒有後端 server。便宜、快、安全 |
| Scrape | 爬蟲 / 抓取 | 程式自動去網頁讀資料 |
| CSV | 逗號分隔表 | Excel 可以開的純文字表格 |
| Cache | 快取 | 把算過的結果存起來,下次直接用,不再重算 |

---

## 它真的免費嗎?

是的。**GitHub Pages** + **GitHub Actions** 對 public repo 完全免費,每月有 2000 分鐘 Actions 額度,
這個專案一天跑一次只用大概 1〜2 分鐘,完全用不到 1%。
Google 翻譯透過 `deep-translator` 是直接打 Google Translate 的網頁版,也不收費。

---

## 法律 / 道德

- war.gov 是美國政府公開網站,內容屬公有領域(public domain)
- 本專案僅做「自動翻譯與閱讀協助」,沒有修改原始檔案
- 一天只抓一次,流量極低,符合該站 robots.txt 與合理使用原則
- 不要把抓回來的圖片/文件當作商業素材出售
