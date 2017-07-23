# -*- coding: utf-8 -*-

# import custom module
from bot import text_msg, oxford_dict, webpage_auto_gen
from bot.system import line_api_proc, string_is_int

import errno, os, sys, tempfile
import traceback
import validators
import time
from collections import defaultdict
from urlparse import urlparse
from cgi import escape
from datetime import datetime, timedelta
from error import error
from flask import Flask, request, url_for

# import for Oxford Dictionary
import httplib
import requests
import json

# Database import
from db import kw_dict_mgr, kwdict_col, group_ban, gb_col, message_tracker, msg_track_col

# tool import
from tool import mff, random_gen

# games import
import game

# import from LINE MAPI
from linebot import (
    LineBotApi, WebhookHandler, exceptions
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageTemplateAction,
    ButtonsTemplate, URITemplateAction, PostbackTemplateAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent
)

# Databases initialization
kwd = kw_dict_mgr("postgres", os.environ["DATABASE_URL"])
gb = group_ban("postgres", os.environ["DATABASE_URL"])
msg_track = message_tracker("postgres", os.environ["DATABASE_URL"])

# Main initialization
app = Flask(__name__)
boot_up = datetime.now() + timedelta(hours=8)

rec = {'cmd': defaultdict(int),
       'last_stk': defaultdict(str), 
       'Silence': False, 'Intercept': True, 
       'webpage': 0}
report_content = {'Error': {}, 
                  'FullQuery': {}, 
                  'FullInfo': {},
                  'Text': {}}
game_object = {'rps': defaultdict(game.rps)}

class command(object):
    def __init__(self, min_split=2, max_split=2, non_user_permission_required=False):
        self._split_max = max_split
        self._split_min = min_split
        self._count = 0
        self._non_user_permission_required = non_user_permission_required

    @property
    def split_max(self):
        """Maximum split count."""
        return self._split_max + (1 if self._non_user_permission_required else 0) 

    @property
    def split_min(self):
        """Minimum split count."""
        return self._split_min

    @property
    def count(self):
        """Called count."""
        return self._count

    @count.setter
    def count(self, value):
        """Called count."""
        self._count = value 

    @property
    def non_user_permission_required(self):
        """Required Permission"""
        return self._non_user_permission_required

# TODO: cmd dict modulize
sys_cmd_dict = {'S': command(1, 1, True), 
            'A': command(2, 4, False), 
            'M': command(2, 4, True), 
            'D': command(1, 2, False), 
            'R': command(1, 2, True), 
            'Q': command(1, 2, False), 
            'C': command(0, 0, True), 
            'I': command(1, 2, False), 
            'K': command(2, 2, False), 
            'P': command(0, 1, False), 
            'G': command(0, 1, False), 
            'GA': command(1, 5, True), 
            'H': command(0, 1, False), 
            'SHA': command(1, 1, False), 
            'O': command(1, 1, False), 
            'B': command(0, 0, False), 
            'RD': command(1, 2, False),
            'STK': command(0, 0, False)}

game_cmd_dict = {'RPS': command(0, 4, True)}

helper_cmd_dict = {'MFF': command(1, 8, True)}

# Line Bot Environment initialization
MAIN_UID_OLD = 'Ud5a2b5bb5eca86342d3ed75d1d606e2c'
MAIN_UID = 'U089d534654e2c5774624e8d8c813000e'
main_silent = False
administrator = os.getenv('ADMIN', None)
group_admin = os.getenv('G_ADMIN', None)
group_mod = os.getenv('G_MOD', None)
if administrator is None:
    print('The SHA224 of ADMIN not defined. Program will be terminated.')
    sys.exit(1)
if group_admin is None:
    print('The SHA224 of G_ADMIN not defined. Program will be terminated.')
    sys.exit(1)
if group_mod is None:
    print('The SHA224 of G_MOD not defined. Program will be terminated.')
    sys.exit(1)
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)
line_api = line_api_proc(api)

# Oxford Dictionary Environment initialization
oxford_dict_obj = oxford_dict('en')

# File path
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# TODO: move to msg_handle_game
class game_processor(object):
    def __init__(self, game_object):
        self._game_object = game_object

    def RPS(self, src, params):
        cid = line_api_proc.source_channel_id(src)
        uid = line_api_proc.source_user_id(src)

        if params[4] is not None:
            rps_obj = self._game_object['rps'].get(cid)
            if rps_obj is not None and isinstance(rps_obj, game.rps):
                action = params[1]
                if action == 'ADD':
                    item_type = params[2]
                    is_sticker = params[3]
                    content = params[4]

                    battle_item = None

                    if item_type == 'R':
                        battle_item = game.battle_item.rock
                    if item_type == 'P':
                        battle_item = game.battle_item.paper
                    if item_type == 'S':
                        battle_item = game.battle_item.scissor

                    if battle_item is not None:
                        if is_sticker == 'STK':
                            if string_is_int(content):
                                rps_obj.register_battle_item(battle_item, True, content)
                                text = rps_obj.battle_item_dict_text()
                            else:
                                error.main.incorrect_param(u'參數4', u'整數，以代表貼圖ID')
                        elif is_sticker == 'TXT':
                            rps_obj.register_battle_item(battle_item, False, content)
                            text = rps_obj.battle_item_dict_text()
                        else:
                            text = error.main.incorrect_param(u'參數3', u'STK(是貼圖ID)或TXT(文字訊息)')
                    else:
                        text = error.main.incorrect_param(u'參數2', u'S(剪刀)、R(石頭)或P(布)')
                else:
                    text = error.main.incorrect_param(u'參數1', u'ADD')
            else:
                text = error.main.miscellaneous(u'尚未建立猜拳遊戲。')
        elif params[3] is not None:
            scissor = params[1]
            rock = params[2]
            paper = params[3]

            rps_obj = game.rps(True if isinstance(src, SourceUser) else False, rock, paper, scissor)
            if isinstance(rps_obj, game.rps):
                if line_api_proc.is_valid_user_id(uid):
                    rps_obj.register_player(line_api.profile(uid).display_name, uid)
                    text = u'遊戲建立成功。\n\n剪刀貼圖ID: {}\n石頭貼圖ID: {}\n布貼圖ID: {}'.format(scissor, rock, paper)
                    self._game_object['rps'][cid] = rps_obj
                else:
                    text = error.main.unable_to_receive_user_id()
            else:
                text = rps_obj
        elif params[2] is not None:
            rps_obj = self._game_object['rps'].get(cid)
            if rps_obj is not None and isinstance(rps_obj, game.rps):
                action = params[1]
                battle_item_text = params[2]

                if action == 'RST':
                    if battle_item_text == 'R':
                        rps_obj.reset_battle_item(game.battle_item.rock)
                        text = u'已重設代表【石頭】的物件。'
                    elif battle_item_text == 'P':
                        rps_obj.reset_battle_item(game.battle_item.paper)
                        text = u'已重設代表【布】的物件。'
                    elif battle_item_text == 'S':
                        rps_obj.reset_battle_item(game.battle_item.scissor)
                        text = u'已重設代表【剪刀】的物件。'
                    else:
                        text = error.main.incorrect_param(u'參數2', u'R(石頭), P(布), S(剪刀)')
                else:
                    text = error.main.incorrect_param(u'參數1', u'RST')
            else:
                text = error.main.miscellaneous(u'尚未建立猜拳遊戲。')
        elif params[1] is not None:
            rps_obj =  self._game_object['rps'].get(cid)
            action = params[1]

            if rps_obj is not None and isinstance(rps_obj, game.rps):
                if action == 'DEL':
                    self._game_object['rps'][cid] = None
                    text = u'猜拳遊戲已刪除。'
                elif action == 'RST':
                    rps_obj.reset_statistics()
                    text = u'猜拳遊戲統計資料已重設。'
                elif action == 'R':
                    text = rps_obj.battle_item_dict_text(game.battle_item.rock)
                elif action == 'P':
                    text = rps_obj.battle_item_dict_text(game.battle_item.paper)
                elif action == 'S':
                    text = rps_obj.battle_item_dict_text(game.battle_item.scissor)
                elif action == 'PLAY':
                    uid = line_api_proc.source_user_id(src)
                    if line_api_proc.is_valid_user_id(uid):
                        player_name = line_api.profile(uid).display_name
                        reg_success = rps_obj.register_player(player_name, uid)
                        if reg_success:
                            text = u'成功註冊玩家 {}。'.format(player_name)
                        else:
                            text = u'玩家 {} 已存在於玩家清單中。'.format(player_name)
                    else:
                        text = error.main.unable_to_receive_user_id()
                elif action == 'SW':
                    rps_obj.enabled = not rps_obj.enabled
                    if rps_obj.enabled:
                        text = u'遊戲已繼續。'
                    else:
                        text = u'遊戲已暫停。'
                else:
                    text = error.main.incorrect_param(u'參數1', u'DEL, RST, R, P, S, PLAY, SW')
            else:
                text = error.main.miscellaneous(u'尚未建立猜拳遊戲。')
        else:
            rps_obj = self._game_object['rps'].get(cid)
            if rps_obj is not None and isinstance(rps_obj, game.rps):
                if rps_obj.player_dict is not None and len(rps_obj.player_dict) > 0:
                    text = game.rps.player_stats_text(rps_obj.player_dict)
                    text += '\n\n'
                    text += rps_obj.battle_item_dict_text()
                else:
                    text = error.main.miscellaneous(u'無玩家資料。')
            else:
                text = error.main.miscellaneous(u'尚未建立猜拳遊戲。')

        return text

# Text parser initialization
command_executor = text_msg(line_api, kwd, gb, msg_track, oxford_dict_obj, [group_mod, group_admin, administrator])
game_executor = game_processor(game_object)

# Webpage auto generator
webpage_generator = webpage_auto_gen.webpage()

# function for create tmp dir for download content
def make_static_tmp_dir():
    try:
        os.makedirs(static_tmp_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(static_tmp_path):
            pass
        else:
            raise


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except exceptions.InvalidSignatureError:
        abort(400)

    return 'OK'

@app.route("/error", methods=['GET'])
def get_error_list():
    rec['webpage'] += 1
    content = u'開機時間: {}\n\n錯誤清單(根據時間排列):\n'.format(boot_up)
    content += '\n'.join(
        [webpage_auto_gen.webpage.html_hyperlink(timestamp, request.url_root + url_for('get_error_message', timestamp=timestamp)[1:]) 
         for timestamp in webpage_generator.error_list()]
        )
        
    return content.replace('\n', '<br/>')

@app.route("/error/<timestamp>", methods=['GET'])
def get_error_message(timestamp):
    rec['webpage'] += 1
    content = webpage_generator.get_content(webpage_auto_gen.content_type.Error, timestamp)
    return webpage_auto_gen.webpage.html_paragraph(content)

@app.route("/query/<timestamp>", methods=['GET'])
def full_query(timestamp):
    rec['webpage'] += 1
    content = webpage_generator.get_content(webpage_auto_gen.content_type.Query, timestamp)
    return webpage_auto_gen.webpage.html_paragraph(content)

@app.route("/info/<timestamp>", methods=['GET'])
def full_info(timestamp):
    rec['webpage'] += 1
    content = webpage_generator.get_content(webpage_auto_gen.content_type.Info, timestamp)
    return webpage_auto_gen.webpage.html_paragraph(content)

@app.route("/full/<timestamp>", methods=['GET'])
def full_content(timestamp):
    rec['webpage'] += 1
    content = webpage_generator.get_content(webpage_auto_gen.content_type.Text, timestamp)
    return webpage_auto_gen.webpage.html_paragraph(content)

@app.route("/ranking/<type>", methods=['GET'])
def full_ranking(type):
    rec['webpage'] += 1
    if type == 'user':
        content = kw_dict_mgr.list_user_created_ranking(api, kwd.user_created_rank())
    elif type == 'used':
        content = kw_dict_mgr.list_keyword_ranking(kwd.order_by_usedrank())
    else:
        content = error.webpage.no_content()
        
    return webpage_auto_gen.webpage.html_paragraph(content)


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    global game_object
    global command_executor
    global game_executor

    token = event.reply_token
    text = event.message.text
    src = event.source
    splitter = '\n'
    
    msg_track.log_message_activity(line_api_proc.source_channel_id(src), 1)

    if text == '561563ed706e6f696abbe050ad79cf334b9262da6f83bc1dcf7328f2':
        rec['Intercept'] = not rec['Intercept']
        api.reply_message(token, TextSendMessage(text='Bot {}.'.format(
            'start to intercept messages' if rec['Intercept'] else 'stop intercepting messages')))
        return
    elif rec['Intercept']:
        intercept_text(event)

    if text == administrator:
        rec['Silence'] = not rec['Silence']
        api.reply_message(token, TextSendMessage(text='Bot set to {mute}.'.format(mute='Silent' if rec['Silence'] else 'Active')))
        return
    elif rec['Silence']:
        return

    try:
        if splitter in text:
            head, cmd, oth = text_msg.split(text, splitter, 3)

            if head == 'JC':
                rec['cmd']['JC'] += 1
                
                # TODO: put inside cmd proc module - static method - verify command - BEGIN
                if cmd not in sys_cmd_dict:
                    text = error.main.invalid_thing(u'指令', cmd)
                    api_reply(token, TextSendMessage(text=text), src)
                    return

                max_prm = sys_cmd_dict[cmd].split_max
                min_prm = sys_cmd_dict[cmd].split_min
                params = text_msg.split(oth, splitter, max_prm)

                if min_prm > len(params) - params.count(None):
                    text = error.main.lack_of_thing(u'參數')
                    api_reply(token, TextSendMessage(text=text), src)
                    return

                params.insert(0, None)
                sys_cmd_dict[cmd].count += 1
                # TODO: put inside cmd proc module - static method - verify command - END
                
                # SQL Command
                if cmd == 'S':
                    text = command_executor.S(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # ADD keyword & ADD top keyword
                elif cmd == 'A' or cmd == 'M':
                    if sys_cmd_dict[cmd].non_user_permission_required:
                        text = command_executor.M(src, params)
                    else:
                        text = command_executor.A(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # DELETE keyword & DELETE top keyword
                elif cmd == 'D' or cmd == 'R':
                    if sys_cmd_dict[cmd].non_user_permission_required:
                        text = command_executor.R(src, params)
                    else:
                        text = command_executor.D(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # QUERY keyword
                elif cmd == 'Q':
                    text = command_executor.Q(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # INFO of keyword
                elif cmd == 'I':
                    text = command_executor.I(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # RANKING
                elif cmd == 'K':
                    text = command_executor.K(src, params)
                    
                    api_reply(token, TextSendMessage(text=text), src)
                # SPECIAL record
                elif cmd == 'P':
                    text = command_executor.P(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # GROUP ban basic (info)
                elif cmd == 'G':
                    text = command_executor.G(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # GROUP ban advance
                elif cmd == 'GA':
                    texts = command_executor.GA(src, params)

                    api_reply(token, [TextSendMessage(text=text) for text in texts], src)
                # get CHAT id
                elif cmd == 'H':
                    output = command_executor.H(src, params)

                    api_reply(token, [TextSendMessage(text=output[0]), TextSendMessage(text=output[1])], src)
                # SHA224 generator
                elif cmd == 'SHA':
                    text = command_executor.SHA(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # Look up vocabulary in OXFORD Dictionary
                elif cmd == 'O':
                    text = command_executor.O(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # RANDOM draw
                elif cmd == 'RD':
                    text = command_executor.RD(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                # last STICKER message
                elif cmd == 'STK':
                    text = command_executor.STK(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                else:
                    sys_cmd_dict[cmd].count -= 1
            elif head == 'HELP':
                rec['cmd']['HELP'] += 1
                data = text_msg.split(text, splitter, 2)

                # TODO: restruct helper
                # TODO: Helper modulize
                if data[1].upper().startswith('MFF'):
                    api_reply(token, [TextSendMessage(text=mff.mff_dmg_calc.help_code()),
                                      TextSendMessage(text=u'下則訊息是訊息範本，您可以直接將其複製，更改其內容，然後使用。或是遵照以下格式輸入資料。\n\n{代碼(參見上方)} {參數}(%)\n\n例如:\nMFF\nSKC 100%\n魔力 1090%\n魔力 10.9\n\n欲察看更多範例，請前往 https://sites.google.com/view/jellybot/mff傷害計算'),
                                      TextSendMessage(text=mff.mff_dmg_calc.help_sample())], src)
                else:
                    job = mff.mff_dmg_calc.text_job_parser(data[1])

                    dmg_calc_dict = [[u'破防前非爆擊(弱點屬性)', mff.mff_dmg_calc.dmg_weak(job)],
                                     [u'破防前爆擊(弱點屬性)', mff.mff_dmg_calc.dmg_crt_weak(job)],
                                     [u'已破防非爆擊(弱點屬性)', mff.mff_dmg_calc.dmg_break_weak(job)],
                                     [u'已破防爆擊(弱點屬性)', mff.mff_dmg_calc.dmg_break_crt_weak(job)],
                                     [u'破防前非爆擊(非弱點屬性)', mff.mff_dmg_calc.dmg(job)],
                                     [u'破防前爆擊(非弱點屬性)', mff.mff_dmg_calc.dmg_crt(job)],
                                     [u'已破防非爆擊(非弱點屬性)', mff.mff_dmg_calc.dmg_break(job)],
                                     [u'已破防爆擊(非弱點屬性)', mff.mff_dmg_calc.dmg_break_crt(job)]]

                    text = u'傷害表:'
                    for title, value in dmg_calc_dict:
                        text += u'\n\n'
                        text += u'{}\n首發: {:.0f}\n連發: {:.0f}\n累積傷害(依次): {}'.format(title,
                                                                                            value['first'],
                                                                                            value['continual'],
                                                                                            u', '.join('{:.0f}'.format(x) for x in value['list_of_sum']))
                    
                    api_reply(token, TextSendMessage(text=text), src)
            elif head == 'G':
                rec['cmd']['GAME'] += 1

                if cmd not in game_cmd_dict:
                    text = error.main.invalid_thing(u'遊戲', cmd)
                    api_reply(token, TextSendMessage(text=text), src)
                    return
                
                max_prm = game_cmd_dict[cmd].split_max
                min_prm = game_cmd_dict[cmd].split_min
                params = text_msg.split(oth, splitter, max_prm)

                if min_prm > len(params) - params.count(None):
                    text = error.main.lack_of_thing(u'參數')
                    api_reply(token, TextSendMessage(text=text), src)
                    return

                params.insert(0, None)

                # GAME - Rock-Paper-Scissor
                if cmd == 'RPS':
                    text = game_executor.RPS(src, params)

                    api_reply(token, TextSendMessage(text=text), src)
                else:
                    game_cmd_dict[cmd].count -= 1

        rps_obj = game_object['rps'].get(line_api_proc.source_channel_id(src))
        if rps_obj is not None:
            rps_text = minigame_rps_capturing(rps_obj, False, text, line_api_proc.source_user_id(src))
            if rps_text is not None:
                api_reply(token, TextSendMessage(text=rps_text), src)
                return

        replied = auto_reply_system(token, text, False, src)
        if (text.startswith('JC') or text.startswith('HELP') or text.startswith('G')) and ((' ' or '  ') in text) and not replied:
            msg = u'小水母指令分隔字元已從【雙空格】修改為【換行】。'
            msg += u'\n\n如欲輸入指令，請以換行分隔指令，例如:\nJC\nA\n你！\n我？'
            msg += u'\n\n如果參數中要包含換行的話，請輸入【\\n】。\n另外，JC RD的文字抽籤中，原先以換行分隔，現在則以單空格分隔。'
            text = error.main.miscellaneous(msg)
            api_reply(token, TextSendMessage(text=text), src)
            return
    except exceptions.LineBotApiError as ex:
        text = u'開機時間: {}\n\n'.format(boot_up)
        text += u'LINE API錯誤，狀態碼: {}\n\n'.format(ex.status_code)
        for err in ex.error.details:
            text += u'錯誤內容: {}\n錯誤訊息: {}\n'.format(err.property, err.message.decode("utf-8"))

        send_error_url_line(token, text, line_api_proc.source_channel_id(src))
    except Exception as exc:
        text = u'開機時間: {}\n\n'.format(boot_up)
        exc_type, exc_obj, exc_tb = sys.exc_info()
        text += u'錯誤種類: {}\n錯誤訊息: {}\n第{}行'.format(exc_type, exc.message.decode("utf-8"), exc_tb.tb_lineno)

        send_error_url_line(token, text, line_api_proc.source_channel_id(src))
    return 

    if text == 'confirm':
        confirm_template = ConfirmTemplate(text='Do it?', actions=[
            MessageTemplateAction(label='Yes', text='Yes!'),
            MessageTemplateAction(label='No', text='No!'),
        ])
        template_message = TemplateSendMessage(
            alt_text='Confirm alt text', template=confirm_template)
        api_reply(event.reply_token, template_message, src)
    elif text == 'carousel':
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='hoge1', title='fuga1', actions=[
                URITemplateAction(
                    label='Go to line.me', uri='https://line.me'),
                PostbackTemplateAction(label='ping', data='ping')
            ]),
            CarouselColumn(text='hoge2', title='fuga2', actions=[
                PostbackTemplateAction(
                    label='ping with text', data='ping',
                    text='ping'),
                MessageTemplateAction(label='Translate Rice', text='米')
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Buttons alt text', template=carousel_template)
        api_reply(event.reply_token, template_message, src)


@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    package_id = event.message.package_id
    sticker_id = event.message.sticker_id
    rep = event.reply_token
    src = event.source
    cid = line_api_proc.source_channel_id(src)
    
    # TODO: Modulize handle received sticker message 
    rec['last_stk'][cid] = sticker_id

    global game_object
    rps_obj = game_object['rps'].get(cid)

    msg_track.log_message_activity(cid, 3)

    if rps_obj is not None:
        text = minigame_rps_capturing(rps_obj, True, sticker_id, line_api_proc.source_user_id(src))
        if text is not None:
            api_reply(rep, TextSendMessage(text=text), src)
            return

    if isinstance(event.source, SourceUser):
        results = kwd.search_sticker_keyword(sticker_id)
        
        if results is not None:
            kwdata = u'相關回覆組ID: {}。\n'.format(u', '.join([unicode(result[kwdict_col.id]) for result in results]))
        else:
            kwdata = u'無相關回覆組ID。\n'

        api_reply(
                rep,
                [TextSendMessage(text=kwdata + u'貼圖圖包ID: {}\n貼圖圖片ID: {}'.format(package_id, sticker_id)),
                 TextSendMessage(text=u'圖片路徑(Android):\nemulated\\0\\Android\\data\\jp.naver.line.android\\stickers\\{}\\{}'.format(package_id, sticker_id)),
                 TextSendMessage(text=u'圖片路徑(Windows):\nC:\\Users\\USER_NAME\\AppData\\Local\\LINE\\Data\\Sticker\\{}\\{}'.format(package_id, sticker_id)),
                 TextSendMessage(text=u'圖片路徑(網路):\n{}'.format(kw_dict_mgr.sticker_png_url(sticker_id)))],
                src
            )
    else:
        auto_reply_system(rep, sticker_id, True, src)



# Incomplete
@handler.add(PostbackEvent)
def handle_postback(event):
    return
    if event.postback.data == 'ping':
        api_reply(
            event.reply_token, TextSendMessage(text='pong'), event.source)


# Incomplete
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    msg_track.log_message_activity(line_api_proc.source_channel_id(event.source), 1)
    return

    api_reply(
        event.reply_token,
        LocationSendMessage(
            title=event.message.title, address=event.message.address,
            latitude=event.message.latitude, longitude=event.message.longitude
        ),
        event.source
    )


# Incomplete
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, AudioMessage))
def handle_content_message(event):
    msg_track.log_message_activity(line_api_proc.source_channel_id(event.source), 1)
    return

    if isinstance(event.message, ImageMessage):
        ext = 'jpg'
    elif isinstance(event.message, VideoMessage):
        ext = 'mp4'
    elif isinstance(event.message, AudioMessage):
        ext = 'm4a'
    else:
        return

    message_content = api.get_message_content(event.message.id)
    with tempfile.NamedTemporaryFile(dir=static_tmp_path, prefix=ext + '-', delete=False) as tf:
        for chunk in message_content.iter_content():
            tf.write(chunk)
        tempfile_path = tf.name

    dist_path = tempfile_path + '.' + ext
    dist_name = os.path.basename(dist_path)
    os.rename(tempfile_path, dist_path)

    api_reply(
        event.reply_token, [
            TextSendMessage(text='Save content.'),
            TextSendMessage(text=request.host_url + os.path.join('static', 'tmp', dist_name))
        ], event.source)


@handler.add(FollowEvent)
def handle_follow(event):
    api_reply(event.reply_token, introduction_template(), event.source)

# Incomplete
@handler.add(UnfollowEvent)
def handle_unfollow():
    return

    app.logger.info("Got Unfollow event")


@handler.add(JoinEvent)
def handle_join(event):
    src = event.source
    reply_token = event.reply_token
    cid = line_api_proc.source_channel_id(src)

    global command_executor

    if not isinstance(event.source, SourceUser):
        group_data = gb.get_group_by_id(cid)
        if group_data is None:
            added = gb.new_data(cid, MAIN_UID, administrator)
            msg_track.new_data(cid)

            api_reply(reply_token, 
                      [TextMessage(text=u'群組資料註冊{}。'.format(u'成功' if added else u'失敗')),
                       introduction_template()], 
                       cid)
        else:
            api_reply(reply_token, 
                      [TextMessage(text=u'群組資料已存在。'),
                       TextMessage(text=command_exec.G(src, [None, None, None])),
                       introduction_template()], 
                       cid)


def introduction_template():
    buttons_template = ButtonsTemplate(
            title=u'機器人簡介', text='歡迎使用小水母！', 
            actions=[
                URITemplateAction(label=u'點此開啟使用說明', uri='https://sites.google.com/view/jellybot'),
                URITemplateAction(label=u'點此導向開發者LINE帳號', uri='http://line.me/ti/p/~raenonx'),
                MessageTemplateAction(label=u'點此查看群組資料', text='JC\nG')
            ])
    template_message = TemplateSendMessage(
        alt_text=u'機器人簡介', template=buttons_template)
    return template_message


def api_reply(reply_token, msgs, src):
    if isinstance(msgs, TemplateSendMessage):
        msg_track.log_message_activity(line_api_proc.source_channel_id(src), 6)
    elif isinstance(msgs, TextSendMessage):
        msg_track.log_message_activity(line_api_proc.source_channel_id(src), 5)

    if not rec['Silence']:
        if not isinstance(msgs, (list, tuple)):
            msgs = [msgs]

        for msg in msgs:
            if isinstance(msg, TextSendMessage) and len(msg.text) > 2000:
                api.reply_message(reply_token, 
                                  TextSendMessage(text=error.main.text_length_too_long(webpage_generator.rec_text(msgs))))
                return

        api.reply_message(reply_token, msgs)
    else:
        print '=================================================================='
        print 'Bot set to silence. Expected message to reply will display below: '
        print msgs
        print '=================================================================='


def intercept_text(event):
    user_id = line_api_proc.source_user_id(event.source)
    user_profile = line_api.profile(user_id)

    print '==========================================='
    print 'From Channel ID \'{}\''.format(line_api_proc.source_channel_id(event.source))
    print 'From User ID \'{}\' ({})'.format(user_id, user_profile.display_name.encode('utf-8') if user_profile is not None else 'unknown')
    print 'Message \'{}\''.format(event.message.text.encode('utf-8'))
    print '=================================================================='


def auto_reply_system(token, keyword, is_sticker_kw, src):
    cid = line_api_proc.source_channel_id(src)

    if gb.is_group_set_to_silence(cid):
        return False

    res = kwd.get_reply(keyword, is_sticker_kw)
    if res is not None:
        msg_track.log_message_activity(line_api_proc.source_channel_id(src), 4 if is_sticker_kw else 2)
        result = res[0]
        reply = result[kwdict_col.reply].decode('utf-8')

        if result[kwdict_col.is_pic_reply]:
            line_profile = line_api.profile(result[kwdict_col.creator])

            api_reply(token, TemplateSendMessage(
                alt_text=u'圖片/貼圖回覆.\n關鍵字ID: {}'.format(id=result[kwdict_col.id]),
                template=ButtonsTemplate(text=u'由{}製作。\n回覆組ID: {}'.format(
                    error.main.line_account_data_not_found() if line_profile is None else line_profile.display_name,
                    result[kwdict_col.id]), 
                                         thumbnail_image_url=reply,
                                         actions=[
                                             URITemplateAction(label=u'Original Picture', uri=reply)
                                         ])), src)
            return True
        else:
            api_reply(token, 
                      TextSendMessage(text=reply),
                      src)
            return True

    return False


def minigame_rps_capturing(rps_obj, is_sticker, content, uid):
    if rps_obj is not None and line_api_proc.is_valid_user_id(uid) and rps_obj.has_player(uid):
        if rps_obj.enabled:
            battle_item = rps_obj.find_battle_item(is_sticker, content)
            if battle_item is not None:
                result = rps_obj.play(battle_item, uid)
                if result is not None:
                    return result
                else:
                    game_cmd_dict['RPS'].count += 1
                    if rps_obj.is_waiting_next:
                        return u'等待下一個玩家出拳中...'
                    if rps_obj.result_generated:
                        return rps_obj.result_text()


if __name__ == "__main__":
    # create tmp dir for download content
    make_static_tmp_dir()

    app.run(port=os.environ['PORT'], host='0.0.0.0')
