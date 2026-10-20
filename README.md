# Bhavya Cafe – Instagram Auto-Post Bot

Ye bot roz shaam 6:30 baje Bhavya Cafe ke Instagram pe apne aap ek post daalta hai, poori tarah free me:

- **AI (Gemini)** IIT Roorkee aur Roorkee walon ke liye desi meme, caption aur hashtags likhta hai.
- **Bot khud design banata hai**, Bhavya ke black-gold theme me. Isme tumhara asli logo use hota hai.
- **Khane ki photos AI se banti hain:** burger, momos, vada pav jaisi realistic photos. Har item ki 3 photos ek baar banti hain aur phir har post me reuse hoti hain. Puzzle posts (ginti, odd one, difference) me emoji hi rehte hain, kyunki puzzle unse hi achhe bante hain.
- **Har hafte formats badalte hain.** Kul 15 formats hain, aur har hafte unka naya mix aata hai.
- **Har hafte ek offer post** aata hai. ₹30 tak ka koi item free milta hai. Ek hafte "Pause karo" wali flash reel aati hai, agle hafte "Zoom karo, code dhundo" wali image.
- **SEO ka dhyan rakha hai:**
  - caption ki pehli line me "Roorkee" aur khane ka naam
  - sirf 5 hashtags (Instagram ki limit)
  - alt text
  - location line

---

## Content strategy (premium cafe brand)
Har hafte: **3 reels + 3 posts + 1 offer**.
- Lagbhag 40% product/aesthetic content: cinematic food reels, spotlight, mood posts, did-you-know.
- Lagbhag 30% samajhdar humour: mature, clever, bina cringe ke.
- Lagbhag 20% interactive posts, aur 10% offers.
- **Har hafte ek "AI concept reel"** aata hai, jisme AI har baar bilkul naya idea sochta hai. Is format ki variety ki koi limit nahi.
- **AI Art Director** har post ka look khud chunta hai:
  - colours har baar naye banate hain: dark, rich aur light, 8 accent colours ke saath
  - 8 font packs
  - 10 text animations aur 11 transitions
  - 8 background styles aur 6 product layouts
  - vibe din aur occasion ke hisaab se badalta hai: luxury, cosy, festive, energetic, fresh-day, playful, desi
- **Photos ki library:** sabse pehle `assets/photos/` (aapki asli photos) use hoti hai. Phir Pexels (`PEXELS_API_KEY` secret) aur AI. Photo na mile to logo lagta hai, emoji kabhi nahi.
- **Music:** `assets/music/` me 4 original tracks hain (lo-fi, upbeat, desi dholak, game beat). Ye copyright-free hain. Apne `.mp3` bhi daal sakte ho.

## Formats

| Format | Kya hai | Kaise algorithm ko help karta hai |
|---|---|---|
| meme_card / relatable_exam / local_roorkee | Desi meme, ek joke | Share hota hai |
| trend_twist | Trend Sheet wale trend ka Bhavya version | Trend wali reach |
| versus | Mess vs Bhavya | Share hota hai |
| comment_battle | Momos vs Vada Pav, A ya B | Comments aate hain |
| tag_friend | "Tag karo us dost ko jo…" | Tags aur naye log |
| rate_combo | Combo ko 1–10 rate karo | Comments aate hain |
| weekend_plan | Checklist meme | Share hota hai |
| spot_difference | 3 difference dhundo | Log zoom aur hold karte hain |
| hidden_item | 100 me se odd one dhundo | Log zoom aur hold karte hain |
| count_items | Kitne momos hain? | Log zoom karte hain aur comment karte hain |
| zoom_read | Chhupa hua secret message | Log zoom aur hold karte hain |
| swipe_twist | 4 slide ki kahani, last slide pe twist | Log swipe karte hain aur save karte hain |
| this_or_that | 3 slide, A ya B | Swipe aur comments |
| **offer_flash_reel** | Items tezi se flash hote hain. Jahan PAUSE karo, wo item FREE | Log replay karte hain |
| **offer_zoom_code** | Image me hidden CODE hai, counter pe dikhao aur FREE pao | Log zoom karte hain aur save karte hain |

---

## Setup (ek baar, ~40 minute)

### Step 1: Instagram ko Business account banao
Instagram app → Settings → **Account type and tools** → **Switch to professional account** → **Business** → category "Cafe".

### Step 2: Instagram token lo (free)
1. **developers.facebook.com** pe Facebook se login karo → **My Apps → Create App**.
2. Use case me **"Manage messaging & content on Instagram"** chuno → app ka naam: `Bhavya Bot`.
3. Left menu → **Instagram → API setup with Instagram login**.
4. **App roles → Roles → Add People → Instagram Tester** me apna cafe ka Instagram username daalo.
   Phir Instagram app → Settings → **Website permissions → Apps and websites → Tester invites** → Accept.
5. Wapas API setup page pe → **Add account** → cafe ke Instagram se login karo → **Generate token**.
6. Jo lamba token mile (`IG...` se shuru hota hai), use copy karke kahin safe rakh lo. Ye **IG_ACCESS_TOKEN** hai.

> App "Development mode" me hi rehne do. Apne khud ke account pe post karne ke liye App Review ki zarurat nahi hai.

### Step 3: Gemini API key lo (free)
**aistudio.google.com** → Google se login → **Get API key → Create API key** → copy karo. Ye **GEMINI_API_KEY** hai.

### Step 4: GitHub pe code daalo
1. **github.com** pe free account banao.
2. **New repository** → naam `bhavya-insta-bot` → **Public** chuno → Create.
   (Public isliye, kyunki Instagram images yahin se uthata hai. Repo me koi password ya token nahi hota. Wo sab "Secrets" me rehte hain.)
3. **uploading an existing file** pe click karo. Zip ko unzip karo, aur uske andar ki **saari files aur folders** drag karke daal do → **Commit changes**.
4. Check karo ki `.github/workflows` folder upload hua ya nahi. Mac pe ye folder chhupa hota hai, isliye kabhi-kabhi upload nahi hota. Agar nahi dikhe, to **Add file → Create new file** karo, naam me `.github/workflows/daily-post.yml` likho, aur zip me rakhi usi naam ki file ka content paste kar do. Baaki 2 workflow files ke liye bhi yahi karo.

### Step 5: Secrets daalo
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `GEMINI_API_KEY` | Step 3 wali key |
| `IG_ACCESS_TOKEN` | Step 2 wala token |
| `CF_ACCOUNT_ID`, `CF_API_TOKEN` | Cloudflare (AI food photos) |
| `PIXABAY_API_KEY` | pixabay.com/api/docs (free HD stock photos + background videos) |
| `CUSTOMER_MEMORY_KEY` | koi bhi lamba password (auto-reply ki encrypted customer memory ke liye) |

> 🔒 Koi bhi key / token **kabhi chat, WhatsApp ya kisi file me paste mat karo**. Sirf yahan Secrets me.
> Galti se kahin paste ho gaya ho to us site pe jaake key **regenerate** kar lo aur nayi wali secret me daalo.

**Reach / likes data (learning ke liye):** Meta app → Instagram → API setup → permissions me
`instagram_business_manage_insights` bhi tick karo → **Generate token** dobara → naya token `IG_ACCESS_TOKEN` me update karo.
Iske bina bot post karega, par ye nahi seekh payega ki kaunsa design zyada chala.

Phir **Settings → Actions → General → Workflow permissions → "Read and write permissions"** → Save.

### Step 6: Token auto-renew (zaroori, warna 60 din baad posting ruk jayegi)
1. GitHub → apni profile photo → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Repository access me **Only select repositories** chuno → `bhavya-insta-bot`.
3. Permissions → **Secrets: Read and write** → Generate.
4. Jo token mile, use Step 5 ki tarah ek naye secret me daalo, naam: `GH_PAT`.

Iske baad har mahine ki 1 tareekh ko Instagram token apne aap renew ho jayega.

### Step 7: Food photos banao (ek baar)
Repo → **Actions** → **Make AI food photos (one time)** → **Run workflow**. 5–10 minute me saare menu items ki AI photos `assets/photos_ai/` me aa jayengi.
Wahan khol ke photos dekh lo. Koi photo pasand na aaye ya asli dish se alag lage, to use delete kar do. Agle din bot nayi bana lega.

> Agar Gemini image free me na chale (Google kabhi-kabhi free limit badal deta hai), to **enter.pollinations.ai** se free key lo aur use `POLLINATIONS_KEY` naam ke secret me daal do. Bot wahan se photos bana lega.

### Step 8: Test karo
Repo → **Actions** tab → **Daily Instagram post** → **Run workflow**. 2–3 minute me post Instagram pe aa jana chahiye.

Uske baad roz shaam 6:30 baje ye apne aap chalega. Kuch fail hua to GitHub tumhe email karega.

---

## 🚀 POST NOW: jab chaho turant post karo
Daily post apne aap jaata rahega. Iske alawa jab bhi kuch special ho, jaise baarish, fest, match, naya item ya koi announcement, to turant ek extra post daal sakte ho:

1. Phone pe **GitHub app** kholo (ya github.com) → apna repo → **Actions** → **POST NOW (abhi turant post karo)** → **Run workflow**.
2. 3 cheezein bharo (teeno optional hain):
   - **type**: `video` (reel), `image`, ya `auto`. Video chuno aur format image wala ho, to bhi bot use music wale video me badal dega.
   - **format**: `auto` rehne do, bot khud chunega. Ya list se koi format chuno, jaise `reel_showcase`.
   - **theme**: `auto` ya koi colour theme.
   - **idea**: apni baat likho, jaise *"Aaj baarish hai, Kulhad Chai + Bun Makkhan perfect combo"* ya *"Fest week me cafe raat 1 baje tak open"*.
   - **item**: kaunsa item dikhana hai, jaise *Kulhad Pizza* ya *Potato Twister*.
3. **Run workflow** dabao. 2–4 minute me post Instagram pe aa jayega.

Idea ya item doge to AI usi pe meme aur caption likhega, aur photo bhi usi item ki lagegi.

## 📅 Content Calendar + 📋 Upload Log

Bot khud aage ke **30 din ka content calendar** banata hai, aur roz ek din aage badha deta hai. Har din ki row me ye hota hai:
- **date** aur din
- **occasion**: tyohaar, IITR exams, chhutti
- **format**: kis type ka post
- **featured_item**: kaunsa item dikhega
- **idea**: AI ka likha post idea
- **status**: planned ya posted
- **instagram_link**: post hone ke baad uska link

Calendar me ye dhyan rakha jaata hai:
- **IIT Roorkee ki official dates:** end-sem exams (13–24 Nov), Diwali break, winter vacation (5 Dec – 6 Jan). Exam wale dinon me exam memes aate hain. Vacation me jab students ghar pe hote hain, tab posts Roorkee ke locals ke liye bante hain.
- **Har hafte ka offer** apne din pe hota hai.
- **Repeat nahi hota:** ek hi format lagatar 2 din nahi aata, aur ek hi item baar-baar nahi aata.

Roz ka post **calendar ki row follow karta hai**. Kisi din ka idea, item ya format badalna ho to bas us row ko edit kar do, bot wahi banayega.

| File | Kya hai |
|---|---|
| `data/content_calendar.csv` | Aage ka plan (yahi edit karna hai) |
| `data/content_calendar.ics` | Wahi plan, calendar app ke liye |
| `data/posts_log.csv` | **Jo-jo upload hua uska record**: date, time, daily ya post-now, format, item, caption, hashtags, offer code, Instagram link |
| `data/occasions.csv` | Tyohaar aur events ki list. Isme apni dates jod sakte ho, jaise Holi, Lohri, college fest ya cafe ki anniversary |

### Phone ke Google Calendar me plan dekho
1. Kisi computer pe **calendar.google.com** kholo. Left side **Other calendars → + → From URL** pe jao.
2. Ye link daalo, `USERNAME` ki jagah apna GitHub username likho:
   `https://raw.githubusercontent.com/USERNAME/bhavya-insta-bot/main/data/content_calendar.ics`
3. **Add calendar** dabao.

Ab phone ke Google Calendar me har din dikhega ki kya post hoga (📸), aur jo post ho gaya uspe ✅ dikhega. Google ise khud refresh karta hai, kabhi-kabhi kuch ghante late.

### Google Sheet me live log + calendar
Nayi Google Sheet banao aur cell A1 me ye formula likho:
```
=IMPORTDATA("https://raw.githubusercontent.com/USERNAME/bhavya-insta-bot/main/data/posts_log.csv")
```
Isse saare uploads ki live list aa jayegi. Doosri tab me `content_calendar.csv` wala link daal do, to poora plan bhi dikh jayega.

### Plan edit karna (phone se bhi)
GitHub me repo → `data` → `content_calendar.csv` → ✏️ (pencil) dabao. Jis din ka `idea` / `featured_item` / `format` badalna hai, badlo → **Commit changes**. Bas itna hi.
- Kisi din ke liye bot khud idea likhe, aisa chahte ho to us din ki row delete kar do. Agle plan me bot naya idea bana dega.
- Har Sunday (aur jab chaho to Actions → **Plan content calendar** → Run workflow) calendar aage badh jaata hai. Pehle se plan hue din waise hi rehte hain, unhe bot nahi chhedta.

## Roz ka kaam (optional, par bahut faydemand)

### Trend Sheet: 10 second ka kaam
Jab bhi koi viral meme ya trend dikhe, use ek Google Sheet me daal do. Agla post usi trend pe banega.
1. Google Sheet banao. Column A me `date`, column B me `trend` likho.
   Example: `2026-10-20 | "2 kachori 1 samosa" wala meme`
2. **File → Share → Publish to web → CSV** → Publish → link copy karo.
3. `config.yaml` me `trend_sheet_csv_url: "yahan link"` daal do.

Sirf pichhle 14 din ke trends use hote hain.

### 📸 Asli food photos (sabse zaroori): `assets/photos/`
Asli photo hamesha AI aur stock photo se upar priority leti hai (asli → Pixabay → AI). Kisi item ki asli photo ho to `assets/photos/` me daal do.
Photo **saaf aur bright honi chahiye, kam se kam 1080px**. Plain background ho to aur achha, kyunki bot dish ko kaat ke design me lagata hai. Us item ke liye AI photo ki jagah wahi lagegi. Naam item ke naam se shuru hona chahiye:
`momos_1.jpg`, `momos_2.jpg`, `cold_coffee_1.jpg`, `vada_pav_1.jpg`, `chilli_paneer_1.jpg` …



### 🎵 Music folder: `assets/music/`
10 copyright-free tracks pehle se hain. Aur daalne ho to **pixabay.com/music** ya **YouTube Audio Library** se `.mp3` download karke yahan upload kar do.
- Naam me mood likh doge to AI Director aur sahi chunega: `lofi_chill_cafe.mp3`, `desi_dhol_party.mp3`, `cinematic_piano.mp3`, `upbeat_pop_fun.mp3`.
- Bot khud har gaane ka BPM, energy aur **sabse catchy hissa (chorus/drop)** nikaalta hai, aur reel ke vibe ke hisaab se gaana + start point chunta hai. Cuts beat pe hote hain, aur whoosh/pop/boom/shimmer sound effects sahi moment pe lagte hain.
- Bollywood / trending film gaane mat daalna. Copyright ki wajah se reel mute ya delete ho sakti hai.

### 🎨 Design references: `assets/references/images/`
Pinterest/Instagram pe koi design pasand aaye to uska **screenshot** yahan upload kar do. Agle run me:
1. AI uske colours, fonts aur layout padh ke ek **style card** banata hai (`data/reference_styles.json`).
2. Uske baad bot usi style me **apne cafe ka original post** banata hai: same colours aur text style, par content, photo aur logo apne.
3. Screenshot repo se apne aap delete ho jaata hai (repo public hai, dusre brand ki file nahi rakhni).

Abhi aapke bheje designs se **15 style cards** bane hue hain. Ek hi design lagatar 4 posts me repeat nahi hota, aur jo design zyada reach laata hai uska chance badh jaata hai.

### 🎬 Reference videos: `assets/references/videos/`
Koi reel ka editing style pasand aaye to `.mp4` (19 MB se chhoti) yahan daal do. AI uski speed, transitions aur text animation samajh ke ek **motion preset** banata hai. Video bhi analysis ke baad delete ho jaati hai.

### 🕵️ AI Auditor (quality check, publish se pehle)
**1. Photo check:** koi bhi nayi photo (Pixabay / Pexels / AI) library me tabhi aati hai jab ye sab sahi ho:
- HD ho (kam se kam 900px) aur blur na ho. Blur machine se naapa jaata hai.
- Gemini dekhta hai ki photo usi dish ki hai, saaf aur sharp hai, aur usme koi watermark, logo ya text nahi hai.
- Tasty dikhne me kam se kam 7/10 aur premium look me kam se kam 6/10 number aaye.

Kharab photo reject ho jaati hai aur bot agli photo try karta hai. **Make AI food photos** chalane pe purani kharab stock/AI photos bhi hat jaati hain. Aapki asli photos kabhi delete nahi hoti, sirf log me warning aati hai.

**2. Layout Guard (har design me, bina AI ke):** bot naapta hai ki khana kisi box, text ya badge ke peeche to nahi chhup raha, aur frame se kat to nahi raha. Aisa ho to dish ko khud chhota karke ya khiska ke sahi jagah rakhta hai. Background hatate waqt glass ke andar jo chhed ban jaate hain (jaise cold coffee me), wo bhi bhar diye jaate hain.

**3. Post check:** final post (ya reel ke 6 frames) Gemini ek creative director ki tarah dekhta hai:
- khana poora dikh raha hai
- cut-out saaf hai
- photo HD hai
- text padhne layak hai aur spelling sahi hai
- price menu se match karta hai
- design premium lagta hai

7/10 se kam aaye to bot **naye design aur nayi photo** se dobara banata hai (max 2 baar), aur sabse achha version hi post hota hai. Teeno koshish ke baad bhi 5/10 se kam aaye, ya khana chhupa ho, to **post nahi hota**. Kharab post daalne se ek din chhodna behtar hai.

Har check ka record `data/audit_log.csv` me hai: score aur problem kya thi. Settings `config.yaml` → `audit:` me hain.

### 🎨 Colour wheel + fonts
AI Art Director har post ke rang **colour wheel ke niyam** se chunta hai:
- **Complementary:** bilkul opposite rang, jaise gold + navy ya coral + teal. Sabse zyada pop karta hai.
- **Split-complementary:** opposite ke dono padosi rang. Contrast rehta hai, par thoda soft.
- **Triadic:** wheel pe 120° door teen rang. Playful aur energetic.
- **Analogous:** paas-paas ke rang. Calm, cosy, warm.
- **Monochrome:** ek hi rang ke shades. Luxury aur minimal.

Vibe ke hisaab se harmony chuni jaati hai, aur text hamesha padhne layak rehta hai (contrast ≥ 7:1, machine se check).
Fonts me 5 naye styles hain: **boutique, bold_modern, retro_diner, desi_bold** (Hindi bhi) aur **royal**. ₹ kabhi dabba ya galat nahi dikhta.

### 📈 Growth brain: jo chal raha hai, uska system (35%)
Roz bot pichhle posts ke insights padhta hai: reach, likes, comments, saves, shares, views. Phir har post ka "DNA" naapta hai: format, design, vibe, colour harmony, font, music mood, item aur din. Format ka asar alag karke naapa jaata hai, taaki item aur design ka asli asar dikhe.
- Isse **winning recipe** banti hai, jaise "poster_reel + Kulhad Pizza + complementary colours".
- **~35% din 🔥 WINNER:** usi system pe naya content banta hai. Same type hota hai, copy kabhi nahi.
- **~65% din 🧪 EXPERIMENT:** naye formats aur designs try hote hain, taaki naya winner mile aur feed boring na ho.
- Gemini best aur worst posts compare karke likhta hai: kya kaam karta hai, kya avoid karna hai, aur agle idea kya ho sakte hain.
- Calendar me nayi column **strategy** hai (🔥 winner / 🧪 experiment), aur Google Calendar me winner din pe 🔥 dikhta hai.
- Percentage `config.yaml` → `growth.exploit_share` me badal sakte ho.
- Data `data/performance.json` me hai. Iske liye `instagram_business_manage_insights` permission chahiye.

### 📱 Stories (roz 2 baar, apne aap)
`.github/workflows/stories.yml`:
- **Dopahar 12:10:** aaj ka special (photo + price) aur ek **"A ya B?"** sawaal, jiska jawab log DM me dete hain aur auto-reply unhe cafe bulata hai.
- **Raat 9:00:** aaj ke post ka teaser aur ek mood line.
- **Offer wale din:** offer reminder bhi (sirf config ka approved offer).

Instagram API se poll, link ya question **sticker nahi lagte** (Meta allow nahi karta), isliye sawaal ka jawab DM me maanga jaata hai.
`config.yaml` → `brand.hours` me timing likh doge (jaise "Open 11 AM – 11 PM") to stories me dikhegi.

### 💬 Auto-reply: comments + DMs (personal touch se cafe bulana)
`.github/workflows/replies.yml` har 30 minute chalta hai:
- **Comments:** har naye comment ka jawab, naam lekar aur unki baat pe. Har jawab me ek specific item aur aane ki ek wajah hoti hai.
  - Price ya location poochhne wale ko ek DM bhi jaata hai. Iske liye Advanced Access chahiye, neeche dekho.
- **Yaad rakhta hai:** naam, pasandida item, chhoti baatein (jaise "exam week", "dosto ke saath aata hai"). Agli baar baat wahin se shuru hoti hai.
- **Shikayat:** public me maafi aur "DM karo", bechne ki koshish nahi. Ye `data/owner_inbox.csv` me aapke liye flag ho jaati hai.
- **DM me shikayat ya booking:** bot jawab **nahi** deta. Message unread rehta hai, taaki aap khud dekho. Bot kabhi table, delivery ya stock confirm nahi karta.
- **Spam ya gaali:** koi jawab nahi.
- **Sach:** koi "bot ho?" pooche to sach batata hai.
- **Sirf asli cheezein:** menu ke asli prices aur approved offer. Koi naya discount ya promise kabhi nahi.
- **Privacy:** customer memory **encrypted** rehti hai (`data/customers.enc`). Logs me sirf ginti aati hai, kisi ka naam ya message nahi.

**Setup:**
1. GitHub Secrets me naya secret `CUSTOMER_MEMORY_KEY` banao. Value me koi bhi lamba password likho (20+ letters) aur use kahin likh ke rakh lo. Badloge to purani yaadein nahi khulengi.
2. Meta app → Instagram → API setup → permissions me **`instagram_business_manage_comments`** aur **`instagram_business_manage_messages`** tick karo → **Generate token** → naya token `IG_ACCESS_TOKEN` me daalo.
3. **Comments ke jawab** isi se shuru ho jayenge.
4. **DM ke jawab** ke liye Meta ka niyam hai ki app ko **Advanced Access** chahiye. Uske liye:
   - (a) **Business Verification:** Meta Business Suite → Settings → Business info → Verify. Cafe ka GST ya registration certificate aur bijli ka bill/address proof lagta hai.
   - (b) **App Review:** app dashboard → App Review → `instagram_business_manage_messages` → chhota screen-recording video aur use case likh ke submit.
   - Approval me aam taur pe kuch din se 2–3 hafte lagte hain. Tab tak bot sirf comments ka jawab dega, aur DM wala hissa approval milte hi apne aap chal padega.
5. Kisi offer ya perk ka zikr karwana ho to `config.yaml` → `replies.invite_perk` me likho. Khaali chhodoge to bot kuch promise nahi karega.

### 🔁 Repeat nahi hota
- Ek photo **image post me 21 din tak dobara nahi** lagti.
- Reels me ek photo **max 3 baar** use hoti hai. Record `data/photo_usage.json` me rehta hai.

### 📈 Bot khud seekhta hai
Roz post se pehle bot purane posts ki reach, likes, saves aur shares padhta hai (`data/performance.json`). Jo format, design aur vibe zyada chale, unka chance badhta hai (60%). Baaki 40% me naye experiments hote rehte hain.

### #️⃣ Hashtags + SEO
Instagram ab har post pe **max 5 hashtags** allow karta hai, isliye bot 3 fixed + 2 rotating tags lagata hai.
Reach ke liye caption me SEO line bhi jaati hai: *Cafe in Roorkee · Near IIT Roorkee · <item> in Roorkee*. Instagram search ab caption ke words bhi padhta hai.

---

## ⚠️ Offer wale din: staff ko batana zaroori hai
Offer post ka **code / free item** har baar yahan likha milega:
- Repo → `posts/<date>/post.json` → `owner_note`, ya
- Actions → us din ka run → "Aaj ka post banao" step → `OWNER NOTE:` line.

Example: `ZOOM OFFER CODE: BH44-KHEER = FREE Kheer (valid till 03 Nov)`.
Counter staff ko ye code pehle se bata do.

Puzzles (count / hidden item) ke answers bhi `owner_note` me milte hain, taaki agle din story pe answer daal sako.

---

## Kuch badalna ho to (sirf `config.yaml` edit karo)
- **Free items / price / terms**: `weekly_offer` section. Sirf ₹30 ya usse kam ke items rakho. Bot isse mehenga item kabhi nahi lagata.
- **Offer ka din**: `weekly_offer.weekday`
- **Menu**: `menu`. AI sirf inhi items ka naam leta hai.
- **Hashtags**: `hashtags`
- **Post ka time**: `.github/workflows/daily-post.yml` me `cron: "0 13 * * *"`. Ye time UTC me hai, IST = UTC + 5:30.
  Example: shaam 7:30 IST ke liye `"0 14 * * *"` likho.

## Agla hafta pehle dekhna ho
Har Sunday subah ek preview ban jaata hai. Actions → **Preview next week** → run kholo → neeche **next-week-preview** download karo.
Isme formats aur design wahi honge jo hafte bhar aayenge. Jokes asli din pe naye likhe jaate hain.

## Credits
Fonts: Google Fonts (OFL): Fraunces, Bricolage Grotesque, Unbounded, Outfit, Righteous, Shrikhand, Yeseva One, Marcellus, Josefin Sans, Sacramento, Rozha One, Baloo 2, Space Grotesk, Lobster, Playfair Display, Poppins, Anton, Dancing Script, Bebas Neue, Montserrat, Cormorant, DM Serif Display, Archivo Black, Oswald, Abril Fatface, Syne, Caveat, Pacifico, Great Vibes, Kalam, Rubik Dirt. Stock photos: Pixabay (credits in `data/photo_credits.csv`). Background removal: rembg (MIT).
