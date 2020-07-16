from pathlib import Path
import uuid
import os

from analizer import *

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

    print("access")

    data = await req.media(format='files')
    file_path = './temp/{}.pdf'.format(str(uuid.uuid4()))
    file=data['file']
    with open(file_path, 'wb') as f:
        f.write(file['content'])
    paper_data = extract_pdf(file_path)

    resp.content = api.template('success.html', paper=paper_data)


if __name__ == '__main__':
    api.run()