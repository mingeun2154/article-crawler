#!/usr/bin/env python3
"""
Provide multi-threaded crawling API. 
"""
import time
import xml.etree.ElementTree as ET
import ssl
import os
import sys
import threading
from urllib.request import urlopen
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from queue import Queue, Empty
'''
조선일보 RSS entity
<item>
    <title>
        제목
    </title>
    <link>
        https://www.chosun.com/economy/stock-finance/2023/03/14/JZISPC4KEJFUBGIUD2OZRUK62U/
    </link>
    <guid isPermaLink="true">
        https://www.chosun.com/economy/stock-finance/2023/03/14/JZISPC4KEJFUBGIUD2OZRUK62U/
    </guid>
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

###################### global variables ######################
ARTICLE_ARCHIVE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/chosun-articles/'
PERFORMANCE_REPORT_PATH = os.path.dirname(os.path.realpath(__file__)) + '/performance-report.txt'
CHOSUN_RSS = 'https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml'
NUMBER_OF_CRAWLER = 2
NUMBER_OF_DISK_WORKER = 2
INDEX_TITLE, INDEX_URL = 0, 1


def record_performance(current_time, number_of_articles, elapsed_time):
    """
    기사 수집 성능을 파일의 형태로 기록한다.
    기록할 내용: crawler thread 수, disk worker 수, 수집한 기사 개수, 걸린 시간
    """
    file = None
    if not os.path.exists(PERFORMANCE_REPORT_PATH):
        file = open(PERFORMANCE_REPORT_PATH, 'w')
        file.write('TEST_TIME NUMBER_OF_CRAWLER NUMBER_OF_DISK_WORKER NUMBER_OF_ARTICLES ELAPSED_TIME\n')
    else:
        file = open(PERFORMANCE_REPORT_PATH, 'a')

    data = f'{current_time} {NUMBER_OF_CRAWLER} {NUMBER_OF_DISK_WORKER} {number_of_articles} {elapsed_time}\n'
    file.write(data)
    file.close()

def get_formatted_time():
    """
    현재 시각을 "00:48" 형태의 문자열로 반환한다.
    """
    t = time.localtime()
    ftime = time.strftime("%H:%M", t)
    return ftime

def make_archive():
    """
    Prepare article archive.
    """
    print('make archive: %s' % ARTICLE_ARCHIVE_PATH)
    if not os.path.exists(ARTICLE_ARCHIVE_PATH):
        os.mkdir(ARTICLE_ARCHIVE_PATH)
    else:
        old_articles = os.listdir(ARTICLE_ARCHIVE_PATH)
        for old in old_articles:
            os.remove(ARTICLE_ARCHIVE_PATH + old)


def to_file(title, body):
    with open (ARTICLE_ARCHIVE_PATH+title, 'w', encoding="utf-8") as file:
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
                if child.tag == 'title' and child.text is not None:
                    title = child.text
                elif child.tag == 'link' and child.text is not None:
                    link = child.text
            articles.append([title, link])
            # </item>
    return articles


def print_progress(progress):
    print('\033[?25l')   # hide cursor
    for t in range(1, NUMBER_OF_CRAWLER+1):
        print('[thread%d] collecting... %0.2f' %(t, progress[t]))
    print('\033[?25h')   # show it back


def disk_worker(tnum, queue, working_crawler):
    """
    Write article to disk while 'queue' is not empty.
    tnum - Thread number.
    queue - Thread-safe queue. Element is tuple(title, body).
    working_crawler - If this queue and queue is empty, stop this thread.
    """
    while not working_crawler.empty():
        try:
            title, body = queue.get(timeout=2) 
            to_file(title + '.txt',  body)
        except Empty:
            continue


def crawler(tnum, articles, start, end, progress, queue, working_crawler):
    """
    Load articles in quota and write them to dest as file.
    start - int value, included.
    end - int value, excluded.
    queue - Buffer for the articles. disk_worker function will flush buffer items to disk.
    """
    count = 0
    working_crawler.put(tnum)
    # prepare webdriver
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    for article in articles[start:end]:
        driver.get(article[INDEX_URL])
        try:
            WebDriverWait(driver, 2)\
                    .until(\
                    EC.presence_of_all_elements_located(\
                    (By.CSS_SELECTOR, 'section.article-body')))
            body = driver.find_element(By.CSS_SELECTOR, 'section.article-body')
            body = body.text
            queue.put((article[INDEX_TITLE], body))
            count += 1
            progress[tnum] = (count/(end-start))*100
        except TimeoutException:
            print('pass: %s' % article[INDEX_URL])
            continue
    working_crawler.get()
    driver.close()
    # Remain elements are not exactly match to working threads' tnum.
    # Only the number of the elemnts is correct.
    print('thread%s finished. Collected %d articles' % (tnum, count))


def Main():
    global NUMBER_OF_CRAWLER
    global NUMBER_OF_DISK_WORKER
    # set the number of thread
    if len(sys.argv) != 1:
        NUMBER_OF_CRAWLER = int(sys.argv[1])
    # get targets
    article_infos = get_articles()
    # cli info
    """
    for article in article_infos:
        print(article[INDEX_TITLE] + ': ' + article[INDEX_URL])
    print()     # empty line
    """
    make_archive()
    print('collected {0} links.'.format(len(article_infos)))

    ################### multi threading code start ###################
    # calcuate the number of articles per thread to collect(read+write)
    TOTAL_COUNT = len(article_infos)
    # create threads
    workers = []
    workload = [0]*(NUMBER_OF_CRAWLER+1)   # amount of article to be collected per one thread
    progress = [0]*(NUMBER_OF_CRAWLER+1)
    quota = int(TOTAL_COUNT/NUMBER_OF_CRAWLER)
    rest = TOTAL_COUNT % NUMBER_OF_CRAWLER
    for t in range(1, NUMBER_OF_CRAWLER+1):
        workload[t] = quota
        if rest > 0:
            workload[t] += 1
            rest -= 1
    # for thread-coummunication
    queue = Queue()
    working_crawler = Queue()
    # network worker
    start_t = time.time()
    print()     # empty line
    for t in range(1, NUMBER_OF_CRAWLER+1):
        print('thread%d - %d articles' %(t, workload[t]))
        start_idx = quota * (t-1) + 1  # start_idx
        end_idx = start_idx + quota  # end_idx
        try:
            worker = threading.Thread(target=crawler, \
                    args=(t, article_infos, start_idx, end_idx, progress, queue, working_crawler))
            workers.append(worker)
            worker.start()
        except Exception as e:
            print('[ERROR] %s' % e)
    # disk worker
    disk_workers = []
    for t in range(1, NUMBER_OF_DISK_WORKER+1):
        try:
            worker = threading.Thread(target=disk_worker, args=(t, queue, working_crawler))
            disk_workers.append(worker)
            worker.start()
        except Exception as e:
            print(f'[ERROR] {e}')
    # wait for workers
    for worker in workers:
        worker.join()
    for worker in disk_workers:
        worker.join()
    end_t = time.time()
    print('\r%-30s %0.2fs' %('finished', end_t-start_t))

    # record
    saved_articles = os.listdir(ARTICLE_ARCHIVE_PATH)
    current_time = get_formatted_time()
    record_performance(current_time, len(saved_articles), end_t-start_t)

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
