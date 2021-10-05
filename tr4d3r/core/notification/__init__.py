"""
Base class for sending notifications.

Notifications can be for transaction bookkeeping, analytics or interactive decision making.
"""
from tr4d3r.core import Loggable
from abc import abstractmethod
import telegram
from telegram.ext import ExtBot, Updater, MessageHandler, Filters, Defaults
import time
import pytz
import wrappy


class Chat(Loggable):
    def __init__(self, bot_config, client_config):
        self.init_bot(bot_config)
        assert hasattr(self, 'bot'), f"Expecting bot attribute"
        self.init_client(client_config)
        assert hasattr(self, 'client'), f"Expecting client attribute"
    
    @abstractmethod
    def init_bot(self, bot_config):
        pass
    
    @abstractmethod
    def init_client(self, client_config):
        pass
    
    @abstractmethod
    def ping(self, message, **kwargs):
        pass
    

class TelegramChat(Chat):
    """
    Chat based on python-telegram-bot.
    """
    PARSE_MODE = telegram.ParseMode.MARKDOWN_V2
    TIME_ZONE = 'Etc/GMT'
    
    def init_bot(self, bot_config):
        token = bot_config['token']
        defaults = Defaults(
            parse_mode=self.__class__.PARSE_MODE,
            tzinfo=pytz.timezone(self.__class__.TIME_ZONE),
        )
        self.bot = ExtBot(token=token, defaults=defaults)
        self.updater = Updater(token=token, use_context=True, defaults=defaults)
        self._good(f"Created bot {self.bot.get_me()}")
        
    def init_client(self, client_config):
        self.client = client_config['chat_id']
        self._good(f"Created client {self.client}")
    
    def ping(self, text, **kwargs):
        self.bot.send_message(
            text=text,
            chat_id=self.client,
            **kwargs,
        )
        
    def attach(self, document, **kwargs):
        self.bot.send_document(
            document=document,
            chat_id=self.client,
            **kwargs,
        )
        
    @wrappy.todo("Consider the implementation. Should this function exist? Should it be scheduled update fetch and callback instead? Should we use Updater or the current logic?")
    def catch(self, check_period=5):
        """
        Wait for an update from the client and return it.
        """
        updates = []
        while not updates:
            updates = self.bot.get_updates()
            update_dictl = [_u.to_dict() for _u in updates]
            valid_idx = [i for i, _d in enumerate(update_dictl) if _d['chat']['id'] == self.client]
            if valid_updates:
                last_idx = valid_idx[-1]
                last_update = updates[last_idx]
            else:
                time.sleep(check_period)
        return update