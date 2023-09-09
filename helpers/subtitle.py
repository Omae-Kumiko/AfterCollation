from configs.constants import UNIQUE_CHARS
from configs.user import MIN_UNIQUE_CHAR_IN_ASS


__all__ = ['getAssTextLangDict']




def getAssTextLangDict(text: str|list[str]) -> dict[str, bool]:
    if isinstance(text, list): text = ''.join(text)
    chars = set(text)
    ret = {}
    for k, v in UNIQUE_CHARS.items():
        ret[k] = True if len(chars.intersection(v)) > MIN_UNIQUE_CHAR_IN_ASS else False
    return ret
