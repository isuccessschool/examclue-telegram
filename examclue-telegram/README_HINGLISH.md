# Exam Clue Telegram Auto-Post: Step by Step (Hinglish)

Is repo ka kaam: aapki `schedule.json` me jo post jis time ke liye likhi hai, GitHub Actions use apne aap @examcluetelegram me bhej deta hai. Har 15 minute me check hota hai.

## Ek baar ka setup

### Step 1: Bot banao
1. Telegram me **@BotFather** kholo, `/newbot` bhejo.
2. Naam aur username do. BotFather ek **token** dega. Ise kisi ko mat dikhao, mujhe bhi nahi.

### Step 2: Pehle TEST channel banao
1. Ek **private** test channel banao (jaise "Exam Clue Test").
2. Bot ko us channel me **Admin** banao (sirf "Post messages" permission kaafi hai).
3. Test channel ka id chahiye. Sabse aasaan: channel me ek message bhejo, phir apne bot ke `getUpdates` se id dekho. Mushkil lage to mujhse puchho, main step bata dunga.

### Step 3: GitHub par naya repo
1. github.com par **New repository** -> naam `examclue-telegram` -> **Public** -> Create.
2. Is folder ki saari files upload karo (**Add file -> Upload files**). `.github/workflows/telegram.yml` bhi upload hona chahiye. Agar folder upload me dikkat aaye to batao.

### Step 4: Secrets daalo
Repo -> **Settings -> Secrets and variables -> Actions -> New repository secret**
- `TELEGRAM_BOT_TOKEN` = BotFather wala token
- `TELEGRAM_CHAT_ID` = **pehle test channel ka id**

### Step 5: Test chalao
Repo -> **Actions** tab -> "Telegram Auto Post" -> **Run workflow**.
`schedule.json` me jo post ka time nikal chuka ho wo test channel me aa jayegi.

### Step 6: Asli channel par lagao
Sab sahi dikhe to `TELEGRAM_CHAT_ID` ko `@examcluetelegram` kar do (bot ko wahan bhi Admin banana hoga).

## Roz ka kaam
1. Mujhse Word file se content banwao -> mujhse milegi `schedule.json` aur `images/`, `pdfs/` files.
2. Unhe repo me upload karo (Add file -> Upload files; `schedule.json` replace ho jayegi).
3. Bas. Baaki GitHub sambhal lega.

**Public repo hai:** jo upload karoge wo koi bhi dekh sakta hai. Isliye **sirf agle 7 din ka content** upload karo, aur paid batch ka content kabhi nahi.

## Post ke prakar (schedule.json me `type`)
| type | kaam |
|---|---|
| `text` | sirf text |
| `photo` | ek image + caption |
| `album` | 2-10 images (slides) + caption |
| `document` | PDF + caption |
| `quiz_set` | 5-10 quiz polls + baad me ek message me poore explanations |
| `promo` | `promos.json` se image + caption + button |

## Telegram ki limits (script khud jaanchti hai)
- Quiz sawal 300, har option 100, poll ka explanation 200 akshar
- Caption 1024, text 4096 akshar

## Dhyan rakho
- GitHub ka cron kabhi 5-20 minute der se chalta hai.
- Public repo me 60 din koi activity na ho to scheduled runs band ho jaate hain. Hafte wala upload isse bacha lega.
- Kisi post me galti ho to `schedule.json` me uska `status` "error" ho jata hai aur wajah `error` me likhi milti hai. Baaki posts nahi rukti.
- `promos.json` me jahan `TODO` likha hai, wo link mujhse bharwa lo. Jab tak TODO hai, wo promo nahi jayegi.
- Promo images `images/` folder me, `promos.json` me likhe naam se rakhni hain.
