# -*- coding: utf-8
import argparse
import unicodedata
import re
import json
import math
import numpy as np

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfpage import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import (
    LAParams,
    LTContainer,
    LTTextLine,
    LTFigure
)

class Extractor:

    def __init__(self, pdf_file_path):

        self.pdf_file_path = pdf_file_path
        self.pages = []

    def exec(self):

        # 1. PDF file -> Pages
        self.pdf_to_pages()

        # 2. Clustering PDF Elements for each page
        for page_index, page in enumerate(self.pages):
            clusters = self.page_to_clusters(page)
            # Overwrite elements
            page['elements'] = list(clusters.values())

        # 3. Merg elements in same cluster
        for page_index, page in enumerate(self.pages):
            for cluster in page['elements']:
                self.merge_cluster_elements(cluster)

        return self.pages

    def pdf_to_pages(self):
        """
        PDFMinerのページ要素から必要なものを抽出してpage_objectに変換
        """
        with open(self.pdf_file_path, "rb") as f:
            parser = PDFParser(f)
            document = PDFDocument(parser)
            if not document.is_extractable:
                raise PDFTextExtractionNotAllowed
            laparams = LAParams(all_texts=True)
            rsrcmgr = PDFResourceManager()
            device = PDFPageAggregator(rsrcmgr, laparams=laparams)
            interpreter = PDFPageInterpreter(rsrcmgr, device)

            # PDFMinerによるページごとへの分解
            pages = list(PDFPage.create_pages(document))
            for page in pages:
                interpreter.process_page(page)
                layout = device.get_result()

                # elements: page内に存在するPDF要素（text, iamge)
                elements = []
                self._extract_elements(layout, elements)

                # Page
                page_object = {
                    "type": "page",
                    "bbox": { "x1": int(page.mediabox[0]), "x2": int(page.mediabox[2]), "y1": int(page.mediabox[1]), "y2": int(page.mediabox[3]), },
                    "elements": elements
                }
                self.pages.append(page_object)   
   
    def page_to_clusters(self, page):
        """
        ページ内要素をクラスタリング
        """
        elements = page['elements']

        distance_matrix = self._calculate_distance_matrix(elements)
        cluster_id_list = self._make_cluster(distance_matrix, threshold=5)
        # ToDo: クラスタリングの閾値を距離行列の統計から動的に決定する．

        # 各クラスタに属する要素を整理
        clusters = {}
        for element_id, cluster_id in enumerate(cluster_id_list):
            if cluster_id not in clusters:
                clusters[cluster_id] = {
                    "type": "cluster",
                    "elements": []
                }
            element = elements[element_id]
            clusters[cluster_id]['elements'].append(element)

        return clusters

    def merge_cluster_elements(self, cluster):
        """
        同一クラスタ内の要素をまとめる(文章なら一つの文にする)
        """
        # 各クラスタ内の要素をマージ
        cluster_elements = cluster['elements']

        # Merge elements
        cluster['full_text'] = self._get_full_text(cluster_elements)
        cluster['bbox'] = self._get_entire_bbox(cluster_elements)

    # ===
    # PDF要素のうち要るものを抽出
    # ===
    def _extract_elements(self, layout, extracted_elements):
        """ 
        layout(pdf要素)内にあるtext, imageを抽出
        入れ子になっている場合もあるので再帰的に
        """
        if not isinstance(layout, LTContainer):
            return

        for obj in layout:
            if isinstance(obj, LTTextLine):
                extracted_elements.append({
                        "type": "text",
                        "text": str(obj.get_text()),
                        "bbox": { "x1": obj.bbox[0], 'x2': obj.bbox[2], 'y1': obj.bbox[1], 'y2': obj.bbox[3] }
                    })
            elif isinstance(obj, LTFigure):
                extracted_elements.append({
                        "type": "image",
                        "bbox": { "x1": obj.bbox[0], 'x2': obj.bbox[2], 'y1': obj.bbox[1], 'y2': obj.bbox[3] }
                    })
            self._extract_elements(obj, extracted_elements)

    # ===
    # For Element Clustering
    # ===
    def _calculate_distance_matrix(self, elements):
        """
        pdf要素同士 (image, text, pdf要素) 同士の距離行列を作成
        """
        N = len(elements)
        distance_matrix = np.zeros((N, N))

        for i in range(0, N):
            e1 = elements[i]
            for j in range(i+1, N):
                e2 = elements[j]
                if e1['type'] != e2['type']:
                    # make Image and Text as different cluster (long distance)
                    distance = 999
                else:
                    distance = self._calculate_distance_of_two_box(e1['bbox'], e2['bbox'])
                distance_matrix[i][j] = distance
                distance_matrix[j][i] = distance
        return distance_matrix


    def _calculate_distance_of_two_box(self, bbox1, bbox2):
        """
        bbox同士の距離を計算
        """
        c1x1 = min(bbox1['x1'], bbox1['x2'])
        c1x2 = max(bbox1['x1'], bbox1['x2'])
        c1y1 = min(bbox1['y1'], bbox1['y2'])
        c1y2 = max(bbox1['y1'], bbox1['y2'])

        c2x1 = min(bbox2['x1'], bbox2['x2'])
        c2x2 = max(bbox2['x1'], bbox2['x2'])
        c2y1 = min(bbox2['y1'], bbox2['y2'])
        c2y2 = max(bbox2['y1'], bbox2['y2'])

        # X distance
        x_d = 0
        if (c1x1 <= c2x1 <= c1x2) or (c2x1 <= c1x1 <= c2x2):
            x_d = 0
        else:
            x_d = min(abs(c1x2-c2x1), abs(c1x1-c2x2))

        # Y distance
        y_d = 0
        if (c1y1 <= c2y1 <= c1y2) or (c2y1 <= c1y1 <= c2y2):
            y_d = 0
        else:
            y_d = min(abs(c1y2-c2y1), abs(c1y1-c2y2))

        return math.sqrt(x_d**2+y_d**2)

    def _make_cluster(self, distance_matrix, threshold):
        """
        距離行列をもとにユークリディアンクラスタリング
        (距離がthreshold以下の要素が同一クラスタになるように分類)
        """
        # ToDo: 画像は単独でクラスタにする．画像bbox内のテキストをtype: image_textなどにしてその画像のクラスタ内に属させる

        N = len(distance_matrix)
        content_cluster_ids = np.zeros(N)
        current_making_cluster_id = 1

        for i in range(N):
            if content_cluster_ids[i] == 0:
                # 未割当の要素
                self._apply_to_cluster(i, current_making_cluster_id, content_cluster_ids, distance_matrix, threshold)
                current_making_cluster_id += 1

        return content_cluster_ids

    def _apply_to_cluster(self, target_content_id, target_cluster_id, content_cluster_ids, distance_matrix, threshold):
        """ 深さ優先で近くの要素が同一クラスタかどうかを判別していく """

        if content_cluster_ids[target_content_id] != 0:
            # 対象要素はすでにいずれかのクラスタに属する
            return 0

        # 対象要素をクラスタに割り当て
        content_cluster_ids[target_content_id] = target_cluster_id

        # 対象要素の近傍コンテンツも同じ要素に割り当て
        nums = 1
        for j in range(len(distance_matrix)):
            distance = distance_matrix[target_content_id][j]
            if distance < threshold:
                # recursive 
                nums += self._apply_to_cluster(j, target_cluster_id, content_cluster_ids, distance_matrix, threshold)
        # そのクラスタに属するコンテンツ数を返す
        return nums

    # ===
    # 要素のマージ
    # ===
    def _get_full_text(self, elements):

        # ToDo: 改行によって単語が途切れているものは戻す． e.g.) de- vice -> device
        # ToDo: 画像内のテキストは含まない (?)
        full_text = ""
        for e in elements:
            if e['type'] == 'text':
                full_text += e['text']
        return str(full_text)

    def _get_entire_bbox(self, elements):
        min_x = 99999
        max_x = -99999
        min_y = 99999
        max_y = -99999

        for e in elements:
            bbox = e['bbox']
            min_x = min(min_x, bbox['x1'], bbox['x2'])
            max_x = max(max_x, bbox['x1'], bbox['x2'])
            min_y = min(min_y, bbox['y1'], bbox['y2'])
            max_y = max(max_y, bbox['y1'], bbox['y2'])

        return { "x1": min_x, "x2": max_x, "y1": min_y, "y2": max_y }
    


# Under Construction

def is_japanese(text):
    return True if re.search(r'[ぁ-んァ-ン]', text) else False 


def english_text_tokenize(text):
    pass


def dump_images(pdf_file_path):
    pdf_images = convert_from_path(pdf_file_path)
    file_name = pdf_file_path.split(".") [0]

    image_path_list = []

    for page_number, image in enumerate(pdf_images):
        image_path = "static/{}-{}.jpg".format(file_name, page_number)
        image.save(image_path, quality=80)
        image_path_list.append(image_path)

    return image_path_list


if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("file_path")
    args = parser.parse_args()

    extractor = Extractor(args.file_path)
    pages = extractor.exec()

    json.dump(pages, open("out.json", 'w'), indent=4, ensure_ascii=False)