# -*- coding: utf-8 -*-

from ConfigParser import SafeConfigParser
import enum

class config_category(EnumWithName):
    KEYWORD_DICT = 0, 'KeywordDictionary'
    TIMEOUT = 1, 'Timeout'

class config_category_kw_dict(EnumWithName):
    CREATE_DUPLICATE = 0, 'PossibleDuplicateCDSeconds'
    REPEAT_CALL = 1, 'RepeatCallCDSeconds'
    ARRAY_SEPARATOR = 2, 'InLineArraySeparator'
    MAX_QUERY_OUTPUT_COUNT = 3, 'MaxQueryOutputCount'
    MAX_SIMPLE_STRING_LENGTH = 4, 'MaxSimpleStringLength'
    MAX_INFO_OUTPUT_COUNT = 5, 'MaxInfoOutputCount'
    MAX_MESSAGE_TRACK_OUTPUT_COUNT = 6, 'MaxMessageTrackOutputCount'
    DEFAULT_RANK_RESULT_COUNT = 7, 'DefaultRankResultCount'

class config_category_timeout(EnumWithName):
    CALCULATOR = 0, 'Calculator'

class config_manager(SafeConfigParser):
    def __init__(self, file_path):
        super(config_manager, self).__init__()
        self.read(file_path)

    def get(self, cat_enum, key_enum):
        return self.get(str(cat_enum), str(key_enum))

    def getint(self, cat_enum, key_enum):
        return super(config_manager, self).getint(str(cat_enum), str(key_enum))

class EnumWithName(enum.Enum):
    def __new__(cls, value, name):
        member = object.__new__(cls)
        member._value_ = value
        member._name = name
        return member

    def __int__(self):
        return self.value

    def __str__(self):
        return self._name

    def __unicode__(self):
        return unicode(self._name.decode('utf-8'))


