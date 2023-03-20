from urllib.request import urlopen 
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import math
import xml.etree.ElementTree as ET
import ssl
import os
import sys
import threading

'''
조선일보 RSS entity
<item>
    <title>
        제목
    </title>
    <link>https://www.chosun.com/economy/stock-finance/2023/03/14/JZISPC4KEJFUBGIUD2OZRUK62U/</link>
    <guid isPermaLink="true">https://www.chosun.com/economy/stock-finance/2023/03/14/JZISPC4KEJFUBGIUD2OZRUK62U/</guid>
    <dc:creator>
        <![CDATA[ 권순완 기자 ]]>
    </dc:creator>
    <description/>
    <pubDate>Tue, 14 Mar 2023 11:58:27 +0000</pubDate>
    <content:encoded>
        기사 본문
    </content:encoded>
</item>

item에서 <title>, <link>, <pubDate>, <creator> 를 가져온다
'''

ARTICLE_ARCHIVE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/chosun-articles/'
CHOSUN_RSS = 'https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml'
NUMBER_OF_THREAD = 2
INDEX_TITLE, INDEX_URL = 0, 1

# prepare article archive
def mkarch():
    print('make archive: %s' % ARTICLE_ARCHIVE_PATH)
    if not os.path.exists(ARTICLE_ARCHIVE_PATH):
        try:
            os.mkdir(ARTICLE_ARCHIVE_PATH)
        except OSError as e:
            print('[mkdir] ERROR')
            exit()


def to_file(title, body):
    with open (ARTICLE_ARCHIVE_PATH+title, 'w') as file:
        file.write(body)


def get_articles():
    """
    Return a list of articles' info ([title, url])
    """
    articles = []
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
            articles.append([title, link])
            # </item>
    return articles


def print_progress(progress):
    print('\033[?25l')   # hide cursor
    for t in range(1, NUMBER_OF_THREAD+1):
        print('[thread%d] collecting... %0.2f' %(t, progress[t]))
    print('\033[?25h')   # show it back


def collect_articles(tnum, articles, start, end, progress):
    """
    Load articles in quota and write them to dest as file.
    start - int value, included.
    end - int value, excluded.
    """
    count = 0
    # prepare webdriver 
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    for article in articles[start:end]:
        driver.get(article[INDEX_URL])
        try:
            element = WebDriverWait(driver, 3)\
                    .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'section.article-body')))
            body = driver.find_element(By.CSS_SELECTOR, 'section.article-body')
            body = body.text
            to_file(article[INDEX_TITLE], body)
            count += 1
            progress = (count/(end-start))*100
        except TimeoutException:
            print('pass: %s' % article[INDEX_URL])
            continue
    driver.close()
    print('thread%s finished. Collected %d articles' % (tnum, count))
    

def Main():
    global NUMBER_OF_THREAD
    # set the number of thread
    if len(sys.argv) != 1:
        NUMBER_OF_THREAD = int(sys.argv[1])
    # get targets
    article_infos = get_articles()
    # cli info
    for article in article_infos:
        print(article[INDEX_TITLE] + ': ' + article[INDEX_URL])
    print()     # empty line
    mkarch()
    print('collected {0} links.'.format(len(article_infos)))

    ################### multi threading code start ###################
    # calcuate the number of articles per thread to collect(read+write)
    TOTAL_COUNT = len(article_infos)
    articles_per_thread = math.ceil(TOTAL_COUNT/NUMBER_OF_THREAD)
    # create threads
    workers = []
    workload = [0]*(NUMBER_OF_THREAD+1)   # amount of article to be collected per one thread
    progress = [0]*(NUMBER_OF_THREAD+1)
    quota = int(TOTAL_COUNT/NUMBER_OF_THREAD)
    rest = TOTAL_COUNT % NUMBER_OF_THREAD
    for t in range(1, NUMBER_OF_THREAD+1):
        workload[t] = quota
        if rest > 0:
            workload[t] += 1
            rest -= 1

    # start threads
    start_t = time.time()
    print()     # empty line
    for t in range(1, NUMBER_OF_THREAD+1):
        print('thread%d - %d articles' %(t, workload[t]))
        start_idx = quota * (t-1) + 1  # start_idx
        end_idx = start_idx + quota  # end_idx
        try:
            worker = threading.Thread(target=collect_articles, args=(t, article_infos, start_idx, end_idx, progress))
            workers.append(worker)
            worker.start()
        except Exception as e:
            print('[ERROR] %s' % e)

    for worker in workers:
        worker.join()
    end_t = time.time()
    print('\r%-30s %0.2fseconds' %('finished', end_t-start_t))

if __name__ == '__main__':
    Main()

'''
print('\033[?25l')   # hide cursor
start = time.time()
end = time.time()
print('\r%-15s %-0.1f%%' %('crawling...', 100), end='')
'''
# nltk example
# https://m.blog.naver.com/PostView.naver?isHttpsRedirect=true&blogId=bcj1210&logNo=22114994778
