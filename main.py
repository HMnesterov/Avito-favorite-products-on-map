import os
import ssl
import browser_cookie3
import requests
from fastapi import FastAPI
import uvicorn
from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager
from requests.packages.urllib3.util import ssl_
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from starlette.templating import Jinja2Templates
import sqlite3
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get('API_KEY')
cj = browser_cookie3.chrome()

templates = Jinja2Templates(directory='templates')
app = FastAPI()
con = sqlite3.connect("markers.db", check_same_thread=False)
cur = con.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS map_markers (
address VARCHAR(100),
coords VARCHAR(100) )
""")

CIPHERS = """ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:AES256-SHA"""


class TlsAdapter(HTTPAdapter):
    """Create adapter to go through block from site"""

    def __init__(self, ssl_options=0, **kwargs):
        self.ssl_options = ssl_options
        super(TlsAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, *pool_args, **pool_kwargs):
        ctx = ssl_.create_urllib3_context(ciphers=CIPHERS, cert_reqs=ssl.CERT_REQUIRED, options=self.ssl_options)
        self.poolmanager = PoolManager(*pool_args, ssl_context=ctx, **pool_kwargs)


def create_session() -> Session:
    """Create requests session"""
    session = requests.session()
    adapter = TlsAdapter(ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1)
    session.mount("https://", adapter)
    return session


def get_data_from_current_page(session, page: int) -> list | None:
    """Take favorite products and data about them from page"""
    url = f'https://www.avito.ru/web/1/favorites/items/list?order=added_at__desc&page={page}'
    data = session.request('GET', url, cookies=cj)
    try:
        favorites = data.json()["items"]
        if not favorites:
            return None
        return [get_important_data_from_curr_product(product) for product in favorites]
    except KeyError:
        return None


def get_important_data_from_curr_product(product: dict) -> dict:
    """Take information about the product"""
    item_link: str = "https://www.avito.ru" + product["uri"]
    title: str = product["title"]
    coords: dict = get_geocoords(product["address"])
    return {"coords": coords, "item_link": item_link, "title": title}


def get_geocoords(address: str) -> dict:
    """Get geocoords from DB or yandex geocoding API"""
    res = cur.execute(f"""SELECT coords from map_markers WHERE address='{address}'""").fetchall()
    if not res:
        link = f"https://geocode-maps.yandex.ru/1.x/?apikey={API_KEY}&format=json&geocode={address}"
        try:
            coords = requests.get(link).json()["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"][
                "Point"]
        except KeyError:
            raise 'Вы превысили лимит YMAPS API!'
        x, y = coords["pos"].split()[::-1]

        """Save in db"""
        db_x_y_look = str(x) + ' ' + str(y)
        cur.execute(f"""INSERT INTO map_markers VALUES 
        ('{address}', '{db_x_y_look}')""")
        con.commit()
        return {"x": x, "y": y}

    x, y = res[0][0].split()
    return {"x": x, "y": y}


session = create_session()


@app.get('/get_products/')
def get_all_products() -> list:
    """Take all data from avito favorites"""
    page = 2
    products = []
    while True:
        response = get_data_from_current_page(session=session, page=page)
        if not response:
            break

        page += 1
        products.extend(response)
        break
    return products


@app.get('/', response_class=HTMLResponse)
async def map_page(request: Request):
    return templates.TemplateResponse("placemark.html", {"request": request, "API_KEY": API_KEY})


if __name__ == '__main__':
    uvicorn.run('main:app', host="127.0.0.1", port=8000)
