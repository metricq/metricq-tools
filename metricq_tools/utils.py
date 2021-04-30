import re

from typing import List, Type, TypeVar

_C = TypeVar("_C", covariant=True)


def camelcase_to_kebabcase(camelcase: str) -> str:
    # Match empty string preceeding uppercase character, but not at the start
    # of the word. Replace with '-' and make lowercase to get kebab-case word.
    return re.sub(r"(?<!^)(?=[A-Z])", "-", camelcase).lower()


def kebabcase_to_camelcase(kebabcase: str) -> str:
    return "".join(part.title() for part in kebabcase.split("-"))


class CommandLineChoice:
    @classmethod
    def as_choice_list(cls) -> List[str]:
        return [
            camelcase_to_kebabcase(name) for name in getattr(cls, "__members__").keys()
        ]

    def as_choice(self) -> str:
        return camelcase_to_kebabcase(getattr(self, "name"))

    @classmethod
    def from_choice(cls: Type[_C], option: str) -> _C:
        member_name = kebabcase_to_camelcase(option)
        return getattr(cls, "__members__")[member_name]
