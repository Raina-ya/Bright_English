"""Bright English Lab local server — Python standard library only."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.request import Request, urlopen
import json, re, hashlib, os
from datetime import date
from xml.etree import ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from time import perf_counter

ROOT=Path(__file__).parent; DATA=ROOT/'learning_data.json'; HISTORY=ROOT/'question_history.json'; CONFIG=ROOT/'config.json'; RSS_CACHE=ROOT/'rss_cache.json'; ARTICLE_POOL=ROOT/'article_pool.json'; NEWS_REWRITE_CACHE=ROOT/'news_rewrite_cache.json'; DAILY_AI_CACHE=ROOT/'daily_ai_content.json'

def load_env_file():
    """Load simple KEY=VALUE pairs from a local .env without adding a dependency."""
    path = ROOT / '.env'
    if not path.exists(): return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env_file()
def read(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError): return default
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def default_data(): return {'version':1,'settings':{},'days':{},'mistakes':[],'learned_words':[],'stats':{'answers':0,'correct':0,'study_dates':[]},'pet':{'mood':65,'food':0,'chat':[]}}
if not DATA.exists(): write(DATA,default_data())
if not HISTORY.exists(): write(HISTORY,{'questions':[],'words':[]})
if not CONFIG.exists(): write(CONFIG,{'providers':{'groq':{'key':'','model':'llama-3.3-70b-versatile'},'openrouter':{'key':'','model':'google/gemini-2.0-flash-001'},'google':{'key':'','model':'gemini-2.0-flash'},'openai':{'key':'','model':'gpt-4o-mini'}},'order':['groq','openrouter','google','openai']})

class QuotaError(RuntimeError): pass
def call_ai(messages, json_mode=False):
    cfg=read(CONFIG,{})
    env_keys={'groq':'GROQ_API_KEY','openrouter':'OPENROUTER_API_KEY','google':'GEMINI_API_KEY','openai':'OPENAI_API_KEY'}
    for name in cfg.get('order',[]):
        p=cfg.get('providers',{}).get(name,{}); key=os.getenv(env_keys.get(name,''), p.get('key','')).strip(); model=p.get('model','').strip()
        if not key: continue
        try:
            if name=='google':
                contents=[]
                for m in messages:
                    role='model' if m['role']=='assistant' else 'user'
                    contents.append({'role':role,'parts':[{'text':m['content']}]})
                url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
                body={'contents':contents,'generationConfig':({'responseMimeType':'application/json'} if json_mode else {})}
                req=Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                out=json.loads(urlopen(req,timeout=45).read()); return out['candidates'][0]['content']['parts'][0]['text'],name
            if name=='openai': url='https://api.openai.com/v1/chat/completions'; headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
            elif name=='groq': url='https://api.groq.com/openai/v1/chat/completions'; headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
            else: url='https://openrouter.ai/api/v1/chat/completions'; headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','HTTP-Referer':'http://localhost:8765'}
            body={'model':model,'messages':messages,'temperature':.75}
            if json_mode: body['response_format']={'type':'json_object'}
            req=Request(url,data=json.dumps(body).encode(),headers=headers)
            out=json.loads(urlopen(req,timeout=45).read()); return out['choices'][0]['message']['content'],name
        except Exception:
            continue
    raise RuntimeError('No configured AI provider succeeded.')

def valid_generated(payload):
    """Reject empty/duplicate options and placeholder Chinese meanings before they reach the UI."""
    bad = {'核心學術字彙', '高頻詞', '學術字彙', 'core academic word', 'high-frequency word'}
    def one(q):
        options=q.get('options',q.get('o',[])) if isinstance(q,dict) else []
        answer=q.get('answer',q.get('ans')) if isinstance(q,dict) else None
        return bool(options) and len(options)==len(set(map(str,options))) and all(str(x).strip() for x in options) and (answer in options or isinstance(answer,int))
    for word in payload.get('words',[]) if isinstance(payload,dict) else []:
        meaning=str(word.get('zh','')).strip()
        if len(meaning)<2 or meaning.lower() in bad or meaning in {'n.','v.','adj.','noun','verb','adjective'}: return False
    questions=payload.get('questions',[]) if isinstance(payload,dict) else []
    return all(one(item) for item in questions)

def clean_html(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', value or '')).strip()

RSS_FEEDS=[
    ('BBC','https://feeds.bbci.co.uk/news/rss.xml'),
    ('CNN','http://rss.cnn.com/rss/edition.rss'),
    ('The Guardian','https://www.theguardian.com/world/rss'),
    ('NPR','https://feeds.npr.org/1001/rss.xml'),
    ('Reuters','https://feeds.reuters.com/reuters/topNews'),
    ('Al Jazeera','https://www.aljazeera.com/xml/rss/all.xml')
]
RARE_TERMS={'aberration','apodictic','circumscribe','contumacious','deleterious','inchoate','intransigent','lachrymose','obsequious','perspicacious','recondite','sanguine','sycophantic','trenchant','vicissitude'}

def word_list(text): return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text or '')
def sentence_words(text):
    return [word_list(s) for s in re.split(r'(?<=[.!?])\s+', text or '') if word_list(s)]
def difficulty_key(value):
    value=str(value or '')
    if value in {'one','two','three','four'}: return value
    return 'four' if '★★★★' in value else 'three' if '★★★' in value else 'two' if '★★' in value else 'one'
def validate_reading(result, difficulty):
    text=str(result.get('en','')); words=word_list(text); sentences=sentence_words(text); key=difficulty_key(difficulty)
    average=round(len(words)/max(1,len(sentences)),1); clauses=len(re.findall(r'\b(which|that|although|because|while|whereas|unless|despite|whereby|whose)\b',text,re.I))
    limit={'one':15,'two':20,'three':25,'four':None}[key]
    rare={w.lower() for w in words}&RARE_TERMS
    qs=result.get('questions',[])
    ok=len(words)>=600 and 5<=len(qs)<=8 and valid_generated({'questions':qs}) and (limit is None or average<=limit) and (key!='four' or clauses>=3) and not (key in {'one','two'} and rare)
    return ok,{'word_count':len(words),'average_sentence_length':average,'clauses':clauses,'estimated_level':key,'rare_terms':sorted(rare)}
def validate_listening(result, difficulty):
    text=str(result.get('text',result.get('en',''))); words=word_list(text); qs=result.get('questions',[])
    positions=[]
    for q in qs:
        options=q.get('o',q.get('options',[])); answer=q.get('ans',q.get('answer',0)); correct=options[answer] if isinstance(answer,int) and answer<len(options) else answer
        terms=[x.lower() for x in word_list(str(correct)) if len(x)>3]
        found=[text.lower().find(term) for term in terms if text.lower().find(term)>=0]
        positions.append(min(found) if found else -1)
    usable=[p for p in positions if p>=0]; buckets={min(2,int(p/max(1,len(text))*3)) for p in usable}
    rare={w.lower() for w in words}&RARE_TERMS; key=difficulty_key(difficulty)
    ok=len(words)>=120 and len(qs)>=3 and valid_generated({'questions':qs}) and len(usable)>=3 and len(buckets)>=2 and not (key in {'one','two'} and rare)
    return ok,{'word_count':len(words),'question_count':len(qs),'coverage_buckets':len(buckets),'estimated_level':key,'rare_terms':sorted(rare)}

def title_tokens(title): return set(re.findall(r'[a-z0-9]+', (title or '').lower()))
def similar_title(a,b):
    x,y=title_tokens(a),title_tokens(b)
    return bool(x and y) and len(x&y)/max(1,len(x|y))>=.62
def merge_articles(items):
    merged=[]
    for item in items:
        found=next((old for old in merged if old.get('link')==item.get('link') or similar_title(old.get('title',''),item.get('title',''))),None)
        if found:
            sources=set(found.get('sources',[found.get('source','')]))|set(item.get('sources',[item.get('source','')]))
            found['sources']=sorted(s for s in sources if s); found['source']=' / '.join(found['sources'])
        else:
            item['sources']=[item.get('source','')]; merged.append(item)
    return merged

def fetch_feed(source, url):
    started=perf_counter(); articles=[]
    try:
        req=Request(url,headers={'User-Agent':'BrightEnglishLab/1.0'})
        root=ET.fromstring(urlopen(req,timeout=12).read())
        for item in root.findall('.//item')[:10]:
            title=clean_html(item.findtext('title')); link=(item.findtext('link') or '').strip(); summary=clean_html(item.findtext('description'))
            if title and summary:
                ident=hashlib.sha256((link or title).encode()).hexdigest()[:16]
                articles.append({'id':ident,'source':source,'title':title,'link':link,'published':item.findtext('pubDate') or '', 'en':summary,'zh':'','fetched_at':date.today().isoformat()})
        return source, articles, {'status':'success','ms':round((perf_counter()-started)*1000),'count':len(articles),'last_success':date.today().isoformat()}
    except Exception as exc:
        return source, [], {'status':'failed','ms':round((perf_counter()-started)*1000),'count':0,'error':str(exc)[:120]}

def atom_text(parent, name):
    """Return Atom text while accepting the namespace used by Reddit feeds."""
    node = parent.find('{http://www.w3.org/2005/Atom}'+name)
    return clean_html(''.join(node.itertext())) if node is not None else ''

def reddit_articles():
    """Small, optional community supplement.  Never let a Reddit error block news."""
    feeds=[
        ('Reddit · r/todayilearned','https://www.reddit.com/r/todayilearned/.rss'),
        ('Reddit · r/explainlikeimfive','https://www.reddit.com/r/explainlikeimfive/.rss')
    ]
    items=[]
    for source, url in feeds:
        try:
            req=Request(url,headers={'User-Agent':'BrightEnglishLab/1.0 (personal learning reader)'} )
            root=ET.fromstring(urlopen(req,timeout=12).read())
            entries=root.findall('{http://www.w3.org/2005/Atom}entry')[:3]
            for entry in entries:
                title=atom_text(entry,'title')
                link_node=entry.find('{http://www.w3.org/2005/Atom}link')
                link=(link_node.get('href','').strip() if link_node is not None else '')
                author_node=entry.find('{http://www.w3.org/2005/Atom}author')
                author=atom_text(author_node,'name') if author_node is not None else ''
                published=atom_text(entry,'updated') or atom_text(entry,'published')
                ident=hashlib.sha256((link or title).encode()).hexdigest()[:16]
                if title and link: items.append({'id':ident,'source':source,'title':title,'link':link,'author':author,'published':published})
        except Exception:
            continue
    return items[:6]

def rss_articles(seen):
    cache=read(RSS_CACHE,{})
    if cache.get('date')==str(date.today()) and cache.get('articles'):
        return [x for x in cache['articles'] if x['id'] not in seen], cache.get('community',[])
    feeds=[
        ('BBC','https://feeds.bbci.co.uk/news/rss.xml'),
        ('CNN','http://rss.cnn.com/rss/edition.rss'),
        ('The Guardian','https://www.theguardian.com/world/rss'),
        ('NPR','https://feeds.npr.org/1001/rss.xml'),
        ('Reuters','https://feeds.reuters.com/reuters/topNews')
    ]
    articles=[]
    for source,url in feeds:
        try:
            req=Request(url,headers={'User-Agent':'BrightEnglishLab/1.0'})
            root=ET.fromstring(urlopen(req,timeout=12).read())
            for item in root.findall('.//item')[:8]:
                title=clean_html(item.findtext('title')); link=(item.findtext('link') or '').strip(); summary=clean_html(item.findtext('description'))
                ident=hashlib.sha256((link or title).encode()).hexdigest()[:16]
                if title and summary and ident not in seen: articles.append({'id':ident,'source':source,'title':title,'link':link,'published':item.findtext('pubDate') or '', 'en':summary,'zh':''})
        except Exception: continue
    articles=articles[:6]
    for article in articles:
        try:
            prompt=f"Translate this news title and summary into complete Traditional Chinese. Return plain text only. Title: {article['title']} Summary: {article['en']}"
            article['zh'],_=call_ai([{'role':'user','content':prompt}],False)
        except Exception: article['zh']='（尚未設定 AI 翻譯，以下保留英文 RSS 摘要。）'
    community=[]
    write(RSS_CACHE,{'date':str(date.today()),'articles':articles,'community':community})
    return articles, community

def rss_articles(seen):
    """Health-checked parallel RSS fetch with a reusable, deduplicated article pool."""
    cache=read(RSS_CACHE,{})
    pool=read(ARTICLE_POOL,{'articles':[]}).get('articles',[])
    health=cache.get('health',{})
    today=str(date.today())
    fresh=[a for a in pool if a.get('fetched_at')==today and a.get('id') not in seen]
    if len(fresh)>=3:
        tier='multi-source cache' if len({a.get('source') for a in fresh})>1 else 'single-source cache'
        return fresh[:8],cache.get('community',[]),{'tier':tier,'health':health}
    fetched=[]
    with ThreadPoolExecutor(max_workers=len(RSS_FEEDS)) as workers:
        jobs=[workers.submit(fetch_feed,source,url) for source,url in RSS_FEEDS]
        for job in as_completed(jobs):
            source,items,status=job.result(); health[source]=status; fetched.extend(items)
    fetched=merge_articles(fetched)
    for article in fetched:
        try:
            prompt=f"Translate this news title and summary into complete Traditional Chinese. Return plain text only. Title: {article['title']} Summary: {article['en']}"
            article['zh'],_=call_ai([{'role':'user','content':prompt}],False)
        except Exception: article['zh']='中文翻譯暫時無法取得；可先閱讀英文摘要。'
    pool=merge_articles(fetched+pool)[:240]
    write(ARTICLE_POOL,{'updated_at':today,'articles':pool})
    community=[]
    write(RSS_CACHE,{'date':today,'articles':fetched,'community':community,'health':health})
    available=[a for a in fetched if a.get('id') not in seen]
    if available:
        tier='multi-source RSS' if len({a.get('source') for a in available})>1 else 'single-source RSS'
        return available[:8],community,{'tier':tier,'health':health}
    old=[dict(a,cache=True) for a in pool if a.get('id') not in seen]
    if old: return old[:8],community,{'tier':'cached article','health':health}
    return [],community,{'tier':'ai-needed','health':health}

NEWS_LIMITS={
    'one':{'reading':300,'listening':120,'sentence':15},
    'two':{'reading':450,'listening':150,'sentence':20},
    'three':{'reading':600,'listening':180,'sentence':25},
    'four':{'reading':700,'listening':220,'sentence':None}
}
def cache_key(kind, difficulty, article):
    ident=article.get('id') or hashlib.sha256((article.get('title','')+article.get('link','')).encode()).hexdigest()[:16]
    return f'{date.today()}|{kind}|{difficulty}|{ident}'
def grounded(anchors, article):
    source_words=set(word_list((article.get('title','')+' '+article.get('en','')).lower()))
    if not isinstance(anchors,list) or len(anchors)<2: return False
    return all(len(set(word_list(str(anchor).lower()))&source_words)>=2 for anchor in anchors[:3])
def validate_news_rewrite(result, article, difficulty, kind):
    key=difficulty_key(difficulty); text=str(result.get('en','')); words=word_list(text); sentences=sentence_words(text)
    average=round(len(words)/max(1,len(sentences)),1); clauses=len(re.findall(r'\b(which|that|although|because|while|whereas|unless|despite|whereby|whose)\b',text,re.I))
    required=NEWS_LIMITS[key][kind]; limit=NEWS_LIMITS[key]['sentence']; fallback=bool(article.get('ai'))
    source_ok=(fallback and result.get('source_name')=='AI generated, not live news') or (result.get('source_url')==article.get('link') and result.get('source_name')==article.get('source') and bool(article.get('link')))
    base=bool(result.get('zh')) and source_ok and grounded(result.get('facts_used'),article) and len(words)>=required and (limit is None or average<=limit) and (key!='four' or clauses>=3)
    if kind=='reading': base=base and 3<=len(result.get('questions',[]))<=5 and valid_generated({'questions':result.get('questions',[])})
    else:
        base=base and 3<=len(result.get('questions',[]))<=5 and valid_generated({'questions':result.get('questions',[])})
        # Correct options must point to at least two thirds of the spoken material.
        positions=[]
        for q in result.get('questions',[]):
            options=q.get('o',[]); ans=q.get('ans',0); answer=options[ans] if isinstance(ans,int) and ans<len(options) else ''
            found=[text.lower().find(w.lower()) for w in word_list(answer) if len(w)>3 and text.lower().find(w.lower())>=0]
            if found: positions.append(min(found))
        base=base and len({min(2,int(p/max(1,len(text))*3)) for p in positions})>=2
    return base,{'word_count':len(words),'average_sentence_length':average,'clauses':clauses,'estimated_level':key,'required_minimum':required,'source_verified':source_ok,'grounded':grounded(result.get('facts_used'),article)}
def generate_from_news(article, difficulty, kind):
    if not article.get('title') or not article.get('en') or not article.get('source') or (not article.get('link') and not article.get('ai')):
        raise ValueError('RSS source metadata is incomplete.')
    key=difficulty_key(difficulty); limits=NEWS_LIMITS[key]
    profile={
        'one':'Use simple B2 vocabulary and short sentences.',
        'two':'Use C1 business and academic vocabulary, with useful background explanation.',
        'three':'Use advanced C1+/C2 vocabulary, complex structures, and analysis of likely effects.',
        'four':'Use C2 academic vocabulary, multiple subordinate clauses, and explicit logical turns.'
    }[key]
    target=limits[kind]
    kind_text='a TOEIC-style listening script' if kind=='listening' else 'a reading article'
    question_rule='Create 3 to 5 multiple-choice questions with options in o, integer answer index in ans, and why.'
    fallback_note='This is an AI fallback, not live news; label source_name exactly "AI generated, not live news" and source_url as an empty string.' if article.get('ai') else 'Copy source_name and source_url exactly.'
    prompt=f'''Rewrite ONLY the supplied news material as {kind_text}. Do not invent events, people, organisations, quotations, dates, or numbers. You may explain general background only when it does not assert a new event-specific fact. {profile} The English text must be at least {target} words. Include a complete Traditional Chinese translation. {question_rule} Return JSON with en, zh, questions, source_name, source_url, source_date, facts_used. facts_used must contain 2 to 3 short factual phrases grounded in the supplied title or summary. {fallback_note}
SOURCE NAME: {article['source']}
SOURCE DATE: {article.get('published','')}
SOURCE URL: {article['link']}
RSS TITLE: {article['title']}
RSS SUMMARY: {article['en']}'''
    last={}; provider=''
    for _ in range(3):
        text,provider=call_ai([{'role':'system','content':'Return valid JSON only. Ground every event-specific statement in the supplied RSS title and summary.'},{'role':'user','content':prompt}],True)
        candidate=json.loads(text); candidate['source_name']='AI generated, not live news' if article.get('ai') else article['source']; candidate['source_url']='' if article.get('ai') else article['link']; candidate['source_date']=article.get('published','')
        ok,last=validate_news_rewrite(candidate,article,key,kind)
        if ok: return candidate,provider,last
    raise ValueError('Generated content did not pass the required length, source, grounding, or difficulty validation.')
def cached_news_rewrite(article, difficulty, kind):
    key=cache_key(kind,difficulty,article); store=read(NEWS_REWRITE_CACHE,{'items':{}}); items=store.get('items',{})
    if key in items: return items[key],True
    daily=[v for k,v in items.items() if k.startswith(f'{date.today()}|{kind}|{difficulty}|')]
    cap=2 if kind=='listening' else 3
    if len(daily)>=cap: raise ValueError(f'Daily {kind} generation limit reached for this difficulty.')
    result,provider,validation=generate_from_news(article,difficulty,kind)
    result.update({'provider':provider,'validation':validation,'kind':kind,'cache_key':key})
    items[key]=result; store['items']=items; write(NEWS_REWRITE_CACHE,store)
    return result,False

DAILY_TOPICS={
    'one':['international cooperation','consumer technology','space science'],
    'two':['social history','performing arts','small-business strategy'],
    'three':['climate adaptation','public health systems','global economics'],
    'four':['diplomatic negotiation','research ethics','cultural policy']
}
DAILY_MINIMUMS={'one':{'reading':300,'quiz':300,'listening':120,'sentence':15},'two':{'reading':450,'quiz':450,'listening':150,'sentence':20},'three':{'reading':600,'quiz':600,'listening':180,'sentence':25},'four':{'reading':700,'quiz':700,'listening':220,'sentence':None}}
def daily_cache_key(kind,difficulty,index): return f'{date.today()}|{kind}|{difficulty}|{index}'
def daily_seed(kind,difficulty,index):
    minimum=DAILY_MINIMUMS[difficulty][kind]; topic=DAILY_TOPICS[difficulty][index if kind!='listening' else 0]
    sentence=f'This seed lesson explores {topic} through clear examples, careful context, and a balanced explanation for English learners.'
    text=' '.join([sentence]*((minimum//len(sentence.split()))+2))
    questions=[]
    if kind in {'quiz','listening'}:
        questions=[
            {'stem':'What is the main focus of the passage?','o':[f'An explanation of {topic}.','A fictional adventure.','A restaurant review.','A sports result.'],'ans':0,'why':'The passage repeatedly develops this topic.'},
            {'stem':'Which approach does the passage emphasize?','o':['Using context and examples.','Avoiding all details.','Changing the subject.','Making an unsupported claim.'],'ans':0,'why':'The seed passage explicitly names context and examples.'},
            {'stem':'What can be inferred about the intended reader?','o':['The reader is learning English through a topic.','The reader is buying a ticket.','The reader is judging a contest.','The reader is repairing equipment.'],'ans':0,'why':'The material is written as an English-learning lesson.'},
            {'stem':'The word "balanced" is closest in meaning to','o':['fair and measured','careless','unrelated','impossible'],'ans':0,'why':'Balanced describes a fair, measured explanation.'}
        ]
    return {'en':text,'zh':'本次為種子內容。此教材用於在 AI 額度不足時維持練習流程。','questions':questions,'topic':topic,'status':'seed','validation':{'word_count':len(text.split()),'estimated_level':difficulty,'required_minimum':minimum}}
def validate_daily(item,kind,difficulty):
    key=difficulty_key(difficulty); text=str(item.get('en','')); word_count=len(text.split()); sentences=sentence_words(text); avg=round(word_count/max(1,len(sentences)),1); clauses=len(re.findall(r'\b(which|that|although|because|while|whereas|unless|despite|whereby|whose)\b',text,re.I)); config=DAILY_MINIMUMS[key]; ok=word_count>=config[kind] and bool(item.get('zh'))
    if config['sentence'] is not None: ok=ok and avg<=config['sentence']
    else: ok=ok and clauses>=3
    if kind in {'quiz','listening'}: ok=ok and len(item.get('questions',[]))==4 and valid_generated({'questions':item.get('questions',[])})
    return ok,{'word_count':word_count,'average_sentence_length':avg,'clauses':clauses,'estimated_level':key,'required_minimum':config[kind]}
def generate_daily(kind,difficulty,index):
    key=difficulty_key(difficulty); topic=DAILY_TOPICS[key][index if kind!='listening' else 0]; config=DAILY_MINIMUMS[key]
    profiles={'one':'B2 vocabulary, short sentences, concrete explanations.','two':'C1 vocabulary, moderate sentence length, useful context.','three':'advanced C1+/C2 vocabulary, complex but clear reasoning.','four':'C2 academic vocabulary, multiple clauses, concessions, contrasts, and logical transitions.'}
    mode='listening script in a TOEIC-like informative style' if kind=='listening' else 'reading article'
    question_rule='Include exactly four multiple-choice questions: main idea, detail, inference, and vocabulary. Each needs o with four unique options, ans as an integer, and why.' if kind in {'quiz','listening'} else 'Do not include questions.'
    prompt=f'''Create one original English-learning {mode} about {topic}. It must be a non-fiction educational text, not a current-news report and not a claim about a real breaking event. Target: {profiles[key]} Write at least {config[kind]} English words, followed by a complete Traditional Chinese translation. {question_rule} Return JSON with topic, en, zh, questions. Do not use placeholder text.'''
    last={}; provider=''
    for _ in range(3):
        text,provider=call_ai([{'role':'system','content':'Return valid JSON only. Obey the exact word minimum and difficulty constraints.'},{'role':'user','content':prompt}],True)
        item=json.loads(text); ok,last=validate_daily(item,kind,key)
        if ok:
            item.update({'status':'ready','provider':provider,'validation':last,'topic':item.get('topic') or topic})
            return item
    raise ValueError('AI content did not meet the required word count, difficulty, or question validation after three attempts.')
def get_daily_content(kind,difficulty,index):
    key=difficulty_key(difficulty); max_index=0 if kind=='listening' else 2
    if kind not in {'reading','quiz','listening'} or not isinstance(index,int) or index<0 or index>max_index: raise ValueError('Invalid daily content request.')
    cache=read(DAILY_AI_CACHE,{'items':{}}); items=cache.get('items',{}); ident=daily_cache_key(kind,key,index)
    if ident in items: return items[ident],True
    try: item=generate_daily(kind,key,index)
    except QuotaError: raise
    except Exception:
        item=daily_seed(kind,key,index)
    items[ident]=item; cache['items']=items; write(DAILY_AI_CACHE,cache)
    return item,False
def reset_today():
    payload=read(DATA,default_data()); payload.get('days',{}).pop(str(date.today()),None); write(DATA,payload)
    cache=read(DAILY_AI_CACHE,{'items':{}}); prefix=str(date.today())+'|'; cache['items']={k:v for k,v in cache.get('items',{}).items() if not k.startswith(prefix)}; write(DAILY_AI_CACHE,cache)
    return payload

class App(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/api/data': return self.respond(read(DATA,default_data()))
        if self.path=='/api/history': return self.respond(read(HISTORY,{'questions':[],'words':[]}))
        if self.path=='/api/config':
            cfg=read(CONFIG,{})
            for p in cfg.get('providers',{}).values(): p['key']='SAVED' if p.get('key') else ''
            return self.respond(cfg)
        return super().do_GET()
    def do_POST(self):
        try: body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
        except json.JSONDecodeError: return self.respond({'error':'Invalid JSON'},400)
        if self.path=='/api/data': write(DATA,body); return self.respond({'ok':True})
        if self.path=='/api/history': write(HISTORY,body); return self.respond({'ok':True})
        if self.path=='/api/rss':
            articles, community, meta=rss_articles(set(body.get('seen',[])))
            return self.respond({'articles':articles,'community':community,'meta':meta})
        if self.path in {'/api/news-rewrite','/api/news-listening'}:
            kind='listening' if self.path.endswith('listening') else 'reading'
            try:
                result,hit=cached_news_rewrite(body.get('article',{}),body.get('difficulty','two'),kind)
                return self.respond({'result':result,'cached':hit})
            except Exception as e:
                return self.respond({'error':str(e)},422)
        if self.path=='/api/longread':
            article=body.get('article',{}); difficulty=body.get('difficulty','★★')
            profile={
                'one':'B2; common university and daily-business vocabulary; average sentence length at most 15 words; avoid rare C2 words.',
                'two':'C1; common business and academic vocabulary; average sentence length at most 20 words; avoid rare C2 words.',
                'three':'C1+/C2; advanced academic and business vocabulary; average sentence length at most 25 words.',
                'four':'C2/GRE; dense academic vocabulary, at least three subordinate clauses, long multi-clause sentences.'
            }[difficulty_key(difficulty)]
            prompt=f'''Create one complete English reading-exam article of at least 600 words based on this RSS topic and summary. Generate it in ONE response, not segments. Target: {profile} Then provide a complete Traditional Chinese translation and 5 to 8 questions covering main idea, detail, inference, vocabulary, and author attitude. Return JSON {{en,zh,questions:[{{stem,o:[four unique options],ans,why}}]}}. Topic: {article.get('title','')} Summary: {article.get('en','')}'''
            last_meta={}
            try:
                for _ in range(3):
                    text,provider=call_ai([{'role':'system','content':'Return valid JSON only. Do not relax the stated length or difficulty constraints.'},{'role':'user','content':prompt}],True)
                    result=json.loads(text); ok,last_meta=validate_reading(result,difficulty)
                    if ok: return self.respond({'result':result,'provider':provider,'validation':last_meta})
                return self.respond({'error':'未達規格：AI 連續三次未通過 600 詞／難度驗證。','validation':last_meta},422)
            except Exception as e: return self.respond({'error':str(e),'validation':last_meta},503)
        if self.path=='/api/listening':
            difficulty=body.get('difficulty','★★')
            profile={'one':'B2, short clear sentences and common vocabulary.','two':'C1, common business and academic vocabulary.','three':'C1+/C2, complex business or academic language.','four':'C2/GRE, dense advanced academic language and complex logical links.'}[difficulty_key(difficulty)]
            prompt=f'''Create one English listening passage of at least 120 words for {profile} and at least 3 questions. Questions must test different thirds of the material: early, middle, and late information. Return JSON {{text,questions:[{{stem,o:[four unique options],ans,why}}]}}. Do not use duplicate options.'''
            last_meta={}
            try:
                for _ in range(3):
                    text,provider=call_ai([{'role':'system','content':'Return valid JSON only. Meet every length, question-count, and coverage requirement.'},{'role':'user','content':prompt}],True)
                    result=json.loads(text); ok,last_meta=validate_listening(result,difficulty)
                    if ok: return self.respond({'result':result,'provider':provider,'validation':last_meta})
                return self.respond({'error':'未達規格：AI 連續三次未通過聽力驗證。','validation':last_meta},422)
            except Exception as e: return self.respond({'error':str(e),'validation':last_meta},503)
        if self.path=='/api/longread':
            article=body.get('article',{}); difficulty=body.get('difficulty','★★')
            prompt=f'''Create one complete English reading-exam article of at least 600 words based on this RSS topic and summary. Generate it in ONE response, not segments. Difficulty: {difficulty}. Then provide a complete Traditional Chinese translation and 5–8 questions covering main idea, detail, inference, vocabulary, and author attitude. Return JSON {{en,zh,questions:[{{stem,o:[four unique options],ans,why}}]}}. Topic: {article.get('title','')} Summary: {article.get('en','')}'''
            text,provider=call_ai([{'role':'system','content':'Return valid JSON only; every question must be based on the generated article.'},{'role':'user','content':prompt}],True)
            result=json.loads(text)
            if len(re.findall(r"[A-Za-z]+",result.get('en','')))<600 or not valid_generated({'questions':result.get('questions',[])}): return self.respond({'error':'Long reading validation failed'},422)
            return self.respond({'result':result,'provider':provider})
        if self.path=='/api/config':
            old=read(CONFIG,{})
            for k,v in body.get('providers',{}).items():
                if v.get('key')=='SAVED': v['key']=old.get('providers',{}).get(k,{}).get('key','')
            write(CONFIG,body); return self.respond({'ok':True})
        try:
            if self.path=='/api/generate':
                quality='''Return valid JSON only. Generate authentic TOEIC, IELTS, or TOEFL-style items, never trivia or meaningless questions. Every vocabulary item must include a genuine Traditional-Chinese definition; never use labels such as 核心學術字彙 or 高頻詞 as a definition. Every question needs non-empty unique options and an answer that exists among them. For a fill-in-the-blank item, the sentence must contain at least 12 words and at least two strong context clues (collocation, cause/effect, contrast, definition, or synonym). Never use “Please use _____ in a sentence”, “The word _____”, or “fill in the blank”. Reject the item yourself if any distractor can also fit naturally; fill-in items must be 30% or less of a vocabulary set. If the requested difficulty is ★★★★/C2, model GRE Text Completion: include two or more logical turns (concession, contrast, or causation), place the blank away from its clues through subordinate or parenthetical clauses, use rare advanced academic vocabulary and near-synonym distractors, and regenerate whenever another choice also satisfies the logic. GRE-level reading must use dense long sentences with multiple clauses, inversions, and abstract nouns.'''
                last=None
                for _ in range(3):
                    text,provider=call_ai([{'role':'system','content':quality},{'role':'user','content':body.get('prompt','')}],True)
                    last=json.loads(text)
                    if valid_generated(last): return self.respond({'result':last,'provider':provider})
                return self.respond({'error':'Generated content failed local quality validation; no repeated fallback was used.'},422)
            if self.path=='/api/chat':
                text,provider=call_ai(body.get('messages',[]),False); return self.respond({'reply':text,'provider':provider})
        except Exception as e: return self.respond({'error':str(e)},503)
        return self.respond({'error':'Not found'},404)
    def respond(self,obj,code=200):
        raw=json.dumps(obj,ensure_ascii=False).encode('utf-8'); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def log_message(self,*args): pass
if __name__=='__main__':
    print('Bright English Lab: http://localhost:8765')
    # Warm the health table and pool without delaying the local web server.
    Thread(target=lambda: rss_articles(set()),daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1',8765),App).serve_forever()
