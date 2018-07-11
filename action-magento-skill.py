#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from hermes_python.hermes import Hermes
from message import Message

MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))

INTENT_LIST_CART_ITEMS = "alrouen:listCartItems"
INTENT_ADD_ITEM = "alrouen:addItem"
INTENT_ORDER_STATUS = "alrouen:orderStatus"
INTENT_SMALL_TALK = "alrouen:smallTalk"
INTENT_YES = "alrouen:sayYes"
INTENT_NO = "alrouen:sayNo"

ALL_INTENTS = [INTENT_LIST_CART_ITEMS, INTENT_ADD_ITEM, INTENT_ORDER_STATUS, INTENT_SMALL_TALK]
YES_NO = [INTENT_YES , INTENT_NO]

SKILL_MESSAGES = {
    'fr': {
        'hello': [
            "Bonjour, que puis-je faire pour vous aider ?"
        ],
        'youAreWelcome': [
            "Mais de rien. De quelle manière puis-je vous aider ?",
            "Je vous en pris. Comment puis-je vous aider ?"
        ],
        'bye': [
            "Très bien, à bientôt",
            "Au revoir, à bientôt"
        ],
        'and': " et ",
        'lookingForPastOrder': "Je recherche dans votre historique d'achat.",
        'addItemConfirmation': "Je vous propose d'ajouter {}. C'est bien ça ?",
        'itemAdded': "Voilà, c'est enregistré",
        'itemNotAdded': "Pas de problème, je n'ai rien ajouter",
        'cahier': "cahier de 96 pages",
        'encre': "paquet de cartouches d'encre noire"
    }
}

ACTION_ADDITEMS = "__add_items"


class MagentoSkill:
    def __init__(self):
        self.messages = Message(SKILL_MESSAGES, 'fr')
        self.__current_add_items = []

    def build_items_array(self, items, quantities):
        items_with_quantities = []
        for i in range(0, len(items)):
            q = quantities[i].value if i < len(quantities) else 1.0
            items_with_quantities.append((items[i].value, int(q)))

        return items_with_quantities

    def build_add_item_sentence(self, items_with_quantities):
        items_list = map(lambda iq: "{} {}".format(iq[1], self.messages.get(iq[0])), items_with_quantities)
        _and = self.messages.get('and')

        if len(items_list) > 1:
            items_str = _and.join([
                ", ".join(items_list[:-1]),
                items_list[-1]
            ])
        else:
            items_str = items_list[0]

        return self.messages.get('addItemConfirmation').format(items_str)

    def add_item(self, hermes, intent_message):
        items = []
        quantities = []

        if intent_message.slots.item:
            items = intent_message.slots.item.all()

        if intent_message.slots.quantity:
            quantities = intent_message.slots.quantity.all()

        items_with_quantities = self.build_items_array(items, quantities)
        self.__current_add_items = items_with_quantities
        hermes.publish_end_session(intent_message.session_id, self.messages.get('lookingForPastOrder'))
        hermes.publish_start_session_action('default', self.build_add_item_sentence(items_with_quantities), YES_NO, True, custom_data=ACTION_ADDITEMS)

    def list_cart_items(self, hermes, intent_message):
        hermes.publish_end_session(intent_message.session_id, "Je ne vois rien dans votre panier pour le moment")

    def order_status(self, hermes, intent_message):
        hermes.publish_end_session(intent_message.session_id, "Je ne vois aucune commande pour le moment")

    def small_talk(self, hermes, intent_message):

        if intent_message.slots.thanks:
            hermes.publish_continue_session(intent_message.session_id, self.messages.get('youAreWelcome'), ALL_INTENTS)
        elif intent_message.slots.hello:
            hermes.publish_continue_session(intent_message.session_id, self.messages.get('hello'), ALL_INTENTS)
        elif intent_message.slots.bye:
            hermes.publish_end_session(intent_message.session_id, self.messages.get('bye'))

    def yes(self, hermes, intent_message):

        if intent_message.custom_data == ACTION_ADDITEMS:
            self.__current_add_items = []
            hermes.publish_end_session(intent_message.session_id, self.messages.get('itemAdded'))

    def no(self, hermes, intent_message):

        if intent_message.custom_data == ACTION_ADDITEMS:
            self.__current_add_items = []
            hermes.publish_end_session(intent_message.session_id, self.messages.get('itemNotAdded'))


    def start(self):
        with Hermes(MQTT_ADDR) as h:
            h \
                .subscribe_intent(INTENT_LIST_CART_ITEMS, self.list_cart_items) \
                .subscribe_intent(INTENT_ADD_ITEM, self.add_item) \
                .subscribe_intent(INTENT_ORDER_STATUS, self.order_status) \
                .subscribe_intent(INTENT_SMALL_TALK, self.small_talk) \
                .subscribe_intent(INTENT_YES, self.yes) \
                .subscribe_intent(INTENT_NO, self.no) \
                .start()


if __name__ == "__main__":
    magentoSkill = MagentoSkill()
    magentoSkill.start()
