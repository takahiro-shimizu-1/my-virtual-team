/**
 * SocialData APIで指定ユーザーのトップポストを収集し、MDファイルで出力
 *
 * Usage:
 *   node collect-top-posts.js <username> [min_faves] [api_key]
 *   node collect-top-posts.js --from-cache <username>
 *
 * Examples:
 *   node collect-top-posts.js your_username           # API収集→キャッシュ保存→上位100件出力
 *   node collect-top-posts.js your_username 100       # いいね100以上のみ収集
 *   node collect-top-posts.js your_username 0 sk-xxx  # APIキーを直接指定
 *   node collect-top-posts.js --from-cache your_username  # キャッシュから再選定（API不要）
 *
 * APIキーは以下の優先順で読み込む:
 *   1. 第3引数で直接指定
 *   2. 環境変数 SOCIALDATA_API_KEY
 *   3. ~/.config/virtual-team/.env の SOCIALDATA_API_KEY
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// === 設定 ===
const USERNAME = process.argv[2];
const MIN_FAVES = parseInt(process.argv[3]) || 0;
const TOP_N = 100;

if (!USERNAME) {
  console.error('Usage: node collect-top-posts.js <username> [min_faves] [api_key]');
  process.exit(1);
}

// APIキー解決
function resolveApiKey() {
  if (process.argv[4]) return process.argv[4];
  if (process.env.SOCIALDATA_API_KEY) return process.env.SOCIALDATA_API_KEY;
  const envPaths = [
    path.join(process.env.HOME, '.config/virtual-team/.env'),
  ];
  for (const envPath of envPaths) {
    try {
      const lines = fs.readFileSync(envPath, 'utf8').split('\n');
      for (const line of lines) {
        const idx = line.indexOf('=');
        if (idx > 0 && line.slice(0, idx).trim() === 'SOCIALDATA_API_KEY') {
          return line.slice(idx + 1).trim();
        }
      }
    } catch {}
  }
  console.error('Error: SOCIALDATA_API_KEY not found');
  process.exit(1);
}

const API_KEY = resolveApiKey();

// === API呼び出し ===
function apiGet(apiPath) {
  return new Promise((resolve, reject) => {
    https.get({
      hostname: 'api.socialdata.tools',
      path: apiPath,
      headers: { 'Authorization': `Bearer ${API_KEY}` },
    }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse error: ${data.slice(0, 200)}`)); }
      });
    }).on('error', reject);
  });
}

function searchTweets(query) {
  const q = encodeURIComponent(query);
  return apiGet(`/twitter/search?query=${q}&type=Top`);
}

function getTweetDetail(tweetId) {
  return apiGet(`/twitter/statuses/show?id=${tweetId}`);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// === 期間リスト生成（半年刻み、3年分） ===
function generatePeriods() {
  const periods = [];
  const now = new Date();
  const threeYearsAgo = new Date(now);
  threeYearsAgo.setFullYear(threeYearsAgo.getFullYear() - 3);

  let start = new Date(threeYearsAgo);
  while (start < now) {
    const end = new Date(start);
    end.setMonth(end.getMonth() + 1);
    if (end > now) end.setTime(now.getTime() + 86400000);

    const since = start.toISOString().split('T')[0];
    const until = end.toISOString().split('T')[0];
    periods.push({ since, until });

    start = new Date(end);
  }
  return periods;
}

// === スレッド（セルフリプライ）の取得 ===
async function fetchThread(tweet) {
  const replies = [];
  const conversationId = tweet.conversation_id_str || tweet.id_str;

  // 自分自身へのリプライチェーン（セルフリプライ）を辿る
  let replyToId = tweet.in_reply_to_status_id_str;
  const visited = new Set([tweet.id_str]);

  // 親を辿る（このツイートがスレッドの途中の場合）
  while (replyToId && !visited.has(replyToId)) {
    visited.add(replyToId);
    try {
      const parent = await getTweetDetail(replyToId);
      if (parent && parent.user && parent.user.screen_name === USERNAME) {
        replies.unshift({
          text: parent.full_text || '',
          id: parent.id_str,
        });
        replyToId = parent.in_reply_to_status_id_str;
      } else {
        break;
      }
    } catch { break; }
    await sleep(300);
  }

  // 子を辿る（このツイートの後のセルフリプライ）
  try {
    const q = `from:${USERNAME} conversation_id:${conversationId}`;
    const result = await searchTweets(q);
    const childTweets = (result.tweets || [])
      .filter(t => t.id_str !== tweet.id_str && !visited.has(t.id_str))
      .sort((a, b) => new Date(a.tweet_created_at) - new Date(b.tweet_created_at));

    for (const child of childTweets) {
      replies.push({
        text: child.full_text || '',
        id: child.id_str,
      });
    }
  } catch {}

  return replies;
}

// === カテゴリ推定 ===
function categorize(text) {
  const lower = text.toLowerCase();
  if (/ai|claude|gpt|chatgpt|gemini|llm|機械学習|deep learning/.test(lower)) return 'AI・テクノロジー';
  if (/プログラミング|コード|エンジニア|開発|web制作|react|python/.test(lower)) return 'プログラミング・開発';
  if (/デイトラ|スクール|受講|コース|教育|学習/.test(lower)) return '教育・スクール';
  if (/youtube|動画|撮影|サムネ/.test(lower)) return 'YouTube・動画';
  if (/x運用|ツイート|ポスト|sns|フォロワー/.test(lower)) return 'SNS・マーケティング';
  if (/経営|事業|売上|収益|起業|社長/.test(lower)) return '経営・ビジネス';
  if (/副業|フリーランス|転職|キャリア|稼/.test(lower)) return 'キャリア・副業';
  return 'その他';
}

// === キャッシュモード判定 ===
const FROM_CACHE = process.argv[2] === '--from-cache';
const CACHE_USERNAME = FROM_CACHE ? process.argv[3] : null;

// === メイン処理 ===
async function main() {
  // キャッシュモード: APIを叩かず保存済みデータから再選定
  if (FROM_CACHE) {
    if (!CACHE_USERNAME) {
      console.error('Usage: node collect-top-posts.js --from-cache <username>');
      process.exit(1);
    }
    const cachePath = path.join(process.cwd(), 'data', `${CACHE_USERNAME}-all-posts.json`);
    if (!fs.existsSync(cachePath)) {
      console.error(`Cache not found: ${cachePath}\nRun without --from-cache first to collect data.`);
      process.exit(1);
    }
    const cached = JSON.parse(fs.readFileSync(cachePath, 'utf8'));
    process.stderr.write(`Loading from cache: ${cached.length} posts\n`);

    // キャッシュからルートポストMapを復元して、後続の選定・スレッド取得・MD生成に流す
    const rootTweets = new Map();
    for (const t of cached) rootTweets.set(t.id_str, t);

    return await selectAndOutput(rootTweets, CACHE_USERNAME);
  }

  // キャッシュが1日以内に作成されていたら再収集せずキャッシュから再選定
  const existingCachePath = path.join(process.cwd(), 'data', `${USERNAME}-all-posts.json`);
  if (fs.existsSync(existingCachePath)) {
    const cacheAge = Date.now() - fs.statSync(existingCachePath).mtimeMs;
    const oneDayMs = 24 * 60 * 60 * 1000;
    if (cacheAge < oneDayMs) {
      const hoursAgo = Math.round(cacheAge / (60 * 60 * 1000));
      process.stderr.write(`Cache is fresh (${hoursAgo}h ago). Reusing cached data.\n`);
      process.stderr.write(`To force re-collection, delete: ${existingCachePath}\n\n`);
      const cached = JSON.parse(fs.readFileSync(existingCachePath, 'utf8'));
      const rootTweets = new Map();
      for (const t of cached) rootTweets.set(t.id_str, t);
      return await selectAndOutput(rootTweets, USERNAME);
    }
  }

  const periods = generatePeriods();
  const allTweets = new Map(); // id_str → tweet

  process.stderr.write(`Collecting posts from @${USERNAME}...\n`);
  process.stderr.write(`Periods: ${periods.length}, Min faves: ${MIN_FAVES || 'none (collect all)'}\n\n`);

  // 1. 期間ごとに収集
  for (const { since, until } of periods) {
    const minFavesQuery = MIN_FAVES > 0 ? ` min_faves:${MIN_FAVES}` : '';
    const query = `from:${USERNAME}${minFavesQuery} -is:reply since:${since} until:${until}`;

    try {
      const result = await searchTweets(query);
      const tweets = result.tweets || [];

      for (const t of tweets) {
        if (!allTweets.has(t.id_str)) {
          allTweets.set(t.id_str, t);
        }
      }
      process.stderr.write(`[${since} ~ ${until}] ${tweets.length} tweets → total: ${allTweets.size}\n`);
    } catch (e) {
      process.stderr.write(`[${since} ~ ${until}] Error: ${e.message}\n`);
    }
    await sleep(1000);
  }

  process.stderr.write(`\nTotal raw tweets: ${allTweets.size}\n`);

  // 2. ルートポストだけを抽出
  //    - スレッドの先頭（conversation_id === 自分のid）→ 残す
  //    - 単独ポスト（リプライでない）→ 残す
  //    - セルフリプライ（スレッドの2件目以降）→ 除外（後でスレッドとして取得）
  //    - 他人へのリプライ → 完全除外
  const rootTweets = new Map();
  let removedSelfReplies = 0;
  let removedOtherReplies = 0;
  for (const [id, t] of allTweets) {
    const convId = t.conversation_id_str || t.id_str;
    const hasReplyTo = !!t.in_reply_to_status_id_str;
    const isReplyToSelf = hasReplyTo && t.in_reply_to_user_id_str === (t.user || {}).id_str;

    if (!hasReplyTo) {
      // リプライでない → 単独ポストまたはスレッドの先頭
      rootTweets.set(id, t);
    } else if (isReplyToSelf && convId === id) {
      // セルフリプライだがconversation_idが自分 → スレッドの先頭扱い
      rootTweets.set(id, t);
    } else if (isReplyToSelf) {
      // セルフリプライ（スレッドの途中）→ 除外
      removedSelfReplies++;
    } else {
      // 他人へのリプライ → 完全除外
      removedOtherReplies++;
    }
  }

  process.stderr.write(`Filtered: ${rootTweets.size} root posts, removed ${removedSelfReplies} self-replies, ${removedOtherReplies} replies to others\n`);

  // 2.5. ルートポスト全件をキャッシュに保存（再実行時はAPIを叩かずここから読める）
  const cacheDir = path.join(process.cwd(), 'data');
  if (!fs.existsSync(cacheDir)) fs.mkdirSync(cacheDir, { recursive: true });
  const cachePath = path.join(cacheDir, `${USERNAME}-all-posts.json`);
  const cacheData = [...rootTweets.values()].map(t => ({
    id_str: t.id_str,
    full_text: t.full_text || '',
    favorite_count: t.favorite_count || 0,
    retweet_count: t.retweet_count || 0,
    reply_count: t.reply_count || 0,
    bookmark_count: t.bookmark_count || 0,
    views_count: t.views_count || 0,
    tweet_created_at: t.tweet_created_at || '',
    conversation_id_str: t.conversation_id_str || '',
    in_reply_to_status_id_str: t.in_reply_to_status_id_str || '',
    in_reply_to_user_id_str: t.in_reply_to_user_id_str || '',
    user: { id_str: (t.user || {}).id_str, screen_name: (t.user || {}).screen_name },
  }));
  fs.writeFileSync(cachePath, JSON.stringify(cacheData, null, 2));
  process.stderr.write(`Cache saved: ${cachePath} (${cacheData.length} posts)\n`);

  await selectAndOutput(rootTweets, USERNAME);
}

// === 選定・スレッド取得・MD生成 ===
async function selectAndOutput(rootTweets, username) {
  // 3. ブックマーク数順で上位N件を選定 → 新しい順に並べ替え
  let byBookmarks = [...rootTweets.values()].sort(
    (a, b) => (b.bookmark_count || 0) - (a.bookmark_count || 0)
  );
  let sorted = byBookmarks.slice(0, TOP_N).sort(
    (a, b) => new Date(b.tweet_created_at || 0) - new Date(a.tweet_created_at || 0)
  );
  const top = sorted;

  process.stderr.write(`Top ${top.length} selected\n`);

  // 3. スレッド内容の取得
  process.stderr.write(`\nFetching thread content...\n`);
  const postsWithThreads = [];

  for (let i = 0; i < top.length; i++) {
    const t = top[i];

    // スレッド検出: conversation_idで自分のセルフリプライを検索
    let thread = [];
    const convId = t.conversation_id_str || t.id_str;
    try {
      const q = `from:${username} conversation_id:${convId}`;
      const convResult = await searchTweets(q);
      const myUserId = (t.user || {}).id_str;
      const childTweets = (convResult.tweets || [])
        .filter(c => c.id_str !== t.id_str) // 先頭ポスト自身を除く
        .filter(c => c.user && c.user.screen_name === username) // 自分の投稿のみ
        .filter(c => c.in_reply_to_user_id_str === myUserId) // セルフリプライのみ（他人への返信を除外）
        .sort((a, b) => new Date(a.tweet_created_at) - new Date(b.tweet_created_at));

      if (childTweets.length > 0) {
        process.stderr.write(`  [${i + 1}/${top.length}] Thread found: ${childTweets.length} replies for ${t.id_str}\n`);
        thread = childTweets.map(c => ({
          text: c.full_text || '',
          id: c.id_str,
        }));
      }
    } catch {}
    await sleep(300);

    postsWithThreads.push({
      rank: i + 1,
      text: t.full_text || '',
      thread,
      likes: t.favorite_count || 0,
      retweets: t.retweet_count || 0,
      replies: t.reply_count || 0,
      bookmarks: t.bookmark_count || 0,
      views: t.views_count || 0,
      date: (t.tweet_created_at || '').split('T')[0],
      url: `https://x.com/${username}/status/${t.id_str}`,
      category: categorize(t.full_text || ''),
    });
  }

  // 4. MD生成
  const lines = [];

  // ヘッダー
  lines.push(`# @${username} トップポスト集（上位${postsWithThreads.length}件）`);
  lines.push('');
  lines.push(`**生成日**: ${new Date().toISOString().split('T')[0]}`);
  lines.push(`**収集条件**: ${MIN_FAVES > 0 ? `いいね${MIN_FAVES}以上` : '全件収集'} → ブックマーク数順で上位${TOP_N}件選定 → 新しい順にソート`);
  lines.push(`**収集期間**: 過去3年`);
  lines.push('');
  lines.push('---');
  lines.push('');

  // 年別集計
  const yearStats = {};
  for (const p of postsWithThreads) {
    const year = p.date.slice(0, 4);
    if (!yearStats[year]) yearStats[year] = { count: 0, totalLikes: 0 };
    yearStats[year].count++;
    yearStats[year].totalLikes += p.likes;
  }

  lines.push('## 年別集計');
  lines.push('');
  lines.push('| 年 | 件数 | いいね合計 |');
  lines.push('|---|---|---|');
  for (const [year, s] of Object.entries(yearStats).sort()) {
    lines.push(`| ${year} | ${s.count} | ${s.totalLikes.toLocaleString()} |`);
  }
  lines.push('');

  // カテゴリ別集計
  const catStats = {};
  for (const p of postsWithThreads) {
    if (!catStats[p.category]) catStats[p.category] = { count: 0, totalLikes: 0, maxLikes: 0 };
    catStats[p.category].count++;
    catStats[p.category].totalLikes += p.likes;
    catStats[p.category].maxLikes = Math.max(catStats[p.category].maxLikes, p.likes);
  }

  lines.push('## カテゴリ別集計');
  lines.push('');
  lines.push('| カテゴリ | 件数 | いいね合計 | 平均いいね | 最高いいね |');
  lines.push('|---|---|---|---|---|');
  for (const [cat, s] of Object.entries(catStats).sort((a, b) => b[1].totalLikes - a[1].totalLikes)) {
    const avg = Math.round(s.totalLikes / s.count);
    lines.push(`| ${cat} | ${s.count} | ${s.totalLikes.toLocaleString()} | ${avg.toLocaleString()} | ${s.maxLikes.toLocaleString()} |`);
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 各ポスト
  lines.push('## ポスト一覧');
  lines.push('');

  for (const p of postsWithThreads) {
    lines.push(`### #${p.rank}（${p.category}）`);
    lines.push('');
    lines.push(`- **日付**: ${p.date}`);
    lines.push(`- **URL**: ${p.url}`);
    lines.push(`- **いいね**: ${p.likes.toLocaleString()} / **RT**: ${p.retweets.toLocaleString()} / **リプ**: ${p.replies.toLocaleString()} / **BM**: ${p.bookmarks.toLocaleString()} / **表示**: ${p.views.toLocaleString()}`);
    lines.push('');
    lines.push('**本文:**');
    lines.push('');
    lines.push(`> ${p.text.replace(/\n/g, '\n> ')}`);
    lines.push('');

    if (p.thread.length > 0) {
      lines.push(`**スレッド（${p.thread.length}件）:**`);
      lines.push('');
      for (let j = 0; j < p.thread.length; j++) {
        lines.push(`> **[${j + 1}]** ${p.thread[j].text.replace(/\n/g, '\n> ')}`);
        lines.push('');
      }
    }

    lines.push('---');
    lines.push('');
  }

  // 出力
  const outputPath = path.join(process.cwd(), `guidelines/top-posts-reference.md`);
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

  fs.writeFileSync(outputPath, lines.join('\n'));
  process.stderr.write(`\nDone! Saved to: ${outputPath}\n`);
  process.stderr.write(`Total posts: ${postsWithThreads.length}\n`);
  process.stderr.write(`Threads fetched: ${postsWithThreads.filter(p => p.thread.length > 0).length}\n`);

  // コスト概算
  const estimatedCalls = rootTweets.size + postsWithThreads.filter(p => p.thread.length > 0).length * 2;
  process.stderr.write(`Estimated API cost: $${(estimatedCalls * 0.0002).toFixed(4)} (${estimatedCalls} calls × $0.0002)\n`);
}

main().catch(e => {
  console.error('Fatal:', e.message);
  process.exit(1);
});
