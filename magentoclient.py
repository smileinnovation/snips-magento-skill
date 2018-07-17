import requests
import time

CLIENT_TOKEN_URI = "rest/V1/integration/customer/token"
GET_CART_URI = "rest/default/V1/carts/mine"
GET_CART_ITEM_URI = "rest/default/V1/carts/mine/items"
ADD_TO_CART_URI = "rest/default/V1/carts/mine/items"
ME_URI = "rest/default/V1/customers/me"
DELETE_ITEM_URI = "rest/default/V1/carts/mine/items/{}"

### SHOULD NOT EXISTS... FOR DEMO PURPOSE ONLY
ADMIN_TOKEN_URI = "rest/V1/integration/admin/token"

ORDER_URI = "rest/default/V1/orders"
ORDER_SEARCH_CRITERIA="searchCriteria[filter_groups][0][filters][0][field]=customer_lastname" \
                      "&searchCriteria[filter_groups][0][filters][0][value]={}" \
                      "&searchCriteria[filter_groups][0][filters][0][condition_type]=eq" \
                      "&searchCriteria[sortOrders][0][field]=created_at"


# Magento API call wrapper : catch 401 and try to recover it by refreshing the auth token
def __magento_client__(retry_interval=1, max_retry=1, fallback_return=None):
    def decorator(func):
        def wrapper(self, *args, **kwargs):

            retry = 0
            while max_retry == 0 or (max_retry > 0 and retry < max_retry):
                try:
                    return func(self, *args, **kwargs)
                except MagentoClientError as mce:
                    if mce.status_code == 401:
                        self._MagentoClient__get_client_token()
                    time.sleep(retry_interval)
                    retry += 1 if max_retry > 0 else 0
                    continue

            if fallback_return is not None:
                return fallback_return

        return wrapper

    return decorator


class MagentoClientError(Exception):
    def __init__(self, message, status_code):
        super(MagentoClientError, self).__init__(message)
        self.status_code = status_code


class MagentoStockIssueError(Exception):
    def __init__(self, message, status_code, item):
        super(MagentoStockIssueError, self).__init__(message)
        self.status_code = status_code
        self.item = item


class MagentoClient:
    def __init__(self, host, login, password, admin="", admin_password=""):
        self.__host = host
        self.__login = login
        self.__password = password

        ### THIS IS UGLY AND DANGEROUS... A MAGENTO CUSTOM API SHOULD EXISTS TO AVOID THIS !!! THIS IS FOR DEMO PURPOSE ONLY!!!
        self.__admin = admin
        self.__admin_password = admin_password
        ### ...........................................

        self.__get_client_token()

    @staticmethod
    def __process_response(response, item=""):

        # Everything ok
        if response.status_code == 200:
            return response.json()

        # Auth error => we raise client error exception with 401 status code
        elif response.status_code == 401:
            raise MagentoClientError(message=response.json()['message'], status_code=response.status_code)

        # Add item to cart return stock issue => we raise Stock exception
        elif response.status_code == 400 and response.json()['message'] and response.json()['message'].encode('utf-8').startswith("We don't have as many"):
                raise MagentoStockIssueError(message=response.json()['message'], status_code=response.status_code, item=item)

        # Any other error else => we raise client error exception
        else:
            raise MagentoClientError(message="Something went wrong with Magento: {}".format(response.content), status_code=response.status_code)

    def __build_url(self, uri, query=None):

        if query is None:
            return "{}/{}".format(self.__host.rstrip('/'), uri)
        else:
            return "{}/{}?{}".format(self.__host.rstrip('/'), uri, query)

    def __auth_header(self):
        return {'Authorization': 'Bearer {}'.format(self.__current_token)}

    def __custom_auth_header(self, token):
        return {'Authorization': 'Bearer {}'.format(token)}

    def __get_client_token(self):
        token_response = requests.post(
            url=self.__build_url(CLIENT_TOKEN_URI),
            json={
                'username': self.__login,
                'password': self.__password
            }
        )
        self.__current_token = MagentoClient.__process_response(token_response)

    def __get_customer_lastname(self):
        return MagentoClient.__process_response(requests.get(
            url=self.__build_url(ME_URI),
            headers=self.__auth_header()
        ))['lastname']

    def __get_admin_token(self):
        token_response = requests.post(
            url=self.__build_url(ADMIN_TOKEN_URI),
            json={
                'username': self.__admin,
                'password': self.__admin_password
            }
        )
        return MagentoClient.__process_response(token_response)

    @__magento_client__(max_retry=3, fallback_return=[])
    def get_cart_items(self):
        items_response = MagentoClient.__process_response(requests.get(
            url=self.__build_url(GET_CART_ITEM_URI),
            headers=self.__auth_header()
        ))
        # We capture only elements we need
        return map(lambda item: (item['sku'], item['qty'], item['name'].encode('utf-8')), items_response)

    @__magento_client__(max_retry=3, fallback_return=0)
    def add_items(self, items):

        # First we need to get a the cart id to be able to insert items into it
        cart_response = requests.get(
            url=self.__build_url(GET_CART_URI),
            headers=self.__auth_header()
        )
        quote_id = MagentoClient.__process_response(cart_response)['id']

        # The item list must be transform into something Magento can understand
        magento_items = map(lambda i: { 'quote_id': quote_id, 'sku': i[2], 'qty': i[1] }, items)

        # Sor I did found any way to insert in bulk all different item...
        # so I need to iterate and call the API for each of them
        item_added = 0
        for magento_item in magento_items:
            MagentoClient.__process_response(requests.post(
                url=self.__build_url(ADD_TO_CART_URI),
                headers=self.__auth_header(),
                json={ 'cartItem': magento_item }
            ), item=magento_item['sku'])
            item_added = item_added + 1

        return item_added

    @__magento_client__(max_retry=3, fallback_return=0)
    def purge_cart(self):

        # First we need to get a the cart' items to be able to delete each of them
        cart_response = requests.get(
            url=self.__build_url(GET_CART_URI),
            headers=self.__auth_header()
        )
        cart = MagentoClient.__process_response(cart_response)
        cart_items = cart['items']

        def remove_item(item_id):
            return requests.delete(
                url=self.__build_url(DELETE_ITEM_URI.format(item_id)),
                headers=self.__auth_header()
            )

        results = map(lambda i: MagentoClient.__process_response(remove_item(i['item_id'])), cart_items)
        return len(results)

    @__magento_client__(max_retry=3, fallback_return=[])
    def get_orders(self):

        customer_lastname = self.__get_customer_lastname()
        admin_token = self.__get_admin_token()

        query_parameters = ORDER_SEARCH_CRITERIA.format(customer_lastname)
        url = self.__build_url(ORDER_URI, query_parameters)
        headers = self.__custom_auth_header(admin_token)

        return MagentoClient.__process_response(requests.get(
            url=url,
            headers=headers
        ))['items']







