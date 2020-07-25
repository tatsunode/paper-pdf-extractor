from pathlib import Path
import uuid
import os

from analyzer import Extractor
from pdf2image import convert_from_path, convert_from_bytes

import responder
import requests

def parentdir(path='.', layer=0):
    return Path(path).resolve().parents[layer]

BASE_DIR = Path(__file__).resolve().parent
print(BASE_DIR)

api = responder.API(
    static_dir=str(BASE_DIR.joinpath('static')),
)

@api.route("/")
async def greet_world(req, resp):
    resp.content = api.template('index.html')

@api.route("/upload")
async def sync_upload_file(req, resp):
    data = await req.media(format='files')
    file_path = './temp/{}.pdf'.format(str(uuid.uuid4()))
    file=data['file']
    with open(file_path, 'wb') as f:
        f.write(file['content'])
    
    # Extract PDF
    extractor = Extractor(file_path)
    pages = extractor.exec()
    paper = {
        "pages": pages
    }

    # Get Images
    pdf_images = convert_from_path(file_path, output_folder='./temp')
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    for page_index, image in enumerate(pdf_images):
        image_path = "static/{}-{}.jpg".format(file_name, page_index)
        image.save(image_path, quality=50)
        paper['pages'][page_index]['image_path'] = image_path

    resp.content = api.template('success.html', paper=paper)

if __name__ == '__main__':

    if 'PROD' in os.environ:
        api.run(address='0.0.0.0', port=80)
    else:
        api.run()