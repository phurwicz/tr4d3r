from rich.console import Console
from rich.prompt import Prompt, Confirm


class Loggable:

    """
    Base class that provides consistently templated logging.

    Inspired by `wasabi`'s `good`/`info`/`warn`/`fail` methods.

    [`Rich` style guide](https://rich.readthedocs.io/en/latest/style.html)
    """

    CONSOLE = Console()

    def _print(self, *args, **kwargs):
        self.__class__._cls_print(*args, **kwargs)

    def _good(self, message):
        self.__class__._cls_good(message)

    def _info(self, message):
        self.__class__._cls_info(message)

    def _warn(self, message):
        self.__class__._cls_warn(message)

    def _fail(self, message):
        self.__class__._cls_fail(message)

    @classmethod
    def _cls_print(cls, *args, **kwargs):
        cls.CONSOLE.print(*args, **kwargs)

    @classmethod
    def _cls_prompt(cls, message, **kwargs):
        answer = Prompt.ask(
            f":question: {cls.__name__}: {message}",
            **kwargs,
        )
        return answer

    @classmethod
    def _cls_confirm(cls, message, **kwargs):
        answer = Confirm.ask(
            f":question: {cls.__name__}: {message}",
            **kwargs,
        )
        return answer

    @classmethod
    def _cls_good(cls, message):
        cls.CONSOLE.print(
            f":green_circle: {cls.__name__}: {message}",
            style="green",
        )

    @classmethod
    def _cls_info(cls, message):
        cls.CONSOLE.print(f":blue_circle: {cls.__name__}: {message}", style="blue")

    @classmethod
    def _cls_warn(cls, message):
        cls.CONSOLE.print(
            f":yellow_circle: {cls.__name__}: {message}",
            style="yellow",
        )

    @classmethod
    def _cls_fail(cls, message):
        cls.CONSOLE.print(f":red_circle: {cls.__name__}: {message}", style="red")
