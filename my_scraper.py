from urllib.request import urlopen
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import xml.etree.ElementTree as ET
import ssl
import os

CHOSUN_RSS = 'https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml'
'''
조선일보 RSS entity
<item>
    <title>
        <![CDATA[ 유럽·아시아 은행 주가도 폭락…獨코메르츠방크 -12.7%·日미쓰비시은행 -8.6% ]]>
    </title>
    <link>https://www.chosun.com/economy/stock-finance/2023/03/14/JZISPC4KEJFUBGIUD2OZRUK62U/</link>
    <guid isPermaLink="true">https://www.chosun.com/economy/stock-finance/2023/03/14/JZISPC4KEJFUBGIUD2OZRUK62U/</guid>
    <dc:creator>
        <![CDATA[ 권순완 기자 ]]>
    </dc:creator>
    <description/>
    <pubDate>Tue, 14 Mar 2023 11:58:27 +0000</pubDate>
    <content:encoded>
    <![CDATA[ <img src="https://www.chosun.com/resizer/y1UY1B7Zh07gTT7OSByNFTP-0MI=/cloudfront-ap-northeast-1.images.arcpublishing.com/chosun/YUQNIF2RF4T5C6CMR4PH2M2ADQ.png" alt="도쿄에 있는 일본 미쓰비시 은행의 본사." height="350" width="622"/><p>미국 실리콘밸리은행(SVB) 사태의 여파로 미국 은행들의 주가가 폭락하는 가운데 13~14일(현지 시각) 유럽과 일본, 중화권 은행들도 비슷한 상황을 맞았다. 미국발 은행 파산 공포가 전 세계로 번진 것이다.</p> ]]>
    </content:encoded>
</item>

item에서 <title>, <link>, <pubDate>, <creator> 를 가져온다
'''


def get_body(article_url):
    context = ssl._create_unverified_context()
    with urlopen(article_url, context=context) as html:
        bs = BeautifulSoup(html, 'html.parser')
        body = bs.find('section', {'class': 'article-body'})
        if body == None:    
            return None
        else:               
            return body


ARTICLE_ARCHIVE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/chosun-articles/'
def to_file(title, body):
    with open (ARTICLE_ARCHIVE_PATH+title, 'w') as file:
        file.write(body)

################################ main ################################

# [patch] load module
'''
from importlib.machinery import SourceFileLoader
article_chosun = SourceFileLoader("article", "/Users/mingeun/study/crawling/oreilly/article.py").load_module()
'''

article_links = {}
# Feed에서 기사 목록 획득
with urlopen(CHOSUN_RSS) as feed:
    root = ET.fromstring(feed.read())
    items = root.find('channel').findall('item')
    for item in items:
        title, link = None, None
        # <item>
        for child in item:
            if child.tag == 'title' and child.text != None:
                title = child.text
            elif child.tag == 'link' and child.text != None:
                link = child.text
        article_links[title] = link
        # </item>

# prepare article archive
if not os.path.exists(ARTICLE_ARCHIVE_PATH):
    try:
            os.mkdir(ARTICLE_ARCHIVE_PATH)
    except OSError as e:
        print('[mkdir] ERROR')
        exit()

for title in article_links:
    print(title + ': ' + article_links[title])
print('collected {0} links.'.format(len(article_links)))

options = webdriver.ChromeOptions()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
# fetch articles to disk
count = 0
TOTAL_COUNT = len(article_links)
print('\033[?25l')   # hide cursor
start = time.time()
for title in article_links:
    print('\r%-15s %-0.1f%%' %('crawling...', count/TOTAL_COUNT*100), end='')
    driver.get(article_links[title])
    try:
        element = WebDriverWait(driver, 3).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'section.article-body')))
    finally:
        body = driver.find_element(By.CSS_SELECTOR, 'section.article-body')
    if body == None:
        print("{0} : none...".format(article_links[title]))
    else:
        body = body.text
        to_file(title, body)
    count += 1

end = time.time()
print('\r%-15s %-0.1f%%' %('crawling...', 100), end='')
print('\033[?25h')   # show it back
print('\r%-30s %0.2fseconds' %('finished', end-start))

# nltk example
# https://m.blog.naver.com/PostView.naver?isHttpsRedirect=true&blogId=bcj1210&logNo=22114994778
