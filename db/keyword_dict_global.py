# -*- coding: utf-8 -*-

from .base import db_base, dict_like_mapping
import pymongo.cursor
import datetime
import error

from .keyword_dict import pair_data, group_dict_manager, PUBLIC_GROUP_ID, ActionNotAllowed

class word_dict_global(db_base):
    CLONE_TIMEOUT_SEC = 15
    CODE_OF_PUBLIC_GROUP = 'PUBLIC'

    def __init__(self, mongo_db_uri):
        super(word_dict_global, self).__init__(mongo_db_uri, group_dict_manager.WORD_DICT_DB_NAME, group_dict_manager.WORD_DICT_DB_NAME, True)

    def clone_by_id(self, id_or_id_list, target_gid, clone_executor, including_disabled=False, including_pinned=True):
        """Return inserted sequence id(s) Empty array if nothing cloned."""
        if isinstance(id_or_id_list, (int, long)):
            id_or_id_list = [id_or_id_list]

        if target_gid == word_dict_global.CODE_OF_PUBLIC_GROUP:
            target_gid = PUBLIC_GROUP_ID

        id_or_id_list = [int(id) for id in id_or_id_list]
        filter_dict = { pair_data.SEQUENCE: { '$in': id_or_id_list } }
        return self._clone_to_group(filter_dict, target_gid, clone_executor, including_disabled, including_pinned)

    def clone_from_group(self, source_gid, target_gid, clone_executor, including_disabled=False, including_pinned=True):
        """
        Return inserted sequence id(s). Empty array if nothing cloned.
        Set org_gid to PUBLIC to clone from public.
        Set new_gid to PUBLIC to clone to public.
        """
        if source_gid == word_dict_global.CODE_OF_PUBLIC_GROUP:
            source_gid = PUBLIC_GROUP_ID
        if target_gid == word_dict_global.CODE_OF_PUBLIC_GROUP:
            target_gid = PUBLIC_GROUP_ID
        filter_dict = { pair_data.AFFILIATED_GROUP: source_gid }
        return self._clone_to_group(filter_dict, target_gid, clone_executor, including_disabled, including_pinned)

    def clear(self, target_gid, clone_executor):
        """Return count of pair disabled."""
        if target_gid == word_dict_global.CODE_OF_PUBLIC_GROUP:
            raise ActionNotAllowed(error.error.main.miscellaneous(u'無法清除公用資料庫。'))

        return self.update_many({ pair_data.AFFILIATED_GROUP: target_gid, pair_data.PROPERTIES + '.' + pair_data.DISABLED: False }, 
                                { '$set': { pair_data.PROPERTIES + '.' + pair_data.DISABLED: True,
                                            pair_data.STATISTICS + '.' + pair_data.DISABLED_TIME: datetime.datetime.now(),
                                            pair_data.STATISTICS + '.' + pair_data.DISABLER: clone_executor } }).modified_count

    def _clone_to_group(self, filter_dict, new_gid, clone_executor, including_disabled=False, including_pinned=True):
        """Return empty array if nothing cloned."""
        import time

        data_list = []
        affected_kw_list = []

        _start_time = time.time()

        if not including_pinned:
            filter_dict[pair_data.PROPERTIES + '.' + pair_data.PINNED] = False

        if not including_disabled:
            filter_dict[pair_data.PROPERTIES + '.' + pair_data.DISABLED] = False

        find_cursor = self.find(filter_dict).sort([(pair_data.SEQUENCE, pymongo.ASCENDING)])

        for result_data in find_cursor:
            del result_data['_id']
            del result_data[pair_data.SEQUENCE]
            data = pair_data(result_data, True)
            affected_kw_list.append(data.keyword)
            data_list.append(data.clone(new_gid))

            if time.time() - _start_time > 15:
                raise RuntimeError('Clone process timeout, try another clone method, or split the condition array.')

        if len(data_list) > 0:
            self.update_many({ pair_data.KEYWORD: { '$in': affected_kw_list }, pair_data.AFFILIATED_GROUP: new_gid }, 
                             { '$set': { pair_data.PROPERTIES + '.' + pair_data.DISABLED: True,
                                         pair_data.STATISTICS + '.' + pair_data.DISABLED_TIME: datetime.datetime.now(),
                                         pair_data.STATISTICS + '.' + pair_data.DISABLER: clone_executor } })

            return self.insert_many(data_list).inserted_seq_ids
        else:
            return []

    def get_pairs_by_group_id(self, gid, including_disabled=False, including_pinned=True):
        """Return EMPTY LIST when nothing found"""
        find_cursor = self.find({ pair_data.AFFILIATED_GROUP: gid })
        return list(find_cursor)
