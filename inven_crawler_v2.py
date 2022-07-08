import re
import os
import time
import random
import logging
from typing import Union
import datetime as dt

from bs4 import BeautifulSoup
from tqdm.auto import tqdm
import pandas as pd

import requests


class InvenCrawler:
    url: str = "https://www.inven.co.kr/board"
    url_comment: str = "https://www.inven.co.kr/common/board/comment.json.php"
    HEADERS: dict = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }
    board_type: str
    board_id: int
    filename: str
    data: list
    
    regex_hit = re.compile(r"(?<=추천: )\d+")
    regex_view = re.compile(r"(?<=조회: )\d+")
    
    def __init__(self, board_type: str, board_id: int, filename: str):
        """크롤러 초기화

        :param board_type: 게시판 타입
        :param board_id: 게시판 ID
        :param filename: 파일 이름
        """
        self.board_type = board_type
        self.board_id = board_id
        self.filename = filename
        self.data = []
    
    @classmethod
    def parsing_from_article(cls, src: str) -> dict:
        """본문 내용 분석

        :param src: HTML 소스
        :return: 분석된 내용
        """
        soup = BeautifulSoup(src, "lxml")

        article_writer = soup.select_one("div.articleWriter").text.strip()
        article_date = soup.select_one("div.articleDate").text.strip()

        article_hit = soup.select_one("div.articleHit").text.strip()
        article_view = cls.regex_view.search(article_hit).group()
        article_like = cls.regex_hit.search(article_hit).group()
        article_category = soup.select_one("div.articleCategory").text.strip()
        article_title = soup.select_one("div.articleTitle").text.strip()
        article_content = soup.select_one("#powerbbsContent").text.strip()

        article = {
            "article_writer": article_writer,
            "article_date": article_date,
            "article_view": article_view,
            "article_like": article_like,
            "article_title": article_title,
            "article_content": article_content,
            "article_category": article_category,
        }
        return article
    
    def crawling_article_comment(self, sess: requests.Session, article_id: int):
        """본문 내용 분석

        :param sess: 연결 세션
        :param article_id: 게시글 ID
        :return: 분석된 내용
        """
        params = {
            "dummy": int(dt.datetime.now().timestamp() * 1000)
        }
        data = {
            "comeidx": f"{self.board_id}",
            "articlecode": f"{article_id}",
            "sortorder": "date",
            "act": "list",
            "replynick": "",
            "replyidx": "0",
            "uploadurl": "",
            "imageposition": "",
        }
        resp_comment = sess.post(self.url_comment, data=data, params=params)
        if resp_comment.json()['lastblock'] != 0:
            time.sleep(0.5)
            data["titles"] = "|".join([f"{i}" for i in range(100, resp_comment.json()['lastblock'] + 1, 100)])
            resp_comment = sess.post(self.url_comment, data=data, params=params)
        return resp_comment.json()
    
    def crawling_article(self, article_id: int):
        sess = requests.Session()
        resp = sess.get(f"{self.url}/{self.board_id}/{article_id}", headers=self.HEADERS)
        resp.raise_for_status()
        article = self.parsing_from_article(resp.text)
        article["board_id"] = self.board_id
        article["article_id"] = article_id
        article["comment_data"] = self.crawling_article_comment(sess, article_id)
        return article

    def save_data(self):
        if not self.data:
            return False
        elif not os.path.isfile(self.filename):
            pd.DataFrame(self.data).to_json(self.filename, force_ascii=False)
        else:
            pd.concat([pd.read_json(self.filename), pd.DataFrame(self.data)]).drop_duplicates("article_id").reset_index(drop=True).to_json(self.filename, force_ascii=False)
        self.data.clear()
        return True

    def crawling(
            self,
            auto_save: bool = True, sampling: bool = False,
            max_idx: Union[int, bool, None] = None,
            min_idx: Union[int, bool, None] = None,
            slow: bool = False,
            step: int = 1,
    ):
        """크롤링 한다

        :param slow: 작동 주기를 늘림
        :param auto_save: 자동 저장을 하는가?
        :param sampling: 100개만 크롤링 하는가?
        :param max_idx: 시작 인덱스는 어디인가? True: 이어하기, int: 지정된 숫자에서 시작, None: 웹사이트에서 가져옴
        :param min_idx: 끝 인덱스는 어디인가?None: 웹에서 가져옴, > 0: 지정된 숫자에서 끝, < 0: max_idx에서 해당 수치를 뺌
        :param step: 인덱스 스텝
        :return:
        """
        # max_idx == True
        if isinstance(max_idx, bool) and max_idx:

            if os.path.isfile(self.filename):
                max_idx = min(pd.read_json(self.filename).to_dict()['article_id'].values())
                print("max_idx: load from file:", max_idx)
            else:
                max_idx = None
                print("max_idx: can not load from file:", max_idx)
        
        if not max_idx:
            resp = requests.get(f"{self.url}/{self.board_type}/{self.board_id}", headers=self.HEADERS)
            soup = BeautifulSoup(resp.text, "lxml")
            length = len(soup.select(".board-list > table > tbody > tr.notice"))
            print("notice length:", length)
            max_idx = soup.select(f".board-list > table > tbody > tr")[length].select_one("td.num").text.strip()
            print("max_idx: load from web:", max_idx)

        if min_idx is None:
            try:
                resp = requests.get(f"{self.url}/{self.board_id}", params={"p": 500}, headers=self.HEADERS)
                soup = BeautifulSoup(resp.text, "lxml")
                min_idx = soup.select(".board-list > table > tbody > tr")[-1].select_one("td.num").text.strip()
                print("min_idx: load from web:", min_idx)
            except:
                min_idx = 0
                print("min_idx: can not load from web:", min_idx)
        elif isinstance(min_idx, int) and min_idx > 0:
            pass
        elif isinstance(min_idx, int) and min_idx < 0:
            min_idx = int(max_idx) - abs(min_idx)
        else:
            min_idx = 0

        max_idx, min_idx = int(max_idx), int(min_idx)
        print("max_idx:", max_idx, "min_idx:", min_idx)

        for i in tqdm(range(max_idx, min_idx, step * -1)):
            try:
                self.data.append(self.crawling_article(i))
            except Exception as e:
                print(e)
            time.sleep(random.random())
            if slow:
                time.sleep(random.random())

            if auto_save and not len(self.data) % 50:
                self.save_data()

            if sampling and len(self.data) > 100:
                break
            
        self.save_data()
        return self


if __name__ == "__main__":
    board_type = "fifaonline4"
    board_id = 3146
    filename = "inven.fifaonline4.자유게시판.json"
    InvenCrawler(board_type, board_id, filename).crawling(sampling=True, max_idx=True)
