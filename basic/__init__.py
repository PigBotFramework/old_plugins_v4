import random
import time
import traceback

from pbf.controller import Cache
from pbf.controller.Banwords import BanWords
from pbf.controller.Handler import p
from pbf.controller.Data import yamldata
from pbf.controller.Menu import Menu
from pbf.controller.PBF import PBF
from pbf.statement import Statement
from pbf.statement.AtStatement import AtStatement
from pbf.statement.FaceStatement import FaceStatement
from pbf.statement.TextStatement import TextStatement
from pbf.utils.CQCode import CQCode
from pbf.utils.RegCmd import RegCmd
from pbf.model.KeywordModel import KeywordModel
from pbf.model.SettingNameModel import SettingNameModel

_name = "基础插件"
_version = "1.0.0"
_description = "机器人基础插件"
_author = "xzyStudio"
_cost = 0.00
_markdown = '''
# basic
pigBotFrameworkPlugin

# 基础插件
功能：基础功能

# 作者
- XzyStudio猪比作者
'''


class basic(PBF):
    @RegCmd(
        name="菜单",
        usage="菜单",
        alias=["help", "帮助"],
        permission="anyone",
        description="查看所有指令",
        mode="只因器人"
    )
    def menu(self):
        Menu(self.data).sendModedMenu()

    @RegCmd(
        name="Message上报基本功能",
        usage="",
        permission="anyone",
        description="监听message事件",
        mode="只因器人",
        type="message"
    )
    def messageListener(self):
        p("messageListener")

        se = self.data.se
        gid = se.get('group_id')
        uid = se.get('user_id')
        settings = self.data.groupSettings
        utils = self.utils
        client = self.client
        message = self.data.message
        botSettings = self.data.botSettings
        only_for_uid = self.getUidOnly()
        banwords = self.banwords
        userCoin = self.data.userCoin
        regex = self.regex
        cid = se.get('channel_id')
        uuid = self.data.uuid
        logger = self.logger
        pbf = self

        if uid != botSettings._get('owner') and se.get('channel_id') == None and gid == None and botSettings._get(
                "reportPrivate"):
            client.msg(
                FaceStatement(151),
                TextStatement('主人，有人跟我说话话~', 1),
                TextStatement(f'内容为：{message}', 1),
                TextStatement(f'回复请对我说：回复|{se.get("user_id")}|{se.get("message_id")}|<回复内容>')
            ).custom(botSettings._get('owner'))
            if uid != botSettings._get('second_owner'):
                client.msg(
                    FaceStatement(151),
                    TextStatement('副主人，有人跟我说话话~', 1),
                    TextStatement(f'内容为：{message}', 1),
                    TextStatement(f'回复请对我说：回复|{se.get("user_id")}|{se.get("message_id")}|<回复内容>')
                ).custom(botSettings._get('second_owner'))

        if '[CQ:at,qq=' + str(botSettings._get('owner')) + ']' in message and botSettings._get("reportAt"):
            client.msg(
                FaceStatement(151),
                TextStatement('主人，有人艾特你~', 1),
                TextStatement(f'消息内容：{message}', 1),
                TextStatement(f'来自群：{gid}', 1),
                TextStatement(f'来自用户：{uid}')
            ).custom(botSettings._get('owner'))

        if '[CQ:at,qq=' + str(botSettings._get('second_owner')) + ']' in message and botSettings._get("reportAt"):
            client.msg(
                FaceStatement(151),
                TextStatement('副主人，有人艾特你~', 1),
                TextStatement(f'消息内容：{message}', 1),
                TextStatement(f'来自群：{gid}', 1),
                TextStatement(f'来自用户：{uid}')
            ).custom(botSettings._get('second_owner'))

        if (f'[CQ:at,qq={botSettings._get("myselfqn")}]' in message) and (userCoin == -1) and not only_for_uid:
            client.msg(
                Statement('reply', id=se.get('message_id')),
                TextStatement(f'{botSettings._get("name")}想起来你还没有注册哦~', 1),
                TextStatement('发送“'),
                TextStatement('注册', transFlag=False),
                TextStatement('”可以让机器人认识你啦QAQ')
            ).send()

        # 防刷屏
        if se.get('channel_id') == None and gid != None:
            messagelist = Cache.get('messagelist', [])
            mlob = utils.findObject('qn', gid, messagelist)
            mlo = mlob.get('object')
            if mlo == 404:
                messagelist.append({'qn': gid, 'uid': uid, 'times': 1})
            else:
                arrnum = mlob.get('num')
                if mlo.get('uid') == uid:
                    if mlo.get('times') >= int(settings._get('AntiswipeScreen')):
                        messagelist[arrnum]['times'] = 1
                        if se.get('sender').get('role') == "member":
                            datajson = client.CallApi('set_group_ban',
                                                      {"group_id": gid, "user_id": uid, "duration": 600})
                            if datajson['status'] != 'ok':
                                client.msg(
                                    FaceStatement(151),
                                    TextStatement('检测到刷屏，但禁言失败！')
                                ).send()
                            else:
                                client.msg(
                                    FaceStatement(54),
                                    TextStatement('检测到刷屏，已禁言！')
                                ).send()
                    else:
                        messagelist[arrnum]['times'] += 1
                    # 禁言警告
                    if mlo.get('times') == int(settings._get('AntiswipeScreen')) - 1 and se.get('sender').get(
                            'role') == "member":
                        client.msg(
                            TextStatement('刷屏禁言警告', 1),
                            TextStatement('请不要连续发送消息超过设定数量！')
                        ).send()
                else:
                    messagelist[arrnum]['times'] = 1
                    messagelist[arrnum]['uid'] = uid
            Cache.set('messagelist', messagelist)

        try:
            if gid != None:
                if settings._get('increase_verify', default=0) != 0:
                    if pbf.execPlugin('basic@getVerifyStatus') == True and '人机验证 ' not in message:
                        client.CallApi('delete_msg', {'message_id': se.get('message_id')})
        except Exception:
            pass

        if message[0:10] == '[CQ:reply,' and '撤回' in message:
            if uid == botSettings._get('owner') or uid == botSettings._get('second_owner') or se.get('sender').get(
                    'role') != 'member':
                reply_id = CQCode(message).get('id', type='reply')
                client.CallApi('delete_msg', {'message_id': se.get('message_id')})
                client.CallApi('delete_msg', {'message_id': reply_id})
                return
            else:
                client.msg(TextStatement('[CQ:face,id=151] 就你？先拿到管理员再说吧！')).send()

        # 违禁词检查
        if not botSettings._get("strict_security_mode"):
            if settings != None:
                weijinFlag = True if settings._get('weijinCheck') else False
            else:
                weijinFlag = True
            if banwords.check(weijinFlag) == True and not only_for_uid:
                return 'OK.'

        try:
            # 关键词回复
            if settings != None:
                kwFlag = 1 if settings._get('keywordReply') else 0
            else:
                kwFlag = 1
            if kwFlag and not only_for_uid:
                keywordlist = KeywordModel()._getAll()
                for i in keywordlist:
                    replyFlag = False
                    if int(userCoin) >= int(i.get('coin')) and (i.get("qn") == 0 or gid == i.get("qn")):
                        replyFlag = True
                    if replyFlag == True:
                        replyKey = regex.replace(i.get('key'))
                        if regex.pair(replyKey, message):
                            regex.send(i.get('value'))
        except Exception:
            logger.warn(f'{traceback.format_exc()}')

    @RegCmd(
        name="群聊设置",
        usage="群聊设置",
        alias=["设置列表"],
        permission="anyone",
        description="查看群聊的设置",
        mode="群聊管理"
    )
    def printConfig(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        settings = self.data.groupSettings

        messageList = [
            FaceStatement(151),
            TextStatement('本群机器人配置：')
        ]
        for i in SettingNameModel()._getAll():
            if int(i.get('isHide')) == 1:
                continue

            messageList.append(TextStatement(' ', 1))
            messageList.append(FaceStatement(54))
            messageList.append(TextStatement(i.get('name')))
            messageList.append(TextStatement('：'))
            messageList.append(TextStatement(i.get('description'), 1))
            messageList.append(TextStatement('    值：'))
            messageList.append(TextStatement(settings._get(i.get('description')), transFlag=False))

            if i.get('other') != '':
                messageList.append(TextStatement(' ', 1))
                messageList.append(TextStatement('    描述：'))
                messageList.append(TextStatement(i.get('other')))
        self.client.msg(messageList).send()

    @RegCmd(
        name="转图片 ",
        usage="转图片 <消息内容>",
        permission="owner",
        description="将文字转为图片",
        mode="实用功能"
    )
    def sendImage(self):
        self.client.data.message = self.data.message
        self.client.msg().image()

    @RegCmd(
        name="回复|",
        usage="见机器人的私聊提示",
        permission="owner",
        description="回复私聊消息",
        mode="只因器人",
        hidden=1
    )
    def replyPM(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message
        uuid = self.data.uuid

        message1 = message.split('|')
        userid = message1[0]
        messageid = message1[1]
        message = message1[2]

        self.client.msg(Statement('reply', id=messageid), TextStatement(message)).custom(userid)
        self.client.msg(FaceStatement(151), TextStatement('回复成功！')).custom(uid)

    @RegCmd(
        name="指令帮助 ",
        usage="指令帮助 <指令内容>",
        permission="anyone",
        description="查看指令帮助",
        mode="只因器人"
    )
    def commandhelp(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message
        print(message)

        for i in Cache.get('commandListenerList'):
            content = i.name.strip()
            promisetext = str()
            if message == content:
                if i.permission == 'admin' or i.permission == 'ao':
                    promisetext = '管理员'
                elif i.permission == 'owner':
                    promisetext = '我的主人'
                elif i.permission == 'anyone':
                    promisetext = '任何人'
                elif i.permission == 'ro':
                    promisetext = '真正的主人'
                elif i.permission == 'xzy':
                    promisetext = '最高管理员'

                alias: str = ''
                for l in i.alias:
                    alias += l + ' '

                self.client.msg(
                    FaceStatement(189),
                    TextStatement('指令帮助', 1),
                    FaceStatement(54),
                    TextStatement('指令内容：'),
                    TextStatement(i.name, 1),
                    FaceStatement(54),
                    TextStatement('指令用法：'),
                    TextStatement(i.usage, 1),
                    FaceStatement(54),
                    TextStatement('指令解释：'),
                    TextStatement(i.description, 1),
                    FaceStatement(54),
                    TextStatement('指令权限：'),
                    TextStatement(promisetext, 1),
                    FaceStatement(54),
                    TextStatement('指令分类：'),
                    TextStatement(i.mode, 1, transFlag=False),
                    FaceStatement(54),
                    TextStatement('指令别名：'),
                    TextStatement(alias, 1, transFlag=False),
                    FaceStatement(54),
                    TextStatement('指令执行：'),
                    TextStatement(i.function)
                ).send()
                return
        self.client.msg('没有这个指令呢qwq').send()

    @RegCmd(
        name="Request上报基本功能",
        usage="",
        permission="anyone",
        description="监听request事件",
        mode="只因器人",
        type="request"
    )
    def requestListener(self):
        se = self.data.se
        botSettings = self.data.botSettings
        uid = se.get('user_id')
        settings = self.data.groupSettings
        gid = se.get('group_id')
        isGlobalBanned = self.data.isGlobalBanned

        if se.get('request_type') == 'group':
            if se.get('sub_type') == 'invite' and botSettings._get('autoAcceptGroup') and isGlobalBanned == None:
                # 邀请机器人加群
                print('group invite')
                return '{"approve":true}'
            elif uid == yamldata.get('chat').get('owner'):
                # 最高管理员一律同意
                print('group invite')
                return '{"approve":true}'
            elif settings._get('autoAcceptGroup') != 0 and se.get('sub_type') == 'add':
                # 有人要加群
                print('group add')
                if isGlobalBanned == None:
                    return '{"approve":true}'
                else:
                    self.client.msg(
                        FaceStatement(151),
                        TextStatement(f'已禁止用户{uid}加群', 1),
                        TextStatement(f'原因：{isGlobalBanned._get("reason")}')
                    ).custom(None, gid)
            elif settings._get('autoAcceptGroup') == 0:
                self.client.msg(
                    FaceStatement(151),
                    TextStatement('管理员快来，有人要加群！')
                ).send()

        elif se.get('request_type') == 'friend' and botSettings._get('autoAcceptFriend'):
            print('friend')
            if isGlobalBanned == None:
                return '{"approve":true}'
            else:
                self.client.msg(
                    FaceStatement(151),
                    TextStatement(f'已禁止用户{uid}加好友', 1),
                    TextStatement(f'原因：{isGlobalBanned._get("reason")}')
                ).custom(botSettings._get('owner'))
                self.client.msg(
                    FaceStatement(151),
                    TextStatement(f'已禁止用户{uid}加好友', 1),
                    TextStatement(f'原因：{isGlobalBanned._get("reason")}')
                ).custom(botSettings._get('second_owner'))

    @RegCmd(
        name="Notice上报基本功能",
        usage="",
        permission="anyone",
        description="监听notice事件",
        mode="只因器人",
        type="notice"
    )
    def noticeListener(self):
        userCoin = self.data.userCoin
        se = self.data.se
        gid = se.get('group_id')
        cid = se.get('channel_id')
        uid = se.get('user_id')
        message = se.get('message')
        settings = self.data.groupSettings
        uuid = self.data.uuid
        botSettings = self.data.botSettings

        if se.get('notice_type') == 'group_ban' and se.get('user_id') == se.get('self_id'):
            # 禁言机器人
            self.checkBan()

        elif se.get('notice_type') == 'group_recall' and int(settings._get('recallFlag')) != 0 and se.get('operator_id') != botSettings._get('myselfqn') and se.get('user_id') != botSettings._get('myselfqn'):
            # 消息防撤回
            data = self.client.CallApi('get_msg', {"message_id": se.get('message_id')})
            if BanWords(self.data).find(data.get('data').get('message')) == False and 'http' not in data.get(
                    'data').get('message'):
                self.client.msg(
                    FaceStatement(54),
                    TextStatement('消息防撤回：', 1),
                    AtStatement(se.get('operator_id')),
                    TextStatement('撤回了'),
                    AtStatement(se.get('user_id')),
                    TextStatement('发送的一条消息', 1),
                    TextStatement('消息内容：'),
                    TextStatement(data.get('data').get('message'))
                ).send()
            else:
                self.client.msg(
                    FaceStatement(54),
                    AtStatement(se.get('operator_id')),
                    TextStatement('撤回了'),
                    AtStatement(se.get('user_id')),
                    TextStatement('发送的一条不可见人的消息')
                ).send()

        elif se.get('notice_type') == 'notify':
            # 戳机器人
            if se.get('sub_type') == 'poke' and se.get('target_id') == botSettings._get(
                    'myselfqn') and botSettings._get("chuo"):
                chuo = botSettings._get("chuo").split()
                chuoReply = chuo[random.randint(0, len(chuo) - 1)]
                self.client.msg(
                    AtStatement(se.get('user_id')),
                    TextStatement(chuoReply)
                ).send()

        elif se.get('notice_type') == 'group_increase':
            # 有人进群
            if settings._get('increase') != 0:
                message = f"[CQ:at,qq={se.get('user_id')}] {settings._get('increase_notice')}"
                userdata = self.client.CallApi("get_stranger_info", {'user_id': uid}).get("data")
                replaceList = [
                    ["{user}", uid],
                    ["{userimg}",
                     f"[CQ:image,Cache=0,url=http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100,file=http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100]"],
                    ["{username}", userdata.get("nickname")],
                    ["{userlevel}", userdata.get("level")]
                ]
                for i in replaceList:
                    if i[0] in message:
                        message = message.replace(i[0], str(i[1]))

                self.client.msg().raw(message)
                if uid == botSettings._get("myselfqn"):
                    self.client.msg().raw(
                        f"{botSettings._get('name')}悄悄告诉你，我有很多功能，但是有些功能可能你并不需要，你可以发送指令「修改设置」来关掉他们。\n无脑禁言我会惹怒我的哦！")
            if settings._get('increase_verify') != 0:
                self.increaseVerify()

        elif se.get('notice_type') == 'group_decrease' and settings._get('decrease') != 0:
            # 有人退群
            if se.get('sub_type') == 'leave':
                message = self.data.groupSettings._get("decrease_notice_leave")
                userdata = self.client.CallApi("get_stranger_info", {'user_id': uid}).get("data")
                replaceList = [
                    ["{user}", uid],
                    ["{userimg}",
                     f"[CQ:image,Cache=0,url=http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100,file=http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100]"],
                    ["{username}", userdata.get("nickname")],
                    ["{userlevel}", userdata.get("level")]
                ]
                for i in replaceList:
                    if i[0] in message:
                        message = message.replace(i[0], str(i[1]))

                self.send(message)

            elif 'kick' in se.get('sub_type'):
                message = self.data.groupSettings._get("decrease_notice_kick")
                userdata = self.client.CallApi("get_stranger_info", {'user_id': uid}).get("data")
                replaceList = [
                    ["{user}", uid],
                    ["{userimg}",
                     f"[CQ:image,Cache=0,url=http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100,file=http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100]"],
                    ["{username}", userdata.get("nickname")],
                    ["{userlevel}", userdata.get("level")],
                    ["{operator}", se.get("operator_id")]
                ]
                for i in replaceList:
                    if i[0] in message:
                        message = message.replace(i[0], str(i[1]))

                self.send(message)

        elif se.get('notice_type') == 'essence':
            # 精华消息
            if se.get('sub_type') == 'add' and settings._get('delete_es') != 0:
                self.client.CallApi('delete_essence_msg', {'message_id': se.get('message_id')})
                self.client.msg(
                    TextStatement('已自动撤回成员'),
                    AtStatement(se.get('sender_id')),
                    TextStatement('设置的精华消息')
                ).send()
            elif se.get('sub_type') == 'delete' and se.get('operator_id') != botSettings._get('myselfqn'):
                data = self.client.CallApi('get_msg', {"message_id": se.get('message_id')})

                self.client.msg(
                    TextStatement('很不幸，'),
                    AtStatement(se.get('operator_id')),
                    TextStatement('撤回了一个精华消息', 1),
                    TextStatement(f"消息内容：{data.get('data').get('message')}")
                ).send()

    @RegCmd(
        name="人机验证 ",
        usage="见提示",
        permission="anyone",
        description="入群人机验证",
        mode="群聊管理"
    )
    def increaseVerifyCommand(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        for i in range(len(increaseVerifyList)):
            if increaseVerifyList[i].get('uid') == uid and increaseVerifyList[i].get('gid') == gid:
                if increaseVerifyList[i].get('pswd') == self.data.message:
                    self.send('正在验证...')
                    increaseVerifyList[i]['pswd'] = None
                else:
                    self.client.msg().raw('你这验证码太假了！')
                return
        self.send(f'[CQ:at,qq={uid}] 没有找到验证信息！')

    def increaseVerify(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        pswd = self.utils.generateCode(4)
        limit = self.data.groupSettings._get('increase_verify', default=0)
        increaseVerifyList.append({"uid": uid, "gid": gid, "pswd": pswd})
        self.client.msg(
            AtStatement(uid),
            TextStatement(f'请在{limit}秒内发送指令“'),
            TextStatement(f'人机验证 {pswd}', transFlag=False),
            TextStatement('”注意中间有空格！')
        ).send()
        l = 0
        for i in range(len(increaseVerifyList)):
            if increaseVerifyList[i].get('uid') == uid and increaseVerifyList[i].get('gid') == gid:
                l = i
                break
        limit = int(limit)
        while limit >= 0:
            # print(increaseVerifyList)
            if increaseVerifyList[l].get('pswd') == None:
                increaseVerifyList[l]["pswd"] = "continue"
                self.client.msg().raw('[CQ:at,qq={0}] 恭喜，验证通过！'.format(uid))
                increaseVerifyList.pop(l)
                return
            limit -= 1
            time.sleep(1)
        self.client.msg().raw('[CQ:at,qq={0}] 到时间啦，飞机票一张！'.format(uid))
        self.client.CallApi('set_group_kick', {'group_id': gid, 'user_id': uid})
        increaseVerifyList.remove(l)

    def getVerifyStatus(self):
        for i in range(len(increaseVerifyList)):
            if increaseVerifyList[i].get('uid') == self.data.se.get('user_id') and increaseVerifyList[i].get(
                    'gid') == self.data.se.get('group_id'):
                if increaseVerifyList[i]["pswd"] == "continue":
                    return False
                return True
        return False

    def passs(self):
        pass

    def checkBan(self):
        if self.data.se.get("sub_type") == "lift_ban":
            # 解禁言
            return

        self.data.groupSettings._set(bannedCount=int(self.data.groupSettings._get("bannedCount"))+1)

        if int(self.data.groupSettings._get("bannedCount")) + 1 >= int(self.data.botSettings._get("bannedCount")):
            # 超过次数，自动退群
            self.client.CallApi('set_group_leave', {"group_id": self.data.se.get("group_id")})
            self.data.groupSettings._set(bannedCount=0)
            if self.data.groupSettings._get("connectQQ"):
                self.client.msg(TextStatement(
                    "[自动消息] 请注意，您关联的群组（{}）因违反机器人规定致使机器人退群，您将会承担连带责任".format(
                        self.data.se.get("group_id")))).custom(self.data.groupSettings._get("connectQQ"))
            self.client.msg(TextStatement(
                "[提示] 群：{}\n关联成员：{}\n行为：禁言{}次\n已自动退群".format(self.data.se.get("group_id"),
                                                                              self.data.groupSettings._get("connectQQ"),
                                                                              int(self.data.groupSettings._get(
                                                                                  "bannedCount")) + 1))).custom(
                self.data.botSettings._get("owner"))

    @RegCmd(
        name="chatgpt ",
        usage="chatgpt <内容>",
        permission="anyone",
        description="chatgpt",
        mode="ChatGPT"
    )
    def chatgpt(self):
        try:
            '''
            from pbf.controller.PbfStruct import chatbot
            self.send(f"[CQ:reply,id={self.data.se.get('message_id')}] 正在获取...")

            message = ""
            for i in chatbot.ask(self.data.message):
                message = i.get('message')
            
            self.send(f"[CQ:reply,id={self.data.se.get('message_id')}] {message}")
            '''
            self.send('face54 该功能正在检修...')
        except Exception as e:
            self.send(
                f"[CQ:reply,id={self.data.se.get('message_id')}] 发生错误，可能是正在生成回答（同一会话不支持并发）或者请求频率超限！\n具体错误详见日志")
            self.logger.warning(traceback.format_exc())


increaseVerifyList = []
