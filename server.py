from pathlib import Path
import uuid
import os

import responder
import requests

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
)

def get_objs(layout, results):
    if not isinstance(layout, LTContainer):
        return
    for obj in layout:
        if isinstance(obj, LTTextLine):
            results.append({'bbox': obj.bbox, 'text' : obj.get_text(), 'type' : type(obj)})
        get_objs(obj, results)

def extract_text(path):

    out = ""
    with open(path, "rb") as f:
        parser = PDFParser(f)
        document = PDFDocument(parser)
        if not document.is_extractable:
            raise PDFTextExtractionNotAllowed
        laparams = LAParams(
            all_texts=True,
        )
        rsrcmgr = PDFResourceManager()
        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.create_pages(document):
            interpreter.process_page(page)
            layout = device.get_result()
            results = []
            get_objs(layout, results)
            for r in results:
                out += r['text']
    return out


def parentdir(path='.', layer=0):
    return Path(path).resolve().parents[layer]

BASE_DIR = parentdir(__file__,1)

api = responder.API(
    static_dir=str(BASE_DIR.joinpath('static')),
)

@api.route("/")
async def greet_world(req, resp):
    resp.content = api.template('index.html')

@api.route("/upload")
async def sync_upload_file(req, resp):

    print("access")

    data = await req.media(format='files')
    file_path = './temp/{}.pdf'.format(str(uuid.uuid4()))
    file=data['file']
    with open(file_path, 'wb') as f:
        f.write(file['content'])
    text = extract_text(file_path)
    # print(text)

    # os.remove(file_path)

    resp.content = api.template('success.html', {'text':text})



# @api.route("/upload")
# async def upload_file(req, resp):
#     @api.background.task
#     def process_data(data):
#         file_path = './temp/{}.pdf'.format(str(uuid.uuid4()))
#         file=data['file']
#         with open(file_path, 'wb') as f:
#             f.write(file['content'])
#         
#         return main(file_path)
#         
#     data = await req.media(format='files')
#     text = process_data(data)
# 
#     resp.content = api.template('success.html', {'text':text})

if __name__ == '__main__':
    api.run()