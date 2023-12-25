import io
import IPython
from PIL import Image
from pathlib import Path
from dotenv import dotenv_values
from w3lib.url import parse_data_uri
from uuid_extensions import uuid7str
from flask import Flask, render_template, request

ENV = dotenv_values(".env")

app = Flask(__name__)
app.secret_key = ENV['APP_SECRET_KEY']
    
MAPS_API_KEY = ENV['MAPS_API_KEY']
OUTPUT_DIR = ENV['OUTPUT_DIR']
Path(OUTPUT_DIR).mkdir(exist_ok=True, parents=True)

@app.route("/", methods=['GET'])
def screenshot():
    id = request.args.get('id')
    lat = request.args.get('lat', 45.531776760335504)
    lng = request.args.get('lng', -73.55924595184348)
    return render_template('index.html', id=id, lat=lat, lng=lng, key=MAPS_API_KEY)


@app.route("/upload", methods=['POST'])
def upload():
    """
    Saves an image locally.
    Could be modified to upload the image to a bucket or other backend.
    """
    data = request.json
    # Generates an id if none is present
    id = data.get('id', uuid7str()) 
    pano = data['pano']
    date = '_'.join(data['date'].split(' '))
    image = parse_data_uri(data['img'])
    image = Image.open(io.BytesIO(image.data))
    path = Path(f'{OUTPUT_DIR}/{id}')
    path.mkdir(exist_ok=True, parents=True)
    image.save(path / f'{id}_{date}_{pano}.jpg')
    return 'ok'

