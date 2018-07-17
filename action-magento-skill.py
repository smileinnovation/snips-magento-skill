#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from hermes_python.hermes import Hermes
from message import Message
from magentoclient import MagentoClient, MagentoClientError, MagentoStockIssueError
from config_parser import SnipsConfigParser

MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))

INTENT_LIST_CART_ITEMS = "alrouen:listCartItems"
INTENT_PURGE_CART = "alrouen:purgeCart"
INTENT_ADD_ITEM = "alrouen:addItem"
INTENT_ORDER_STATUS = "alrouen:orderStatus"
INTENT_SMALL_TALK = "alrouen:smallTalk"
INTENT_YES = "alrouen:sayYes"
INTENT_NO = "alrouen:sayNo"

ALL_INTENTS = [INTENT_LIST_CART_ITEMS, INTENT_PURGE_CART, INTENT_ADD_ITEM, INTENT_ORDER_STATUS, INTENT_SMALL_TALK]
YES_NO = [INTENT_YES , INTENT_NO]

SKILL_MESSAGES = {
    'fr': {
        'hello': [
            "Bonjour, que puis-je faire pour vous aider ?",
            "Bonjour, comment puis-je vous aider ?"
        ],
        'youAreWelcome': [
            "Mais de rien.",
            "Je vous en pris."
        ],
        'newQuestion': [
            "Que puis-je faire d'autre pour vous aider ?",
            "Puis-je vous aider pour autre chose ?"
        ],
        'bye': [
            "à bientôt"
        ],
        'unknownSmallTalk': [
            "Je ne suis pas sur de vous avoir compris... "
        ],
        'and': " et ",
        'lookingForPastOrder': [
            "Bien sur, je recherche dans votre historique d'achat",
            "Pas de problème, je regarde dans vos derniers achats"
        ],
        'purgeCartConfirmation': "Voulez-vous supprimer cet article ?",
        'purgeCartPluralConfirmation': "Voulez-vous supprimer ces articles ?",
        'purgeDone': "Voilà votre panier est vide",
        'purgeCancel': "Pas de problème, je n'ai rien supprimé",
        'addItemConfirmation': "Je vous propose d'ajouter {}. C'est bien ça ?",
        'itemAdded': "Voilà l'article est enregistré",
        'itemsAdded': "Voilà les {} articles sont enregistré",
        'itemNotAdded': "Pas de problème, je n'ai rien ajouter",
        'noEnoughItem': "Désolé mais pour l'article {}, le stock n'est pas suffisant pour la quantité que vous demandez",
        'inYourCart': "J'ai trouvé {} article dans votre panier: {}",
        'inYourCartShort' : "J'ai trouvé {} article dans votre panier",
        'emptyCart': "Je ne vois rien dans votre panier pour le moment",
        'tooBigCart' : "Il y a plus de 10 articles dans votre paniers",
        'cahier': "cahier de 96 pages",
        'protegecahier': "Protège-cahier transparent vert",
        'encre': "étui de 24 cartouches d'encre noire",
        'stylo': "Stylo bille noire",
        'unknown_product': "produit que je ne connais pas",
        'order_status': 'Le status de votre dernière commande est celui-ci : {}',
        'unknown_status': 'inconnus'
    }
}

PRODUCTS = {
    '3329680637410': 'cahier',
    '3086126732343': 'encre',
    '0073228109695': 'stylo',
    '3210330734057': 'protegecahier'
}

ORDER_STATUS = {
    'canceled':'annulée',
    'closed':'fermée',
    'complete':'terminée',
    'holded':'en suspend',
    'payment_review':'en cours de validation paiement',
    'paypal_reversed':'annulation paypal',
    'pending': "en cours de préparation",
    'pending_payment':'en attente de paiement',
    'pending_paypal':'en attente de confirmation paypal',
    'processing':'en cours de traitement'
}

ACTION_ADD_ITEMS = "__add_items"
ACTION_PURGE_CART = "__purge_cart"


def _product_sku_by_name(name):
    return PRODUCTS.keys()[PRODUCTS.values().index(name)]


def _product_name_by_sku(sku):
    try:
        return PRODUCTS[sku]
    except KeyError:
        return None


def _status_name(status):
    try:
        return ORDER_STATUS[status]
    except KeyError:
        return None


class MagentoSkill:
    def __init__(self, magento_client):
        self.messages = Message(SKILL_MESSAGES, 'fr')
        self.__current_add_items = []
        self.__magento_client = magento_client

    def __sku_to_message(self, sku):
        product_name = _product_name_by_sku(sku)
        if product_name is not None:
            return self.messages.get(product_name)
        else:
            return self.messages.get('unknown_product')

    def build_items_array(self, items, quantities):
        items_with_quantities_and_sku = []
        for i in range(0, len(items)):
            q = quantities[i].value if i < len(quantities) else 1.0
            items_with_quantities_and_sku.append((items[i].value, int(q), _product_sku_by_name(items[i].value)))

        return items_with_quantities_and_sku

    def build_item_sequence(self, items_with_quantities, item_renaming):
        items_list = map(lambda iq: "{} {}".format(iq[1], item_renaming(iq[0])), items_with_quantities)
        _and = self.messages.get('and')

        if len(items_list) > 1:
            items_str = _and.join([
                ", ".join(items_list[:-1]),
                items_list[-1]
            ])
        else:
            items_str = items_list[0]

        return items_str

    def build_add_item_sentence(self, items_with_quantities):

        def item_renaming(item_name):
            return self.messages.get(item_name)

        items_str = self.build_item_sequence(items_with_quantities, item_renaming)
        return self.messages.get('addItemConfirmation').format(items_str)

    def loop_new_question(self, hermes):
        hermes.publish_start_session_action('default', self.messages.get('newQuestion'), ALL_INTENTS, True, custom_data=None)

    def add_item(self, hermes, intent_message):
        items = []
        quantities = []

        if intent_message.slots.item:
            items = intent_message.slots.item.all()

        if intent_message.slots.quantity:
            quantities = intent_message.slots.quantity.all()

        self.__current_add_items = self.build_items_array(items, quantities)
        hermes.publish_end_session(intent_message.session_id, self.messages.get('lookingForPastOrder'))
        hermes.publish_start_session_action('default', self.build_add_item_sentence(self.__current_add_items), YES_NO, True, custom_data=ACTION_ADD_ITEMS)

    def list_cart_items(self, hermes, intent_message):

        items = self.__magento_client.get_cart_items()

        if len(items) == 0:
            hermes.publish_end_session(intent_message.session_id, self.messages.get('emptyCart'))
        elif len(items) > 10:
            hermes.publish_end_session(intent_message.session_id, self.messages.get('tooBigCart'))
        else:
            item_str = self.build_item_sequence(items, self.__sku_to_message)
            hermes.publish_end_session(intent_message.session_id, self.messages.get('inYourCart').format(len(items), item_str))

        self.loop_new_question(hermes)

    def purge_cart(self, hermes, intent_message):

        items = self.__magento_client.get_cart_items()

        if len(items) > 0:
            hermes.publish_end_session(intent_message.session_id, self.messages.get('inYourCartShort').format(len(items)))
            confirmation = self.messages.get('purgeCartPluralConfirmation') if len(items) > 1 else self.messages.get('purgeCartConfirmation')
            hermes.publish_start_session_action('default', confirmation, YES_NO, True, custom_data=ACTION_PURGE_CART)
        else:
            hermes.publish_end_session(intent_message.session_id, self.messages.get('emptyCart'))
            self.loop_new_question(hermes)

    def order_status(self, hermes, intent_message):

        orders = self.__magento_client.get_orders()

        if len(orders) > 0:
            status = orders[0]['status']
            status_name = _status_name(status)
            if status_name is None:
                status_name = self.messages.get('unknown_status')
            hermes.publish_end_session(intent_message.session_id, self.messages.get('order_status').format(status_name))
        else:
            hermes.publish_end_session(intent_message.session_id, "Je ne vois aucune commande pour le moment")

        self.loop_new_question(hermes)

    def small_talk(self, hermes, intent_message):

        if intent_message.slots.bye:
            hermes.publish_end_session(intent_message.session_id, self.messages.get('bye'))
        elif intent_message.slots.thanks:
            hermes.publish_end_session(intent_message.session_id, "{} {}".format(self.messages.get('youAreWelcome'), self.messages.get('bye')))
        elif intent_message.slots.hello:
            hermes.publish_continue_session(intent_message.session_id, self.messages.get('hello'), ALL_INTENTS)
        else:
            hermes.publish_continue_session(intent_message.session_id, "{} {}".format(self.messages.get('unknownSmallTalk'), self.messages.get('newQuestion')), ALL_INTENTS)

    def yes(self, hermes, intent_message):

        if intent_message.custom_data == ACTION_ADD_ITEMS:
            try:
                added = self.__magento_client.add_items(self.__current_add_items)
                self.__current_add_items = []
                if added > 1:
                    hermes.publish_end_session(intent_message.session_id, self.messages.get('itemsAdded').format(added))
                elif added > 0:
                    hermes.publish_end_session(intent_message.session_id, self.messages.get('itemAdded'))

                self.loop_new_question(hermes)

            except MagentoStockIssueError as mce:
                self.__current_add_items = []
                hermes.publish_end_session(intent_message.session_id, self.messages.get('noEnoughItem').format(self.messages.get(_product_name_by_sku(mce.item))))
                self.loop_new_question(hermes)

        elif intent_message.custom_data == ACTION_PURGE_CART:
            self.__magento_client.purge_cart()
            hermes.publish_end_session(intent_message.session_id, self.messages.get('purgeDone'))
            self.loop_new_question(hermes)

    def no(self, hermes, intent_message):

        if intent_message.custom_data == ACTION_ADD_ITEMS:
            self.__current_add_items = []
            hermes.publish_end_session(intent_message.session_id, self.messages.get('itemNotAdded'))
            self.loop_new_question(hermes)

        elif intent_message.custom_data == ACTION_PURGE_CART:
            hermes.publish_end_session(intent_message.session_id, self.messages.get('purgeCancel'))
            self.loop_new_question(hermes)

    def start(self):
        with Hermes(MQTT_ADDR) as h:
            h \
                .subscribe_intent(INTENT_LIST_CART_ITEMS, self.list_cart_items) \
                .subscribe_intent(INTENT_PURGE_CART, self.purge_cart) \
                .subscribe_intent(INTENT_ADD_ITEM, self.add_item) \
                .subscribe_intent(INTENT_ORDER_STATUS, self.order_status) \
                .subscribe_intent(INTENT_SMALL_TALK, self.small_talk) \
                .subscribe_intent(INTENT_YES, self.yes) \
                .subscribe_intent(INTENT_NO, self.no) \
                .start()


if __name__ == "__main__":
    try:
        config = SnipsConfigParser.read_configuration_file('config.ini')

        if config['secret'] is not None:
            magento_host = config['secret']['magento_host']
            magento_user = config['secret']['magento_user']
            magento_password = config['secret']['magento_password']

            # THIS IS UGLY AND DANGEROUS... A MAGENTO CUSTOM API SHOULD EXISTS TO AVOID THIS !!! THIS IS FOR DEMO PURPOSE ONLY!!!
            # but Magento API is so stupid, that so far to retrieve order status I need admin credential.
            # Next release of our Magento Showroom instance will include custom API for such requests
            magento_admin = config['secret']['magento_admin']
            magento_admin_password = config['secret']['magento_admin_password']
            # .................................................................................................

            if magento_host is not None and magento_user is not None and magento_password is not None:
                magento_client = MagentoClient(host=magento_host, login=magento_user, password=magento_password, admin=magento_admin, admin_password=magento_admin_password)
                magentoSkill = MagentoSkill(magento_client)
                magentoSkill.start()
            else:
                print "Invalid configuration file (magento connection information are missing)."

        else:
            print "Invalid configuration file (magento connection information are missing)."

    except MagentoClientError as magento_error:
        print "{}: {}".format(magento_error.status_code, magento_error.message)
    except KeyError as ke:
        print "Configuration error with this key: {}".format(ke.message)
    except Exception as e:
        print repr(e)
        print e.message
