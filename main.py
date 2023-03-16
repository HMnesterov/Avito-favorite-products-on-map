import ssl
import browser_cookie3
import requests
from fastapi import FastAPI
import uvicorn
from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager
from requests.packages.urllib3.util import ssl_

from set import API_KEY

app = FastAPI()

cj = browser_cookie3.edge()

CIPHERS = """ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:AES256-SHA"""


class TlsAdapter(HTTPAdapter):

    def __init__(self, ssl_options=0, **kwargs):
        self.ssl_options = ssl_options
        super(TlsAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, *pool_args, **pool_kwargs):
        ctx = ssl_.create_urllib3_context(ciphers=CIPHERS, cert_reqs=ssl.CERT_REQUIRED, options=self.ssl_options)
        self.poolmanager = PoolManager(*pool_args, ssl_context=ctx, **pool_kwargs)


def create_session() -> Session:
    session = requests.session()
    adapter = TlsAdapter(ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1)
    session.mount("https://", adapter)
    return session


def take_favorites_from_page(session, url) -> list | None:
    data = session.request('GET', url, cookies=cj)
    try:
        favorites = data.json()["items"]
    except KeyError:
        return None
    return favorites


def get_important_data_from_curr_product(product: dict) -> dict:
    coords: dict = get_geocoords(product["address"])
    item_link: str = "https://www.avito.ru" + product["uri"]
    title: str = product["title"]

    return {"coords": coords, "item_link": item_link, "title": title}


def get_geocoords(address: str) -> dict:
    link = f"https://geocode-maps.yandex.ru/1.x/?apikey={API_KEY}&format=json&geocode={address}"
    coords = requests.get(link).json()["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]
    x, y = coords["pos"].split()[::-1]
    return {"x": x, "y": y}


session = create_session()


@app.get('/avito/{page}')
async def get_data_from_curr_avito_page(page: int):
    url = f'https://www.avito.ru/web/1/favorites/items/list?order=added_at__desc&page={page}'
    data = take_favorites_from_page(session=session, url=url)
    if not data:
        return {}
    response = [get_important_data_from_curr_product(product) for product in data]
    return response





if __name__ == '__main__':
    uvicorn.run('main:app', host="127.0.0.1", port=8000)