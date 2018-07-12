import requests
import json

CLIENT_TOKEN_URI = "rest/V1/integration/customer/token"
GET_CART_URI = "rest/default/V1/carts/mine"
GET_CART_ITEM_URI = "rest/default/V1/carts/mine/items"
ADD_TO_CART_URI = "rest/default/V1/carts/mine/items"


class MagentoClientError(Exception):
    def __init__(self, message, status_code):
        super(MagentoClientError, self).__init__(message)
        self.status_code = status_code


class MagentoClient:
    def __init__(self, host, login, password):
        self.__host = host
        self.__login = login
        self.__password = password
        self.__current_token = self.__get_client_token()

    @staticmethod
    def __process_response(response):
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise MagentoClientError(message=response.json()['message'], status_code=response.status_code)
        else:
            raise MagentoClientError(message="Something went wrong with Magento: {}".format(response.content), status_code=response.status_code)

    def __build_url(self, uri):
        return "{}/{}".format(self.__host.rstrip('/'), uri)

    def __auth_header(self):
        return {'Authorization': 'Bearer {}'.format(self.__current_token)}

    def __get_client_token(self):
        token_response = requests.post(
            url=self.__build_url(CLIENT_TOKEN_URI),
            json={
                'username': self.__login,
                'password': self.__password
            }
        )

        return MagentoClient.__process_response(token_response)

    def get_cart_items(self):
        items_response = requests.get(
            url=self.__build_url(GET_CART_ITEM_URI),
            headers=self.__auth_header()
        )
        return map(lambda item: (item['sku'], item['qty'], item['name'].encode('utf-8')), items_response.json())

    def add_items(self, items):

        cart_response = requests.get(
            url=self.__build_url(GET_CART_URI),
            headers=self.__auth_header()
        )
        quote_id = MagentoClient.__process_response(cart_response)['id']

        payload = map(lambda i: { 'quote_id': quote_id, 'sku': i[2], 'qty': i[1] }, items)

        ### Still in progress ... Magento API is strange....
        add_item_response = requests.post(
            url=self.__build_url(ADD_TO_CART_URI),
            headers=self.__auth_header(),
            json={ 'cartItem': payload[0] }
        )

        print add_item_response.status_code
        return MagentoClient.__process_response(add_item_response)





