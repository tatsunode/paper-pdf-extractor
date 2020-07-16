import argparse
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

from pdf2image import convert_from_path, convert_from_bytes

import unicodedata
import re

def extract_objects(layout, extracted_objects):
    """ extract text,image recursively """
    if not isinstance(layout, LTContainer):
        return
    
    for obj in layout:
        if isinstance(obj, LTTextLine):
            extracted_objects.append({
                    "type": "text",
                    "text": obj.get_text(),
                    "bbox": {
                        "x1": obj.bbox[0],
                        'x2': obj.bbox[1],
                        'y1': obj.bbox[2],
                        'y2': obj.bbox[3]
                    }
                })
            
            # recursive call
            
        elif isinstance(obj, LTFigure):
            extracted_objects.append({
                    "type": "image",
                    "bbox": {
                        "x1": obj.bbox[0],
                        'x2': obj.bbox[1],
                        'y1': obj.bbox[2],
                        'y2': obj.bbox[3]
                    }
                })
        extract_objects(obj, extracted_objects)


def extract_pdf(pdf_file_path):

    paper_data = {
        "pages": []
    }

    image_path_list = dump_images(pdf_file_path)

    with open(pdf_file_path, "rb") as f:
        parser = PDFParser(f)
        document = PDFDocument(parser)
        if not document.is_extractable:
            raise PDFTextExtractionNotAllowed
        laparams = LAParams(all_texts=True)
        rsrcmgr = PDFResourceManager()
        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)

        pages = list(PDFPage.create_pages(document))

        for page_no, page in enumerate(pages):
            interpreter.process_page(page)
            layout = device.get_result()
            
            contents = []
            extract_objects(layout, contents)

            page_data = {
                "bbox": {
                    "x1": page.mediabox[0],
                    "x2": page.mediabox[2],
                    "y1": page.mediabox[1],
                    "y2": page.mediabox[3],
                },
                "contents": contents,
                "image_path": image_path_list[page_no],
            }
            page_data['full_text'] = concat_texts(contents)

            paper_data['is_japanese'] = is_japanese(page_data['full_text'])
            paper_data['pages'].append(page_data)   
    
    return paper_data


def is_japanese(text):
    return True if re.search(r'[ぁ-んァ-ン]', text) else False 


def english_text_tokenize(text):
    pass



def concat_texts(contents):

    text = ""
    for content in contents:
        if 'text' in content:
            text += content['text']
    return text

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

    text = extract_pdf(args.file_path)

    print(text)
